"""Generation configuration. Starter and full share the same generator; only volumes differ."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

GENERATOR_VERSION = "1.0.0"
AS_OF = date(2026, 10, 22)            # fixed "today" of the synthetic world (never the wall clock)
DEFAULT_SEED = 20261022

SCALES = {
    "full": dict(applicants=3000, quotes=4000, policies=2000, renewals=1200, anomaly_each=20, anomaly_extra=10),
    "starter": dict(applicants=150, quotes=200, policies=100, renewals=60, anomaly_each=3, anomaly_extra=2),
}
ANOMALY_TYPES_CORE = ["POLICY_WITHOUT_ACCEPTANCE", "PREMIUM_FORMULA_MISMATCH", "ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT",
                      "RENEWAL_FOR_CANCELLED_POLICY", "UNAUTHORIZED_POLICY_OVERLAP"]
ANOMALY_TYPES_EXTRA = ["INVALID_FOREIGN_KEY", "DUPLICATE_TRANSACTION", "INVALID_DATE_SEQUENCE"]


@dataclass(frozen=True)
class GenConfig:
    seed: int = DEFAULT_SEED
    scale: str = "starter"
    anomalies: bool = True

    @property
    def volumes(self) -> dict:
        return SCALES[self.scale]

    @property
    def n_core(self) -> int:
        return self.volumes["anomaly_each"] if self.anomalies else 0

    @property
    def n_extra(self) -> int:
        return self.volumes["anomaly_extra"] if self.anomalies else 0

    def as_dict(self) -> dict:
        return {"seed": self.seed, "scale": self.scale, "anomalies": self.anomalies, "as_of": AS_OF.isoformat(),
                "volumes": self.volumes, "generator_version": GENERATOR_VERSION}
