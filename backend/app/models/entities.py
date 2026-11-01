"""SQLAlchemy models. IDs are deterministic strings (see services/ids.py).
History is append-only: decisions, status history, endorsements, renewals and audit events
are new rows, never overwritten."""
from __future__ import annotations
from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey,
                        Index, Integer, Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from app.core import enums as E
from app.database.base import Base


def _in(col, values, name):
    return CheckConstraint(f"{col} IN ({', '.join(repr(v) for v in values)})", name=name)


class IdCounter(Base):
    __tablename__ = "id_counters"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


# ------------------------------------------------------------------ master data
class Product(Base):
    __tablename__ = "products"
    product_id: Mapped[str] = mapped_column(String(16), primary_key=True)          # PROD-001
    product_key: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    base_rate: Mapped[float] = mapped_column(Numeric(10, 6))
    min_insured_value: Mapped[float] = mapped_column(Numeric(14, 2))
    max_insured_value: Mapped[float] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    rules_version: Mapped[str] = mapped_column(String(24))
    __table_args__ = (_in("product_key", E.PRODUCT_KEYS, "ck_product_key"),
                      CheckConstraint("max_insured_value >= min_insured_value", name="ck_product_value_range"))


class CoverageOption(Base):
    __tablename__ = "coverage_options"
    coverage_id: Mapped[str] = mapped_column(String(16), primary_key=True)         # COV-001
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    min_limit: Mapped[float] = mapped_column(Numeric(14, 2))
    max_limit: Mapped[float] = mapped_column(Numeric(14, 2))
    rate_multiplier: Mapped[float] = mapped_column(Numeric(6, 3))
    __table_args__ = (CheckConstraint("max_limit >= min_limit", name="ck_cov_limits"),)


class ProductCoverage(Base):                       # bridge: Product N:M CoverageOption
    __tablename__ = "product_coverages"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), primary_key=True)
    coverage_id: Mapped[str] = mapped_column(ForeignKey("coverage_options.coverage_id"), primary_key=True)
    effective_from: Mapped[date] = mapped_column(Date)


class RiskFactor(Base):
    __tablename__ = "risk_factors"
    risk_factor_id: Mapped[str] = mapped_column(String(16), primary_key=True)      # RSK-001
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    input_field: Mapped[str] = mapped_column(String(40))
    weight: Mapped[float] = mapped_column(Float)
    mandatory: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (CheckConstraint("weight > 0 AND weight <= 1", name="ck_rf_weight"),)


class ApprovalAuthority(Base):
    __tablename__ = "approval_authorities"
    authority_id: Mapped[str] = mapped_column(String(24), primary_key=True)         # AUTH-MOTOR-OPERATIONS_ANALYST
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"))
    level: Mapped[str] = mapped_column(String(24))
    role: Mapped[str | None] = mapped_column(String(24))
    max_coverage: Mapped[float | None] = mapped_column(Numeric(14, 2))   # NULL = unlimited
    max_risk_category: Mapped[str] = mapped_column(String(8))


# ---------------------------------------------------------------- parties/assets
class Applicant(Base):
    __tablename__ = "applicants"
    applicant_id: Mapped[str] = mapped_column(String(24), primary_key=True)         # APP-2026-000001
    owner_key: Mapped[str | None] = mapped_column(String(64), index=True)           # demo-session isolation
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(160), index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    age: Mapped[int | None] = mapped_column(Integer)
    applicant_type: Mapped[str] = mapped_column(String(16), default="INDIVIDUAL")
    location: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    __table_args__ = (_in("applicant_type", ("INDIVIDUAL", "BUSINESS"), "ck_app_type"),
                      _in("status", ("ACTIVE", "INACTIVE"), "ck_app_status"))


class InsuredAsset(Base):
    __tablename__ = "insured_assets"
    asset_id: Mapped[str] = mapped_column(String(24), primary_key=True)             # AST-2026-000001
    applicant_id: Mapped[str] = mapped_column(ForeignKey("applicants.applicant_id"), index=True)
    asset_type: Mapped[str] = mapped_column(String(24))
    declared_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    location: Mapped[str | None] = mapped_column(String(64))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    __table_args__ = (_in("asset_type", ("VEHICLE", "PROPERTY", "COMMERCIAL_ASSET"), "ck_asset_type"),)


