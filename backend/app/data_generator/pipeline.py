"""Baseline (valid) dataset generation. Every record is produced through services.workflow so all
derived values (risk, premium, decisions, dates, statuses) come from the deterministic engines.
Anomaly injection is a SEPARATE stage (anomalies.py)."""
from __future__ import annotations
import random
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core import rules_config as R
from app.core.errors import ConflictError
from app.core.security import Actor
from app.data_generator import profiles as P
from app.data_generator.config import AS_OF, GenConfig
from app.engines.underwriting_engine import coverage_authority
from app.models import Endorsement, Policy, Quote, Renewal, RiskAssessment
from app.services import ids
from app.services import workflow as W

ROLE_FOR_AUTH = {"AUTOMATED": "OPERATIONS_ANALYST", "OPERATIONS_ANALYST": "OPERATIONS_ANALYST",
                 "RISK_REVIEWER": "RISK_REVIEWER", "SENIOR_UNDERWRITER": "ADMINISTRATOR"}
STAFF_POOL = {"OPERATIONS_ANALYST": [Actor(f"analyst-{i:02d}", "OPERATIONS_ANALYST") for i in range(1, 5)],
              "RISK_REVIEWER": [Actor(f"reviewer-{i:02d}", "RISK_REVIEWER") for i in range(1, 4)],
              "ADMINISTRATOR": [Actor("admin-01", "ADMINISTRATOR")]}
EARLY_START, EARLY_END = date(2025, 1, 2), date(2025, 12, 1)
LATE_END = date(2026, 10, 18)
CANCEL_REASONS = ["Customer request - asset sold", "Customer request - switched insurer", "Non-disclosure identified",
                  "Customer request - no longer required"]
INFO_CHANGES = ["Phone number updated", "Mailing address updated", "Contact email updated"]


