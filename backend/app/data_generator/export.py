"""Deterministic exports: CSV (+JSON for small tables) + SQL seed + checksums. Row order = primary key;
column order = model order; no timestamps inside checksummed files."""
from __future__ import annotations
import csv, hashlib, json, os
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.engines.validation_engine import dataset_tables
from app.models import GroundTruth

JSON_MAX_ROWS = 5000


def fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, separators=(",", ":"))
    return str(v)


def native(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sql_lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float, Decimal)):
        return format(v, "f") if isinstance(v, Decimal) else repr(v)
    return "'" + fmt(v).replace("'", "''") + "'"


def _rows(session, t):
    pk = list(t.primary_key.columns)
    return [dict(r._mapping) for r in session.execute(select(t).order_by(*pk))]


def write_table_files(session, t, out_dir, files):
    cols = [c.name for c in t.columns]
    rows = _rows(session, t)
    p = os.path.join(out_dir, "csv", f"{t.name}.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([fmt(r[c]) for c in cols])
    files[f"csv/{t.name}.csv"] = sha256(p)
    return cols, rows


def export_dataset(session, out_dir: str) -> dict:
    for sub in ("csv", "json", "ground_truth"):
        os.makedirs(os.path.join(out_dir, sub), exist_ok=True)
    files, counts, sql = {}, {}, ["-- InsureFlow synthetic seed data (no real customer information)",
                                  "-- SQLite: FK enforcement must be OFF to load labelled INVALID_FOREIGN_KEY anomaly rows.",
                                  "PRAGMA foreign_keys=OFF;"]
    for t in dataset_tables():
        cols, rows = write_table_files(session, t, out_dir, files)
        counts[t.name] = len(rows)
        if len(rows) <= JSON_MAX_ROWS:
            p = os.path.join(out_dir, "json", f"{t.name}.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump([{c: native(r[c]) for c in cols} for r in rows], f, sort_keys=True, indent=1)
            files[f"json/{t.name}.json"] = sha256(p)
        for r in rows:
            sql.append(f"INSERT INTO {t.name} ({', '.join(cols)}) VALUES ({', '.join(sql_lit(r[c]) for c in cols)});")
    p = os.path.join(out_dir, "seed_data.sql")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sql) + "\n")
    files["seed_data.sql"] = sha256(p)

    gt_files = {}                                           # ground truth: SEPARATE directory + checksums
    gt = [dict(r._mapping) for r in session.execute(select(GroundTruth.__table__).order_by(GroundTruth.__table__.c.gt_id))]
    gcols = [c.name for c in GroundTruth.__table__.columns]
    p = os.path.join(out_dir, "ground_truth", "ground_truth.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(gcols)
        for r in gt:
            w.writerow([fmt(r[c]) for c in gcols])
    gt_files["ground_truth/ground_truth.csv"] = sha256(p)
    p = os.path.join(out_dir, "ground_truth", "ground_truth.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(gt, f, sort_keys=True, indent=1)
    gt_files["ground_truth/ground_truth.json"] = sha256(p)
    return {"files": files, "ground_truth_files": gt_files, "row_counts": counts, "ground_truth_rows": len(gt)}