# ------------------------------------------------------------------- quoting
class Quote(Base):
    __tablename__ = "quotes"
    quote_id: Mapped[str] = mapped_column(String(24), primary_key=True)             # QTE-2026-000001
    applicant_id: Mapped[str] = mapped_column(ForeignKey("applicants.applicant_id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("insured_assets.asset_id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    coverage_id: Mapped[str | None] = mapped_column(ForeignKey("coverage_options.coverage_id"))
    coverage_code: Mapped[str | None] = mapped_column(String(40))
    requested_coverage: Mapped[float | None] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(24), index=True)
    eligibility_status: Mapped[str | None] = mapped_column(String(20))
    eligibility_detail: Mapped[dict | None] = mapped_column(JSON)
    risk_score: Mapped[float | None] = mapped_column(Float)
    risk_category: Mapped[str | None] = mapped_column(String(8))
    premium: Mapped[float | None] = mapped_column(Numeric(14, 2))
    premium_breakdown: Mapped[dict | None] = mapped_column(JSON)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    rules_version: Mapped[str] = mapped_column(String(24))
    valid_until: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    __table_args__ = (_in("status", E.QUOTE_STATUSES, "ck_quote_status"),)


class QuoteCoverage(Base):
    __tablename__ = "quote_coverages"
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.quote_id"), primary_key=True)
    coverage_id: Mapped[str] = mapped_column(ForeignKey("coverage_options.coverage_id"), primary_key=True)
    requested_amount: Mapped[float] = mapped_column(Numeric(14, 2))


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    assessment_id: Mapped[str] = mapped_column(String(24), primary_key=True)        # RAS-2026-000001
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.quote_id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(8))
    factors: Mapped[list] = mapped_column(JSON)
    missing_info: Mapped[list] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    rules_version: Mapped[str] = mapped_column(String(24))
    assessed_at: Mapped[datetime] = mapped_column(DateTime)
    __table_args__ = (_in("category", E.RISK_CATEGORIES, "ck_ras_cat"),)


class UnderwritingDecision(Base):                 # append-only
    __tablename__ = "underwriting_decisions"
    decision_id: Mapped[str] = mapped_column(String(24), primary_key=True)          # UWD-2026-000001
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.quote_id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(24))
    decision_type: Mapped[str] = mapped_column(String(12))                           # AUTOMATED | MANUAL
    risk_score: Mapped[float | None] = mapped_column(Float)
    reasons: Mapped[list] = mapped_column(JSON)
    rule_ids: Mapped[list] = mapped_column(JSON)
    approval_authority: Mapped[str] = mapped_column(String(24))
    decided_by: Mapped[str] = mapped_column(String(48))
    decided_role: Mapped[str] = mapped_column(String(24))
    notes: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime)
    rule_engine_version: Mapped[str] = mapped_column(String(24))
    __table_args__ = (UniqueConstraint("quote_id", "sequence", name="uq_decision_seq"),
                      _in("outcome", E.DECISION_OUTCOMES, "ck_uwd_outcome"))


class QuoteAcceptance(Base):
    __tablename__ = "quote_acceptances"
    acceptance_id: Mapped[str] = mapped_column(String(24), primary_key=True)        # ACC-2026-000001
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.quote_id"), unique=True)
    accepted_by: Mapped[str] = mapped_column(String(48))
    accepted_at: Mapped[datetime] = mapped_column(DateTime)
    terms_version: Mapped[str] = mapped_column(String(24))


