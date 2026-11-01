"""CLI:  python -m app.data_generator --seed 20261022 --scale full [--no-anomalies] [--repro-check]"""
import argparse, json, os, sys, time

from app.core.config import settings
from app.data_generator.config import DEFAULT_SEED, SCALES, GenConfig
from app.data_generator.runner import reproducibility_check, run_generation
from app.database.session import make_engine


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.data_generator")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--scale", choices=sorted(SCALES), default="starter")
    ap.add_argument("--no-anomalies", action="store_true", help="baseline only (no labelled anomaly injection)")
    ap.add_argument("--out", default=None, help="export directory (default: <data_dir>/exports/<scale>)")
    ap.add_argument("--db", default=None, help="SQLAlchemy URL (default: sqlite file inside --out)")
    ap.add_argument("--repro-check", action="store_true", help="regenerate twice in memory and compare checksums")
    a = ap.parse_args(argv)
    cfg = GenConfig(seed=a.seed, scale=a.scale, anomalies=not a.no_anomalies)
    out = a.out or os.path.join(settings.data_dir, "exports", cfg.scale)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    db = a.db or f"sqlite:///{os.path.join(out, f'insureflow_{cfg.scale}.db')}"
    if db.startswith("sqlite:///") and ":memory:" not in db and os.path.exists(db[10:]):
        os.remove(db[10:])
    res = run_generation(make_engine(db), cfg, out_dir=out, triggered_by="cli")
    print(f"[generate] {cfg.scale} seed={cfg.seed} anomalies={cfg.anomalies} in {time.time() - t0:.1f}s -> {out}")
    for k, v in res["row_counts"].items():
        print(f"  {k:26s}{v:>9,}")
    ev = res["report"].get("evaluation")
    print("[validation]", json.dumps({"exceptions": res["report"]["metrics"]["exception_total"],
                                      "precision": ev and ev["precision"], "recall": ev and ev["recall"]}))
    if res["notes"]:
        print("[notes]", res["notes"])
    if a.repro_check:
        rep = reproducibility_check(cfg)
        with open(os.path.join(out, "reproducibility_report.json"), "w") as f:
            json.dump(rep, f, indent=1, sort_keys=True)
        print(f"[reproducibility] identical={rep['identical']} files_compared={rep['files_compared']} mismatches={rep['mismatches'][:5]}")
        return 0 if rep["identical"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
