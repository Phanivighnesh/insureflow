"""Orchestrates a full generation run: reset -> seed -> baseline -> (optional) anomalies -> ground truth ->
validation -> export. Same code path for CLI, API and tests."""
from __future__ import annotations
import json, os, platform, shutil, sys, tempfile
from datetime import datetime

import sqlalchemy
from sqlalchemy import delete, func, select

from app.core import rules_config as R
from app.data_generator import anomalies
from app.data_generator.config import GENERATOR_VERSION, GenConfig
from app.data_generator.export import export_dataset, sha256
from app.data_generator.pipeline import Generator
from app.database.base import Base
from app.database.session import init_db, make_engine, make_session_factory
from app.engines.validation_engine import NON_DATASET, dataset_tables
from app.models import DatasetRun, GroundTruth, Policy
from app.services import evaluation, ids
from app.services import workflow as W
from app.services.seed import seed_master_data


def reset_dataset(session):
    """Destructive: removes all dataset rows (run-metadata tables are kept)."""
    keep = NON_DATASET - {"ground_truth"}
    for t in reversed(Base.metadata.sorted_tables):
        if t.name not in keep:
            session.execute(delete(t))
    session.flush()


def generate_into(session, cfg: GenConfig) -> Generator:
    v = cfg.volumes
    n_ren_base = v["renewals"] - cfg.n_core
    n_accept = round(0.45 * n_ren_base)
    n_policy_quote = v["policies"] - n_accept - cfg.n_core
    reset_dataset(session)
    seed_master_data(session)
    g = Generator(session, cfg)
    g.submit_quotes(); g.provide_info(); g.review_referrals()
    g.issue_policies(n_policy_quote)
    g.lifecycle()
    accepted = g.renewals(n_ren_base, n_accept)
    g.topup_policies(n_accept - accepted)
    g.maintenance()
    if cfg.anomalies:
        anomalies.inject(g)
    shortfall = v["policies"] - session.scalar(select(func.count()).select_from(Policy))
    g.topup_policies(shortfall)
    g.maintenance()
    for lab in g.labels:                                     # ground truth persisted LAST, separately from data
        session.add(GroundTruth(gt_id=ids.gt_id(session), issue_type=lab["issue_type"],
                                ground_truth_label=f"{lab['record_category']}:{lab['issue_type']}",
                                expected_outcome=lab["expected_outcome"], affected_entity=lab["affected_entity"],
                                affected_record_id=lab["affected_record_id"], severity=lab["severity"],
                                record_category=lab["record_category"]))
    session.commit()
    return g


def _software():
    return {"python": platform.python_version(), "sqlalchemy": sqlalchemy.__version__, "platform": platform.system(),
            "generator_version": GENERATOR_VERSION, "rules_version": R.RULES_VERSION,
            "premium_formula_version": R.PREMIUM_FORMULA_VERSION, "underwriting_engine_version": R.UW_ENGINE_VERSION}


def run_generation(engine, cfg: GenConfig, out_dir: str | None = None, triggered_by="cli",
                   persist_run=True, run_id: str | None = None) -> dict:
    Sf = make_session_factory(engine)
    init_db(engine)
    started = W.utcnow()
    if persist_run:
        with Sf() as s:
            run_id = run_id or f"GEN-{s.scalar(select(func.count()).select_from(DatasetRun)) + 1:03d}"
            if s.get(DatasetRun, run_id) is None:                       # API pre-creates the row for background runs
                s.add(DatasetRun(run_id=run_id, seed=cfg.seed, scale=cfg.scale, anomaly_injection=cfg.anomalies,
                                 config=cfg.as_dict(), status="RUNNING", generator_version=GENERATOR_VERSION,
                                 started_at=started, triggered_by=triggered_by))
            s.commit()
    try:
        with Sf() as s:
            g = generate_into(s, cfg)
            vrun = evaluation.run_and_persist_validation(s, triggered_by) if persist_run else None
            if vrun is None:                                # non-persisting (reproducibility) path: compute only
                from app.engines.validation_engine import run_validation
                rep = run_validation(s)
                report = {"checks": rep.checks, "metrics": evaluation.business_metrics(s, rep),
                          "evaluation": evaluation.evaluate_against_ground_truth(s, rep.findings)}
            else:
                report = {"checks": vrun.checks, "metrics": vrun.metrics, "evaluation": vrun.evaluation}
            s.commit()
            exp = None
            if out_dir:
                exp = export_dataset(s, out_dir)
                vp = os.path.join(out_dir, "validation_report.json")      # deterministic: no timestamps
                with open(vp, "w") as f:
                    json.dump(report, f, sort_keys=True, indent=1, default=str)
                exp["files"]["validation_report.json"] = sha256(vp)
                manifest = {"config": cfg.as_dict(), "row_counts": exp["row_counts"], "checksums": exp["files"],
                            "ground_truth_checksums": exp["ground_truth_files"],
                            "source": "100% synthetic; no real customer data; no external datasets used",
                            "notes": g.notes}
                with open(os.path.join(out_dir, "manifest.json"), "w") as f:
                    json.dump(manifest, f, sort_keys=True, indent=1)
                with open(os.path.join(out_dir, "run_metadata.json"), "w") as f:     # NON-deterministic run metadata
                    json.dump({"generated_at": started.isoformat(), "finished_at": W.utcnow().isoformat(),
                               "software": _software(), "triggered_by": triggered_by}, f, indent=1)
            counts = evaluation.row_counts(s)
        if persist_run:
            with Sf() as s:
                run = s.get(DatasetRun, run_id)
                run.status, run.finished_at, run.row_counts = "COMPLETED", W.utcnow(), counts
                run.checksums = (exp or {}).get("files"); run.notes = g.notes
                s.commit()
        return {"run_id": run_id, "row_counts": counts, "checksums": (exp or {}).get("files"),
                "ground_truth_checksums": (exp or {}).get("ground_truth_files"), "notes": g.notes, "report": report}
    except Exception as e:
        if persist_run:
            with Sf() as s:
                run = s.get(DatasetRun, run_id)
                if run:
                    run.status, run.error, run.finished_at = "FAILED", repr(e)[:1000], W.utcnow()
                    s.commit()
        raise


def reproducibility_check(cfg: GenConfig, runs: int = 2) -> dict:
    """Regenerate `runs` times from scratch (fresh in-memory DBs) and compare row counts + checksums."""
    results, tmp = [], tempfile.mkdtemp(prefix="insureflow_repro_")
    try:
        for i in range(runs):
            eng = make_engine("sqlite:///:memory:")
            out = os.path.join(tmp, f"run{i + 1}")
            res = run_generation(eng, cfg, out_dir=out, persist_run=False)
            results.append(res)
            eng.dispose()
        base = results[0]
        all_files = {**base["checksums"], **{f"[ground_truth] {k}": v for k, v in base["ground_truth_checksums"].items()}}
        mismatches = []
        for i, r in enumerate(results[1:], 2):
            other = {**r["checksums"], **{f"[ground_truth] {k}": v for k, v in r["ground_truth_checksums"].items()}}
            mismatches += [f"run{i}: {k}" for k in set(all_files) | set(other) if all_files.get(k) != other.get(k)]
            if r["row_counts"] != base["row_counts"]:
                mismatches.append(f"run{i}: row counts differ")
        return {"identical": not mismatches, "runs": runs, "config": cfg.as_dict(), "row_counts": base["row_counts"],
                "files_compared": len(all_files), "checksums_run1": dict(sorted(all_files.items())),
                "mismatches": sorted(mismatches), "verified_at": W.utcnow().isoformat(), "software": _software()}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