# ----------------------------------------------------------------- policies
class Policy(Base):
    __tablename__ = "policies"
    policy_id: Mapped[str] = mapped_column(String(24), primary_key=True)            # POL-2026-000001
    quote_id: Mapped[str | None] = mapped_column(ForeignKey("quotes.quote_id"), unique=True)  # 1:0..1
    applicant_id: Mapped[str] = mapped_column(ForeignKey("applicants.applicant_id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("insured_assets.asset_id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    coverage_id: Mapped[str] = mapped_column(ForeignKey("coverage_options.coverage_id"))
    coverage_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    premium: Mapped[float] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(24), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date] = mapped_column(Date)
    cancelled_at: Mapped[date | None] = mapped_column(Date)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    overlap_reason: Mapped[str | None] = mapped_column(String(80))       # permitted-overlap justification
    renewal_of_policy_id: Mapped[str | None] = mapped_column(ForeignKey("policies.policy_id"))
    snapshot: Mapped[dict] = mapped_column(JSON)                          # original terms, immutable
    issued_at: Mapped[datetime] = mapped_column(DateTime)
    __table_args__ = (_in("status", E.POLICY_STATUSES, "ck_policy_status"),
                      CheckConstraint("expiry_date > start_date", name="ck_policy_dates"))


class PolicyCoverage(Base):
    __tablename__ = "policy_coverages"
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.policy_id"), primary_key=True)
    coverage_id: Mapped[str] = mapped_column(ForeignKey("coverage_options.coverage_id"), primary_key=True)
    limit_amount: Mapped[float] = mapped_column(Numeric(14, 2))


class PolicyStatusHistory(Base):
    __tablename__ = "policy_status_history"
    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.policy_id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    changed_at: Mapped[datetime] = mapped_column(DateTime)
    changed_by: Mapped[str] = mapped_column(String(48))
    reason: Mapped[str | None] = mapped_column(Text)


class Payment(Base):
    __tablename__ = "payments"
    payment_id: Mapped[str] = mapped_column(String(24), primary_key=True)           # PAY-2026-000001
    quote_id: Mapped[str | None] = mapped_column(ForeignKey("quotes.quote_id"), index=True)
    policy_id: Mapped[str | None] = mapped_column(ForeignKey("policies.policy_id"), index=True)
    renewal_id: Mapped[str | None] = mapped_column(String(48), index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(10))
    method: Mapped[str] = mapped_column(String(12), default="DEMO")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    __table_args__ = (_in("status", E.PAYMENT_STATUSES, "ck_pay_status"),
                      CheckConstraint("amount >= 0", name="ck_pay_amount"))


class Endorsement(Base):
    __tablename__ = "endorsements"
    endorsement_id: Mapped[str] = mapped_column(String(40), primary_key=True)       # END-POL-2026-000001-001
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.policy_id"), index=True)
    endorsement_type: Mapped[str] = mapped_column(String(24))
    requested_changes: Mapped[dict] = mapped_column(JSON)
    coverage_before: Mapped[float] = mapped_column(Numeric(14, 2))
    coverage_after: Mapped[float] = mapped_column(Numeric(14, 2))
    declared_value_before: Mapped[float] = mapped_column(Numeric(14, 2))
    declared_value_after: Mapped[float] = mapped_column(Numeric(14, 2))
    premium_before: Mapped[float] = mapped_column(Numeric(14, 2))
    premium_after: Mapped[float | None] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(12))
    effective_date: Mapped[date] = mapped_column(Date)
    policy_snapshot: Mapped[dict] = mapped_column(JSON)                  # policy as it was at request time
    requested_by: Mapped[str] = mapped_column(String(48))
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    decided_by: Mapped[str | None] = mapped_column(String(48))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (_in("status", E.ENDORSEMENT_STATUSES, "ck_end_status"),
                      _in("endorsement_type", E.ENDORSEMENT_TYPES, "ck_end_type"))


