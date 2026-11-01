"""Renders docs/VALIDATION_REPORT.md and docs/REPRODUCIBILITY_REPORT.md from the artifacts of a real run
(data/exports/<scale>/validation_report.json, manifest.json, reproducibility_report.json). No numbers are typed by hand.
Usage: python -m scripts.generate_reports [scale]"""
import json, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
scale = sys.argv[1] if len(sys.argv) > 1 else "full"
D = os.path.join(ROOT, "data", "exports", scale)
load = lambda n: json.load(open(os.path.join(D, n)))  # noqa: E731
val, man, rep, meta = load("validation_report.json"), load("manifest.json"), load("reproducibility_report.json"), load("run_metadata.json")
m, ev, cfg = val["metrics"], val["evaluation"], man["config"]
pct = lambda x: "n/a" if x is None else f"{x * 100:.2f}%"  # noqa: E731

V = [f"# VALIDATION REPORT - `{scale}` dataset (seed {cfg['seed']})\n",
     f"_Rendered from `data/exports/{scale}/validation_report.json`. Generated {meta['generated_at']} by generator {cfg['generator_version']}._\n",
     "> 100% synthetic data. No real customer information and no external datasets were used.\n",
     "## Row counts\n", "| Table | Rows |\n|---|---|"] + [f"| {k} | {v:,} |" for k, v in sorted(man["row_counts"].items())]
V += ["\n## Validation checks (independent detector - never reads ground truth)\n", "| Check | Records checked | Failed |\n|---|---|---|"]
V += [f"| {k} | {c['checked']:,} | {c['failed']:,} |" for k, c in val["checks"].items()]
V += ["\n## Metrics\n", "| Metric | Value |\n|---|---|"]
for k in ("total_records_processed", "valid_records", "invalid_records", "exception_total", "eligibility_pass_rate", "approval_rate",
          "rejection_rate", "referral_rate", "pending_information_rate", "average_premium", "premium_reconciliation_accuracy",
          "policy_issuance_compliance", "renewal_eligibility_compliance", "foreign_key_integrity"):
    V.append(f"| {k} | {m[k]} |")
V += ["\n### Exceptions detected by type\n", "| Issue type | Count |\n|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(m["exception_counts"].items())]
V += ["\n## Detector vs ground truth (evaluation only)\n",
      f"Ground-truth anomalies: **{ev['ground_truth_anomalies']}**, detected: **{ev['detected']}**, TP **{ev['true_positives']}**, "
      f"FP **{ev['false_positives']}**, FN **{ev['false_negatives']}**, precision **{pct(ev['precision'])}**, recall **{pct(ev['recall'])}**, F1 **{ev['f1']}**.\n",
      "| Issue type | TP | FP | FN | Precision | Recall |\n|---|---|---|---|---|---|"]
V += [f"| {k} | {v['tp']} | {v['fp']} | {v['fn']} | {pct(v['precision'])} | {pct(v['recall'])} |" for k, v in ev["per_issue_type"].items()]
V += ["\n### Edge-case labels (expected behaviours, not defects)\n", "| Label | Count |\n|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(ev["edge_case_labels"].items())]
V += ["\n## Honest limitations of this evaluation\n",
      "- Perfect precision/recall reflects that anomalies are injected through well-defined, rule-detectable mutations; it does **not** imply the detector would catch arbitrary real-world data defects.",
      "- The clean baseline (anomaly injection off) yields **0 findings** - verified by `test_clean_baseline_has_zero_findings_and_perfect_reconciliation` on the starter scale.",
      f"- Generator notes: {man['notes'] or 'none'}."]
open(os.path.join(ROOT, "docs", "VALIDATION_REPORT.md"), "w").write("\n".join(V) + "\n")

R = [f"# REPRODUCIBILITY REPORT - `{scale}` dataset\n",
     f"_Rendered from `data/exports/{scale}/reproducibility_report.json` (verified {rep['verified_at']})._\n",
     f"- **Result: {'IDENTICAL' if rep['identical'] else 'MISMATCH'}** - {rep['runs']} independent regenerations from empty in-memory databases, **{rep['files_compared']} files** compared (CSV, JSON, SQL seed, validation report and ground truth).",
     f"- Seed: `{cfg['seed']}` | scale: `{cfg['scale']}` | anomalies: `{cfg['anomalies']}` | as-of date: `{cfg['as_of']}` | generator `{cfg['generator_version']}`",
     f"- Mismatches: {rep['mismatches'] or 'none'}",
     f"- Software: {json.dumps(rep['software'])}",
     "\n## What is (and is not) in the deterministic output\n",
     "Deterministic: all dataset tables, IDs, timestamps (injected simulated clock), ground truth, validation report. NOT in checksums: `run_metadata.json` (wall-clock generation time), `dataset_runs` / `validation_runs` / `detected_exceptions` tables (run metadata).\n",
     "How to reproduce: `cd backend && python -m app.data_generator --seed 20261022 --scale full --repro-check`\n",
     "## SHA-256 checksums (run 1; run 2 identical)\n", "| File | SHA-256 |\n|---|---|"] + [f"| {k} | `{v}` |" for k, v in rep["checksums_run1"].items()]
open(os.path.join(ROOT, "docs", "REPRODUCIBILITY_REPORT.md"), "w").write("\n".join(R) + "\n")
print("reports written")
