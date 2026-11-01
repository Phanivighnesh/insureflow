"""Field-level data dictionary generated from the SQLAlchemy models (no drift).
Usage: python -m scripts.generate_data_dictionary > ../docs/DATA_DICTIONARY.md"""
import re
from sqlalchemy import CheckConstraint

import app.models  # noqa: F401
from app.database.base import Base

ID_FORMAT = {"applicants.applicant_id": "APP-2026-000001", "insured_assets.asset_id": "AST-2026-000001",
             "products.product_id": "PROD-001", "coverage_options.coverage_id": "COV-001",
             "risk_factors.risk_factor_id": "RSK-001", "quotes.quote_id": "QTE-2026-000001",
             "policies.policy_id": "POL-2026-000001", "endorsements.endorsement_id": "END-<policy-id>-001",
             "renewals.renewal_id": "REN-<policy-id>-2027", "underwriting_decisions.decision_id": "UWD-2026-000001",
             "risk_assessments.assessment_id": "RAS-2026-000001", "quote_acceptances.acceptance_id": "ACC-2026-000001",
             "payments.payment_id": "PAY-2026-000001", "audit_events.audit_id": "AUD-2026-000001",
             "ground_truth.gt_id": "GT-000001", "dataset_runs.run_id": "GEN-001", "validation_runs.run_id": "VAL-001",
             "detected_exceptions.exception_id": "EXC-VAL-001-00001"}
L = ["# DATA DICTIONARY (generated from `backend/app/models/entities.py`)\n",
     "Regenerate: `cd backend && python -m scripts.generate_data_dictionary > ../docs/DATA_DICTIONARY.md`\n",
     "Units: monetary columns are `USD` with 2 decimals; dates ISO-8601; timestamps naive UTC. "
     "`Allowed values` come from DB CHECK constraints; deeper validation rules are in `docs/BUSINESS_RULES.md`.\n"]
for t in Base.metadata.sorted_tables:
    checks = {}
    for c in t.constraints:
        if isinstance(c, CheckConstraint):
            m = re.match(r"(\w+) IN \((.*)\)", str(c.sqltext))
            if m:
                checks[m.group(1)] = m.group(2).replace("'", "")
            else:
                checks.setdefault("__rules__", []).append(str(c.sqltext))
    uniq = {col.name for col in t.columns if col.unique} | {c.name for u in t.constraints if u.__class__.__name__ == "UniqueConstraint" for c in u.columns}
    L.append(f"\n## `{t.name}`\n")
    L.append("| Column | Type | Required | Key | Allowed values / validation | Format / notes |\n|---|---|---|---|---|---|")
    for col in t.columns:
        key = "PK" if col.primary_key else ""
        fks = [f"FK -> {fk.column.table.name}.{fk.column.name}" for fk in col.foreign_keys]
        key = ", ".join(x for x in [key] + fks + (["UNIQUE"] if col.name in uniq and not col.primary_key else []) if x)
        allowed = checks.get(col.name, "")
        L.append(f"| {col.name} | {col.type} | {'no' if col.nullable and not col.primary_key else 'yes'} | {key} | {allowed} | {ID_FORMAT.get(f'{t.name}.{col.name}', '')} |")
    for r in checks.get("__rules__", []):
        L.append(f"\n- Table rule: `{r}`")
print("\n".join(L))