class Renewal(Base):
    __tablename__ = "renewals"
    renewal_id: Mapped[str] = mapped_column(String(48), primary_key=True)           # REN-POL-2026-000001-2027
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.policy_id"), index=True)
    renewal_year: Mapped[int] = mapped_column(Integer)
    new_start_date: Mapped[date] = mapped_column(Date)
    new_expiry_date: Mapped[date] = mapped_column(Date)
    coverage_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    offered_premium: Mapped[float | None] = mapped_column(Numeric(14, 2))
    premium_breakdown: Mapped[dict | None] = mapped_column(JSON)
    risk_score: Mapped[float | None] = mapped_column(Float)
    eligibility_status: Mapped[str] = mapped_column(String(20))
    reasons: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), index=True)
    new_policy_id: Mapped[str | None] = mapped_column(ForeignKey("policies.policy_id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime)
    response_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (_in("status", E.RENEWAL_STATUSES, "ck_ren_status"),
                      UniqueConstraint("policy_id", "renewal_year", name="uq_renewal_term"))


# --------------------------------------------------------------- audit / eval
class AuditEvent(Base):
    __tablename__ = "audit_events"
    audit_id: Mapped[str] = mapped_column(String(24), primary_key=True)             # AUD-2026-000001
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_id: Mapped[str] = mapped_column(String(48), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(48))
    actor_role: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)


class GroundTruth(Base):
    """Evaluation labels ONLY. Never read by decision engines or the anomaly detector."""
    __tablename__ = "ground_truth"
    gt_id: Mapped[str] = mapped_column(String(24), primary_key=True)                # GT-000001
    issue_type: Mapped[str] = mapped_column(String(48), index=True)
    ground_truth_label: Mapped[str] = mapped_column(String(48))
    expected_outcome: Mapped[str] = mapped_column(Text)
    affected_entity: Mapped[str] = mapped_column(String(24))
    affected_record_id: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(10), default="HIGH")
    record_category: Mapped[str] = mapped_column(String(12), default="ANOMALY", server_default="ANOMALY")  # ANOMALY | EDGE_CASE


# ----------------------------------------------- AI copilot run metadata (NOT part of deterministic dataset)
class AiInteraction(Base):
    """Run metadata for AI copilot calls. Excluded from dataset exports and checksums."""
    __tablename__ = "ai_interactions"
    interaction_id: Mapped[str] = mapped_column(String(24), primary_key=True)   # AIX-000001
    user_id: Mapped[str] = mapped_column(String(48))
    role: Mapped[str] = mapped_column(String(24))
    question: Mapped[str] = mapped_column(String(500))
    intent: Mapped[str] = mapped_column(String(40), index=True)
    record_refs: Mapped[list | None] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(24))               # groq | fallback-templates
    model: Mapped[str | None] = mapped_column(String(80))
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(120))
    guard_result: Mapped[dict | None] = mapped_column(JSON)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_version: Mapped[str | None] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime)


# ------------------------------------------- run metadata (NOT part of deterministic dataset)
class DatasetRun(Base):
    __tablename__ = "dataset_runs"
    run_id: Mapped[str] = mapped_column(String(16), primary_key=True)               # GEN-001
    seed: Mapped[int] = mapped_column(Integer)
    scale: Mapped[str] = mapped_column(String(12))
    anomaly_injection: Mapped[bool] = mapped_column(Boolean)
    config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12))                                 # RUNNING | COMPLETED | FAILED
    row_counts: Mapped[dict | None] = mapped_column(JSON)
    checksums: Mapped[dict | None] = mapped_column(JSON)
    reproducibility: Mapped[dict | None] = mapped_column(JSON)
    notes: Mapped[list | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    generator_version: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    triggered_by: Mapped[str] = mapped_column(String(48))


class ValidationRun(Base):
    __tablename__ = "validation_runs"
    run_id: Mapped[str] = mapped_column(String(16), primary_key=True)               # VAL-001
    triggered_by: Mapped[str] = mapped_column(String(48))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime] = mapped_column(DateTime)
    checks: Mapped[dict] = mapped_column(JSON)                                      # per-check checked/failed
    metrics: Mapped[dict] = mapped_column(JSON)
    evaluation: Mapped[dict | None] = mapped_column(JSON)                           # precision/recall vs ground truth
    finding_count: Mapped[int] = mapped_column(Integer)


class DetectedException(Base):
    __tablename__ = "detected_exceptions"
    exception_id: Mapped[str] = mapped_column(String(24), primary_key=True)         # EXC-VAL-001-00001
    run_id: Mapped[str] = mapped_column(ForeignKey("validation_runs.run_id"), index=True)
    issue_type: Mapped[str] = mapped_column(String(48), index=True)
    affected_entity: Mapped[str] = mapped_column(String(24))
    affected_record_id: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(10))
    record_date: Mapped[date | None] = mapped_column(Date)
    detected_at: Mapped[datetime] = mapped_column(DateTime)
    expected_outcome: Mapped[str] = mapped_column(Text)
    actual_outcome: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)
    resolution_status: Mapped[str] = mapped_column(String(14), default="OPEN")      # OPEN | ACKNOWLEDGED | RESOLVED
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(48))