class Generator:
    def __init__(self, session, cfg: GenConfig):
        self.s, self.cfg = session, cfg
        self.v = cfg.volumes
        self._rngs: dict[str, random.Random] = {}
        self.labels: list[dict] = []            # ground-truth rows (edge cases + anomalies)
        self.notes: list[str] = []
        self.qt: dict[str, datetime] = {}       # last event time per quote
        self.cust: dict[str, Actor] = {}        # applicant_id -> customer actor
        self.specs: dict[str, dict] = {}        # quote_id -> generation spec (generator-side knowledge only)

    # ------------------------------------------------------------------ utils
    def rng(self, name) -> random.Random:
        if name not in self._rngs:
            self._rngs[name] = random.Random(f"{self.cfg.seed}:{name}")
        return self._rngs[name]

    def staff(self, authority, rng) -> Actor:
        return rng.choice(STAFF_POOL[ROLE_FOR_AUTH[authority]])

    @staticmethod
    def bump(dt: datetime, rng, lo=0, hi=3) -> datetime:
        return dt + timedelta(days=rng.randint(lo, hi), minutes=rng.randint(10, 300))

    @staticmethod
    def day(d: date, rng) -> datetime:
        return datetime.combine(d, time(rng.randint(8, 17), rng.randint(0, 59), rng.randint(0, 59)))

    @staticmethod
    def live(dt: datetime) -> bool:
        return dt.date() <= AS_OF

    def label(self, issue_type, entity, rid, expected, category="EDGE_CASE", severity="MEDIUM"):
        self.labels.append({"issue_type": issue_type, "affected_entity": entity, "affected_record_id": rid,
                            "expected_outcome": expected, "record_category": category, "severity": severity})

    # ------------------------------------------------------- stages A+B: quotes
    def submit_quotes(self):
        r = self.rng("plan")
        n_app, n_q = self.v["applicants"], self.v["quotes"] - self.cfg.n_core   # overlap anomalies add n_core quotes
        prods = ["MOTOR", "PROPERTY", "COMMERCIAL"]
        primary = [P.pick(r, prods, [.45, .30, .25]) for _ in range(n_app)]
        apps = [P.sample_applicant(i + 1, r, primary[i]) for i in range(n_app)]
        owners = list(range(n_app)) + [r.randrange(n_app) for _ in range(n_q - n_app)]
        plan = []
        for k, ai in enumerate(owners):
            prod = primary[ai] if (k < n_app or r.random() < 0.75) else r.choice(prods)
            early = r.random() < 0.70
            lo, hi = (EARLY_START, EARLY_END) if early else (EARLY_END + timedelta(days=1), LATE_END)
            d = lo + timedelta(days=r.randrange((hi - lo).days + 1))
            plan.append({"ai": ai, "product": prod, "date": d, "early": early})
        # an applicant's first quote must carry their profile; chronological order for ID realism
        plan.sort(key=lambda p: (p["date"], p["ai"]))
        for p in plan:
            ap = dict(apps[p["ai"]])
            if p["product"] == "COMMERCIAL" and ap["applicant_type"] != "BUSINESS":
                ap["applicant_type"] = "BUSINESS"
            payload, fix = P.sample_quote_payload(r, p["product"], ap)
            actor = Actor(f"cust-{p['ai'] + 1:05d}", "CUSTOMER", f"gen-{p['ai'] + 1:05d}")
            now = self.day(p["date"], r)
            q = W.submit_application(self.s, payload, actor, now)
            self.cust[q.applicant_id] = actor
            self.qt[q.quote_id] = now
            self.specs[q.quote_id] = {"fix": fix, "early": p["early"], "date": p["date"], "payload": payload}
            ras = self.s.scalars(select(RiskAssessment).where(RiskAssessment.quote_id == q.quote_id)).first()
            if q.eligibility_status == "NEEDS_INFORMATION" or (ras and ras.missing_info):
                self.label("MISSING_RISK_INFORMATION", "Quote", q.quote_id,
                           "Missing risk data is penalised (never zero risk); mandatory gaps -> PENDING_INFORMATION")
            if q.status == "REFERRED" and q.risk_category == "HIGH":
                self.label("HIGH_RISK_REFERRAL", "Quote", q.quote_id,
                           "HIGH risk quotes are never auto-approved; referred to senior underwriting authority")
            if len(self.specs) % 400 == 0:
                self.s.commit()
        self.s.commit()

    # ------------------------------------------------------ stage C: info/review
    def _quotes(self, *statuses):
        return self.s.scalars(select(Quote).where(Quote.status.in_(statuses)).order_by(Quote.quote_id)).all()

    def provide_info(self):
        r = self.rng("info")
        for q in self._quotes("PENDING_INFORMATION"):
            fix = self.specs[q.quote_id]["fix"]
            if not fix or r.random() > 0.55:
                continue
            now = self.bump(self.qt[q.quote_id], r, 1, 6)
            if not self.live(now):
                continue
            W.provide_information(self.s, q.quote_id, {"attributes": fix}, self.cust[q.applicant_id], now)
            self.qt[q.quote_id] = now
        self.s.commit()

    def review_referrals(self):
        r = self.rng("review")
        for q in self._quotes("REFERRED"):
            cur = W.current_decision(self.s, q.quote_id)
            if self.qt[q.quote_id].date() > AS_OF - timedelta(days=7) or r.random() < 0.03:
                continue                                     # recent / backlog stays pending
            now = self.bump(self.qt[q.quote_id], r, 1, 5)
            if not self.live(now):
                continue
            x = r.random()
            action = "APPROVE" if x < 0.78 else ("REJECT" if x < 0.92 else "REQUEST_INFORMATION")
            W.review_quote(self.s, q.quote_id, action, self.staff(cur.approval_authority, r),
                           "Reviewed against underwriting guidelines", now)
            self.qt[q.quote_id] = now
        self.s.commit()

    # ------------------------------------------------- stage D: accept/pay/issue
    def _accept_and_pay(self, q: Quote, r, pattern: str):
        actor = self.cust[q.applicant_id]
        now = self.bump(self.qt[q.quote_id], r, 0, 5)
        W.accept_quote(self.s, q.quote_id, actor, now)
        self.qt[q.quote_id] = now
        if pattern == "FAILED_THEN_SUCCESS":
            now = self.bump(now, r, 0, 2)
            W.demo_payment(self.s, q.quote_id, "FAILED", actor, None, now)
        if pattern == "PENDING_THEN_SUCCESS":
            now = self.bump(now, r, 0, 2)
            pay, _, _ = W.demo_payment(self.s, q.quote_id, "PENDING", actor, None, now)
            now = self.bump(now, r, 1, 2)
            _, pol = W.resolve_pending_payment(self.s, pay.payment_id, "SUCCESS", actor, now)
            return pol
        now = self.bump(now, r, 0, 3)
        _, pol, _ = W.demo_payment(self.s, q.quote_id, "SUCCESS", actor, f"gen-{q.quote_id}", now)
        self.qt[q.quote_id] = now
        return pol

    def _issue(self, quotes: list[Quote], r):
        n = 0
        for q in quotes:
            pat = r.choices(["DIRECT", "FAILED_THEN_SUCCESS", "PENDING_THEN_SUCCESS"], [.88, .08, .04])[0]
            if self._accept_and_pay(q, r, pat):
                n += 1
        self.s.commit()
        return n

    def issue_policies(self, count: int):
        r = self.rng("issue")
        cands = [q for q in self._quotes("APPROVED") if self.specs[q.quote_id]["early"]]
        if len(cands) < count:
            raise RuntimeError(f"Only {len(cands)} approvable early quotes for {count} policies; tune distributions")
        r.shuffle(cands)
        chosen, self._reserve = cands[:count], cands[count:]
        chosen.sort(key=lambda q: (self.qt[q.quote_id], q.quote_id))
        self._issue(chosen, r)
        self._partial_acceptance(r)

    def topup_policies(self, shortfall: int):
        if shortfall <= 0:
            return
        r = self.rng("topup")
        pool = [q for q in self._reserve if q.status == "APPROVED"]
        if len(pool) < shortfall:
            self.notes.append(f"policy top-up short by {shortfall - len(pool)}")
        self._issue(pool[:shortfall], r)
        self._reserve = pool[shortfall:]

    def _partial_acceptance(self, r):
        """Approved-but-not-issued quotes: never accepted / accepted unpaid / payment failed.
        The first 60 reserve quotes are left untouched so a policy top-up remains possible."""
        protected = {q.quote_id for q in self._reserve[:60]}
        for q in self._quotes("APPROVED"):
            if q.quote_id in protected or r.random() < 0.45:
                continue
            now = self.bump(self.qt[q.quote_id], r, 1, 8)
            if not self.live(now):
                continue
            actor = self.cust[q.applicant_id]
            W.accept_quote(self.s, q.quote_id, actor, now)
            self.qt[q.quote_id] = now
            if r.random() < 0.55:
                W.demo_payment(self.s, q.quote_id, "FAILED", actor, None, self.bump(now, r, 0, 2))
        self.s.commit()
        self._reserve = [q for q in self._reserve if q.status == "APPROVED"]

    # ------------------------------------------- stage E: lifecycle on policies
    def policies(self, **flt):
        stmt = select(Policy).order_by(Policy.policy_id)
        return [p for p in self.s.scalars(stmt) if all(getattr(p, k) == v for k, v in flt.items())]

    def lifecycle(self):
        r = self.rng("lifecycle")
        pols = [p for p in self.policies(status="ACTIVE") if p.quote_id]
        r.shuffle(pols)
        n_cancel, n_end = int(len(pols) * 0.05), int(len(pols) * 0.12)
        cancel, endorse = pols[:n_cancel], pols[n_cancel:n_cancel + n_end]
        for p in cancel:
            d = min(p.start_date + timedelta(days=r.randint(15, 280)), AS_OF - timedelta(days=1))
            if d <= p.start_date:
                continue
            W.cancel_policy(self.s, p.policy_id, r.choice(CANCEL_REASONS), self.cust[p.applicant_id],
                            self.day(d, r), effective=d)
            self.label("CANCELLED_POLICY", "Policy", p.policy_id, "Policy status CANCELLED; no valid renewal may exist")
        for p in endorse:
            self._endorse(p, r)
        self.s.commit()

    def _endorse(self, p: Policy, r):
        pk = p.snapshot["product_key"]
        cov, dv = float(p.coverage_amount), p.snapshot["asset"]["declared_value"]
        d = min(p.start_date + timedelta(days=r.randint(10, 240)), AS_OF - timedelta(days=1))
        now = self.day(d, r)
        base = 100 if pk == "MOTOR" else 1000
        kind = r.choices(["COVERAGE_ADJUSTMENT", "DECLARED_VALUE_CHANGE", "ASSET_MODIFICATION", "INSURED_INFO_CHANGE"],
                         [.40, .25, .20, .15])[0]
        change = {"endorsement_type": kind, "changes": {}}
        cov_opt = R.COVERAGE_BY_CODE[p.snapshot["coverage_code"]]
        if kind == "COVERAGE_ADJUSTMENT":
            new = round(cov * r.uniform(0.85, 1.15) / base) * base
            if r.random() < 0.12:                                   # legitimate request that breaches the limit
                new = int(cov_opt["max_limit"] * 1.2)
            change["new_coverage_amount"] = new
            change["new_declared_value"] = max(dv, round(new * 1.05))
        elif kind in ("DECLARED_VALUE_CHANGE", "ASSET_MODIFICATION"):
            change["new_declared_value"] = max(cov, round(dv * r.uniform(0.9, 1.2) / base) * base)
            if kind == "ASSET_MODIFICATION":
                change["changes"] = {"modification": "Asset upgraded / modified mid-term"}
        else:
            change["changes"] = {"note": r.choice(INFO_CHANGES)}
        e = W.request_endorsement(self.s, p.policy_id, change, d, self.cust[p.applicant_id], now)
        if e.status == "PENDING":
            x = r.random()
            if x < 0.80:
                auth = coverage_authority(pk, float(e.coverage_after))
                W.decide_endorsement(self.s, e.endorsement_id, True, self.staff(auth, r), "Approved", self.bump(now, r, 1, 3))
                if kind in ("DECLARED_VALUE_CHANGE", "ASSET_MODIFICATION"):
                    self.label("MID_TERM_ASSET_CHANGE", "Endorsement", e.endorsement_id,
                               "Approved mid-term asset change; policy snapshot preserved, effective terms updated")
            elif x < 0.92:
                W.decide_endorsement(self.s, e.endorsement_id, False, self.staff("OPERATIONS_ANALYST", r), "Not justified",
                                     self.bump(now, r, 1, 3))

    # ------------------------------------------------------- stage F: renewals
    def renewals(self, n_baseline: int, n_accept: int) -> int:
        r = self.rng("renewals")
        horizon = AS_OF + timedelta(days=55)
        pool = [p for p in self.policies(status="ACTIVE") if p.quote_id and p.expiry_date <= horizon]
        r.shuffle(pool)
        plan = []
        for p in pool:
            gen = min(AS_OF - timedelta(days=r.randint(0, 5)), p.expiry_date - timedelta(days=r.randint(5, 55)))
            plan.append((gen, p.policy_id, p.applicant_id))
        made, offered = [], []
        cand = sorted(plan[:int(n_baseline * 1.15) + 5])               # extra headroom for conflicts
        for gen, pid, aid in cand:
            if len(made) >= n_baseline:
                break
            try:
                ren = W.generate_renewal(self.s, pid, self.cust[aid], gen, self.day(gen, r))
            except ConflictError:
                continue
            made.append(ren)
            if ren.status == "OFFERED":
                offered.append(ren)
        if len(made) < n_baseline:
            self.notes.append(f"renewals short by {n_baseline - len(made)}")
        r.shuffle(offered)
        accepted = 0
        for i, ren in enumerate(offered):
            pol = self.s.get(Policy, ren.policy_id)
            actor = self.cust[pol.applicant_id]
            resp = self.bump(ren.generated_at, r, 1, 12)
            resp = min(resp, datetime.combine(min(pol.expiry_date, AS_OF), time(17, 0)))
            if resp <= ren.generated_at:
                continue
            if accepted < n_accept:
                _, new = W.respond_renewal(self.s, ren.renewal_id, True, actor, "SUCCESS", None, resp)
                accepted += 1 if new else 0
            elif i < n_accept + int(len(offered) * 0.30):
                W.respond_renewal(self.s, ren.renewal_id, False, actor, reason=r.choice(
                    ["Found a cheaper quote", "Asset sold", "No longer required"]), now=resp)
                self.label("DECLINED_RENEWAL", "Renewal", ren.renewal_id, "Customer declined; policy lapses at expiry")
            elif i < n_accept + int(len(offered) * 0.36):
                d = min(resp.date() + timedelta(days=1), pol.expiry_date, AS_OF)
                if d >= ren.generated_at.date() and pol.status == "ACTIVE":
                    W.cancel_policy(self.s, pol.policy_id, "Customer request after renewal offer", actor, self.day(d, r), effective=d)
                    self.label("CANCELLED_POLICY", "Policy", pol.policy_id, "Cancelled; open renewal offer withdrawn (CANCELLED)")
        self.s.commit()
        return accepted

    def maintenance(self):
        W.expire_stale_renewals(self.s, AS_OF, now=datetime.combine(AS_OF, time(2, 0)))
        W.expire_policies(self.s, AS_OF, now=datetime.combine(AS_OF, time(2, 5)))
        self.s.commit()
