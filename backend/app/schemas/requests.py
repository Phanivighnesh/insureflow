"""Pydantic request bodies. Business validation stays in the workflow service/engines."""
from __future__ import annotations
from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionRequest(Base):
    role: Literal["CUSTOMER", "OPERATIONS_ANALYST", "RISK_REVIEWER", "ADMINISTRATOR"]
    display_name: Optional[str] = Field(default=None, max_length=60)
    access_code: Optional[str] = None


class ApplicantIn(Base):
    full_name: str = Field(min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, max_length=160)
    phone: Optional[str] = Field(default=None, max_length=32)
    age: Optional[int] = None
    location: Optional[str] = Field(default=None, max_length=64)
    applicant_type: Literal["INDIVIDUAL", "BUSINESS"] = "INDIVIDUAL"


class AssetIn(Base):
    declared_value: Optional[float] = None
    location: Optional[str] = Field(default=None, max_length=64)
    attributes: dict[str, Any] = Field(default_factory=dict)


class QuoteRequest(Base):
    product_key: str
    coverage_code: Optional[str] = None
    requested_coverage: Optional[float] = None
    applicant: ApplicantIn
    asset: AssetIn


class InformationUpdate(Base):
    attributes: dict[str, Any] = Field(default_factory=dict)
    declared_value: Optional[float] = None
    location: Optional[str] = None


class PaymentRequest(Base):
    outcome: Literal["SUCCESS", "FAILED", "PENDING"]
    idempotency_key: Optional[str] = Field(default=None, max_length=64)


class ResolvePayment(Base):
    outcome: Literal["SUCCESS", "FAILED"]


class EndorsementRequest(Base):
    endorsement_type: str
    new_coverage_amount: Optional[float] = None
    new_declared_value: Optional[float] = None
    changes: dict[str, Any] = Field(default_factory=dict)
    effective_date: date


class CancelRequest(Base):
    reason: str = Field(min_length=1, max_length=500)


class ReviewRequest(Base):
    notes: Optional[str] = Field(default=None, max_length=1000)


class DecideEndorsement(Base):
    reason: Optional[str] = Field(default=None, max_length=500)


class RenewalGenerate(Base):
    policy_id: str
    as_of_date: Optional[date] = None      # honoured for staff only (demo convenience)


class RenewalAccept(Base):
    payment_outcome: Literal["SUCCESS", "FAILED", "PENDING"] = "SUCCESS"


class RenewalDecline(Base):
    reason: Optional[str] = Field(default=None, max_length=500)


class ResolveException(Base):
    resolution_status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
    note: Optional[str] = Field(default=None, max_length=500)


class GenerateRequest(Base):
    seed: int = 20261022
    scale: Literal["starter", "full"] = "starter"
    anomalies: bool = True
    confirm: bool = False
    background: bool = True
