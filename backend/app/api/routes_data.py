"""Data generation, validation and export endpoints (ADMINISTRATOR / RISK_REVIEWER)."""
from __future__ import annotations
import json, os, re, threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.api import serializers as S
from app.api.deps import TransactionalRoute, admin_only, get_db, reviewer_or_admin, staff_only
from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.core.security import Actor
from app.data_generator.config import GenConfig
from app.data_generator.runner import reproducibility_check, run_generation
from app.models import DatasetRun, ValidationRun
from app.schemas.requests import GenerateRequest
from app.services import evaluation
from app.services import workflow as W

router = APIRouter(prefix="/api", tags=["data"], route_class=TransactionalRoute)
_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _export_dir(request: Request) -> str:
    return os.path.join(request.app.state.settings.data_dir, "exports", "current")


def _run_dict(r: DatasetRun | None):
    if r is None:
        return None
    return {"run_id": r.run_id, "seed": r.seed, "scale": r.scale, "anomaly_injection": r.anomaly_injection,
            "status": r.status, "config": r.config, "row_counts": r.row_counts, "checksums": r.checksums,
            "reproducibility": r.reproducibility, "notes": r.notes, "error": r.error,
            "generator_version": r.generator_version, "started_at": r.started_at, "finished_at": r.finished_at,
            "triggered_by": r.triggered_by}


def _val_dict(v: ValidationRun | None):
    if v is None:
        return None
    return {"run_id": v.run_id, "triggered_by": v.triggered_by, "started_at": v.started_at, "finished_at": v.finished_at,
            "checks": v.checks, "metrics": v.metrics, "evaluation": v.evaluation, "finding_count": v.finding_count}


@router.post("/data/generate", status_code=202)
def generate(body: GenerateRequest, request: Request, actor: Actor = Depends(admin_only), db=Depends(get_db)):
    """DESTRUCTIVE: replaces ALL dataset records (customer submissions included). Requires confirm=true."""
    if not body.confirm:
        raise ValidationFailed("Regeneration deletes all existing applicants, quotes, policies and related records. "
                               "Resend with confirm=true to proceed.")
    if db.scalars(select(DatasetRun).where(DatasetRun.status == "RUNNING")).first():
        raise ConflictError("A data generation run is already in progress")
    cfg = GenConfig(seed=body.seed, scale=body.scale, anomalies=body.anomalies)
    run_id = f"GEN-{db.scalar(select(func.count()).select_from(DatasetRun)) + 1:03d}"
    db.add(DatasetRun(run_id=run_id, seed=cfg.seed, scale=cfg.scale, anomaly_injection=cfg.anomalies, config=cfg.as_dict(),
                      status="RUNNING", generator_version=cfg.as_dict()["generator_version"], started_at=W.utcnow(),
                      triggered_by=actor.user_id))
    db.commit()
    engine, out = request.app.state.engine, _export_dir(request)
    job = lambda: run_generation(engine, cfg, out_dir=out, triggered_by=actor.user_id, run_id=run_id)  # noqa: E731
    if body.background:
        def safe():
            try:
                job()
            except Exception:       # status/error is recorded on the DatasetRun row by run_generation
                pass
        threading.Thread(target=safe, daemon=True, name=f"datagen-{run_id}").start()
        return {"run_id": run_id, "status": "RUNNING", "message": "Generation started; poll GET /api/data/status"}
    job()
    return {"run_id": run_id, "status": db.get(DatasetRun, run_id) and "COMPLETED", "message": "Generation finished"}


@router.get("/data/status")
def status(actor: Actor = Depends(staff_only), db=Depends(get_db)):
    last = db.scalars(select(DatasetRun).order_by(DatasetRun.run_id.desc())).first()
    return {"latest_run": _run_dict(last), "running": bool(last and last.status == "RUNNING"),
            "live_row_counts": evaluation.row_counts(db)}


@router.post("/validation/run")
def run_validation_endpoint(actor: Actor = Depends(reviewer_or_admin), db=Depends(get_db)):
    run = evaluation.run_and_persist_validation(db, actor.user_id)
    return _val_dict(run)


@router.get("/data/validation")
def latest_validation(actor: Actor = Depends(staff_only), db=Depends(get_db)):
    v = db.scalars(select(ValidationRun).order_by(ValidationRun.run_id.desc())).first()
    if v is None:
        raise NotFoundError("No validation run yet; POST /api/validation/run")
    return _val_dict(v)


@router.post("/data/reproducibility-check", status_code=202)
def repro(body: GenerateRequest, request: Request, actor: Actor = Depends(admin_only), db=Depends(get_db)):
    """Regenerates twice in isolated in-memory databases (never touches live data) and compares checksums."""
    cfg = GenConfig(seed=body.seed, scale=body.scale, anomalies=body.anomalies)
    path = os.path.join(request.app.state.settings.data_dir, "exports", "reproducibility_report.json")

    def job():
        rep = reproducibility_check(cfg)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(rep, f, indent=1, sort_keys=True)
        return rep
    if body.background:
        threading.Thread(target=lambda: job(), daemon=True).start()
        return {"status": "RUNNING", "message": "Poll GET /api/data/reproducibility"}
    return job()


@router.get("/data/reproducibility")
def repro_report(request: Request, actor: Actor = Depends(staff_only)):
    path = os.path.join(request.app.state.settings.data_dir, "exports", "reproducibility_report.json")
    if not os.path.exists(path):
        raise NotFoundError("No reproducibility report yet")
    return json.load(open(path))


@router.get("/data/export")
def export_list(request: Request, actor: Actor = Depends(reviewer_or_admin)):
    d = _export_dir(request)
    mp = os.path.join(d, "manifest.json")
    if not os.path.exists(mp):
        raise NotFoundError("No export available; generate a dataset first")
    man = json.load(open(mp))
    files = [{"name": n, "kind": n.split("/")[0] if "/" in n else "root", "sha256": h} for n, h in man["checksums"].items()]
    files += [{"name": n, "kind": "ground_truth", "sha256": h} for n, h in man["ground_truth_checksums"].items()]
    for f in files:
        f["size_bytes"] = os.path.getsize(os.path.join(d, f["name"]))
    return {"directory": "exports/current", "config": man["config"], "row_counts": man["row_counts"], "files": files,
            "notice": "Ground-truth files are for evaluation only and must never be used as model/engine input."}


@router.get("/data/export/{kind}/{name}")
def export_download(kind: str, name: str, request: Request, actor: Actor = Depends(reviewer_or_admin)):
    if kind not in ("csv", "json", "ground_truth", "root") or not _NAME.match(name):
        raise ValidationFailed("Invalid export path")
    d = _export_dir(request)
    path = os.path.join(d, name if kind == "root" else os.path.join(kind, name))
    if not os.path.realpath(path).startswith(os.path.realpath(d) + os.sep) or not os.path.isfile(path):
        raise NotFoundError("Export file not found")
    return FileResponse(path, filename=name)
