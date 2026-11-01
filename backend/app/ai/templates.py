"""Deterministic fallback templates for each intent.

Templates render a ChatResponse directly from GroundedContext — no LLM involved.
The output is deterministic: same input → identical output.
Every number, ID and claim in the template MUST come from the GroundedContext.
"""
from __future__ import annotations
from app.ai.schemas import ChatResponse, GroundedContext, RecordRef, SupportingRule


_DISCLAIMER = "AI explains stored results only. It cannot approve, reject, or change anything."


def _base(ctx: GroundedContext, answer_id: str, **overrides) -> dict:
    d = {
        "answer_id": answer_id,
        "intent": ctx.intent,
        "record_references": ctx.record_refs,
        "supporting_rules": ctx.rules,
        "limitations": ctx.limitations,
        "confidence": ctx.confidence,
        "provider": "fallback-templates",
        "model": None,
        "used_fallback": True,
        "fallback_reason": None,
        "ai_available": False,
        "disclaimer": _DISCLAIMER,
    }
    d.update(overrides)
    return d


def render(ctx: GroundedContext, answer_id: str, ai_available: bool = False,
           fallback_reason: str | None = None) -> ChatResponse:
    """Select and render the template for the given intent."""
    fn = _TEMPLATES.get(ctx.intent, _tmpl_unsupported)
    resp = fn(ctx, answer_id)
    resp.ai_available = ai_available
    if fallback_reason:
        resp.fallback_reason = fallback_reason
    return resp


# ---------------------------------------------------------------------------
# Per-intent template functions
# ---------------------------------------------------------------------------

def _tmpl_not_found(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    limitation = ctx.limitations[0] if ctx.limitations else "The requested record was not found."
    return ChatResponse(
        **_base(ctx, answer_id, confidence="low"),
        summary=limitation,
        key_findings=[limitation],
        explanation="Please verify the ID and try again.",
        recommended_action="Check the ID format and confirm the record exists in the system.",
    )


def _tmpl_explain_decision(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    if ctx.not_found:
        return _tmpl_not_found(ctx, answer_id)
    f = ctx.facts
    dec = f.get("current_decision") or {}
    outcome = dec.get("outcome") or f.get("status", "UNKNOWN")
    authority = dec.get("approval_authority", "UNKNOWN")
    risk_score = f.get("risk_score")
    risk_cat = f.get("risk_category", "UNKNOWN")
    product = f.get("product", "Unknown product")
    quote_id = f.get("quote_id", "")
    rule_ids = dec.get("rule_ids") or []
    rule_str = ", ".join(rule_ids) if rule_ids else ""

    # Extract distinct reason messages
    reason_texts = []
    if dec.get("reasons"):
        for r in dec["reasons"]:
            msg = r.get("message") if isinstance(r, dict) else str(r)
            if msg and msg not in reason_texts:
                reason_texts.append(msg)

    # Extract missing info fields
    missing_texts = []
    if f.get("missing_info"):
        for m in f["missing_info"]:
            label = m.get("input") if isinstance(m, dict) else str(m)
            if label and label not in missing_texts:
                missing_texts.append(label)

    premium = f.get("premium")
    premium_note = f.get("premium_note", "")

    # Build clear, informative summary
    if outcome == "DECLINED":
        if reason_texts:
            summary = (
                f"Quote {quote_id} for {product} was declined due to {reason_texts[0]} "
                f"(risk score: {risk_score}, category: {risk_cat})."
            )
        elif risk_score is not None and risk_score >= 85:
            summary = (
                f"Quote {quote_id} for {product} was declined because risk score {risk_score} "
                f"exceeds the automatic decline threshold (85.0)."
            )
        else:
            summary = (
                f"Quote {quote_id} for {product} was declined under product rules "
                f"(risk score: {risk_score}, category: {risk_cat}, authority: {authority.replace('_', ' ').title()})."
            )
    elif outcome == "REFERRED":
        primary = reason_texts[0] if reason_texts else f"risk category {risk_cat} requires {authority.replace('_', ' ').title()} review"
        summary = (
            f"Quote {quote_id} for {product} was referred for underwriter review: {primary} "
            f"(risk score: {risk_score}, category: {risk_cat})."
        )
    elif outcome == "APPROVED":
        summary = (
            f"Quote {quote_id} for {product} was approved: meets all eligibility criteria "
            f"and risk score ({risk_score}) is within automated limits."
        )
    elif outcome == "PENDING_INFORMATION":
        miss_str = ", ".join(missing_texts) if missing_texts else "required applicant inputs"
        summary = f"Quote {quote_id} for {product} is pending information: missing {miss_str}."
    else:
        summary = (
            f"Quote {quote_id} for {product} status: {outcome} "
            f"(risk score: {risk_score}, category: {risk_cat}, authority: {authority.replace('_', ' ').title()})."
        )

    # Build key findings
    findings = []
    if risk_score is not None:
        findings.append(f"Risk score: {risk_score} — category: {risk_cat}")
    for msg in reason_texts[:5]:
        findings.append(msg)
    for m in missing_texts[:3]:
        findings.append(f"Missing information: {m}")
    if rule_str:
        findings.append(f"Governing rule(s): {rule_str}")
    findings.append(f"Approval authority: {authority.replace('_', ' ').title()}")
    if premium is not None:
        label = f"${premium:,.2f}" + (" (indicative, not offered)" if premium_note else "")
        findings.append(f"Calculated premium: {label}")

    # Build comprehensive, articulate detailed explanation
    exp_paragraphs = []
    if outcome == "DECLINED":
        exp_paragraphs.append(
            f"Underwriting evaluation for quote {quote_id} ({product}): "
            f"The application was evaluated by the deterministic underwriting engine and marked DECLINED."
        )
        if reason_texts:
            reasons_joined = "; ".join(reason_texts)
            p = f"Decline reason(s): {reasons_joined}."
            if "Ineligible" in reasons_joined or "ineligible" in reasons_joined:
                p += (
                    " Product eligibility rules are mandatory constraints; an application that falls outside "
                    "product limits or coverage bounds is declined automatically regardless of the calculated risk score."
                )
            exp_paragraphs.append(p)
        elif risk_score is not None and risk_score >= 85:
            exp_paragraphs.append(
                f"The calculated risk score of {risk_score} meets or exceeds the automatic decline threshold of 85.0 points."
            )

        if risk_score is not None and (risk_score < 70 or risk_cat in ("LOW", "MEDIUM")):
            exp_paragraphs.append(
                f"Note on risk assessment: Although the calculated risk score is {risk_score} ({risk_cat} risk), "
                f"eligibility validation takes precedence over risk scoring in the underwriting workflow."
            )

        if missing_texts:
            exp_paragraphs.append(
                f"Required underwriting detail(s) missing at submission: {', '.join(missing_texts)}."
            )

        meta = []
        if dec.get("decided_at"):
            meta.append(f"Decision recorded at {dec['decided_at'][:19]} by role {dec.get('decided_role', 'SYSTEM')}")
        if rule_str:
            meta.append(f"under rule {rule_str}")
        meta.append("no binding premium offer was issued.")
        exp_paragraphs.append(". ".join(meta))

    elif outcome == "REFERRED":
        exp_paragraphs.append(
            f"Underwriting evaluation for quote {quote_id} ({product}): "
            f"The quote was marked REFERRED for manual underwriter review and cannot be bound automatically."
        )
        if reason_texts:
            exp_paragraphs.append(f"Referral trigger(s): {'; '.join(reason_texts)}.")
        if risk_score is not None:
            exp_paragraphs.append(
                f"Risk assessment: The application received a risk score of {risk_score} ({risk_cat} risk). "
                f"Under the underwriting authority rules, applications in the {risk_cat} band must be reviewed and approved "
                f"by a {authority.replace('_', ' ').title()}."
            )
        if missing_texts:
            exp_paragraphs.append(
                f"Missing inputs: {', '.join(missing_texts)} were not supplied at submission and were penalised in the risk score."
            )
        if premium is not None:
            exp_paragraphs.append(
                f"Calculated indicative premium: ${premium:,.2f} (subject to underwriter review or terms adjustment)."
            )
        if dec.get("decided_at"):
            exp_paragraphs.append(
                f"Decision recorded at {dec['decided_at'][:19]} by role {dec.get('decided_role', 'SYSTEM')} under rule {rule_str or 'standard rules'}."
            )

    elif outcome == "APPROVED":
        exp_paragraphs.append(
            f"Underwriting evaluation for quote {quote_id} ({product}): "
            f"The quote was automatically APPROVED by the deterministic underwriting engine."
        )
        exp_paragraphs.append(
            f"Eligibility & Risk: All product eligibility requirements and asset value limits were fully satisfied. "
            f"The calculated risk score of {risk_score} ({risk_cat} risk) falls safely within the automated approval authority threshold."
        )
        if premium is not None:
            exp_paragraphs.append(f"Calculated premium: ${premium:,.2f}.")
        if f.get("valid_until"):
            exp_paragraphs.append(
                f"The quote is valid until {f['valid_until']} and is ready for customer acceptance and binding."
            )
        if dec.get("decided_at"):
            exp_paragraphs.append(
                f"Decision recorded at {dec['decided_at'][:19]} by role {dec.get('decided_role', 'SYSTEM')} under rule {rule_str or 'standard rules'}."
            )

    elif outcome == "PENDING_INFORMATION":
        exp_paragraphs.append(
            f"Underwriting evaluation for quote {quote_id} ({product}): "
            f"The application is currently PENDING_INFORMATION and cannot proceed to approval."
        )
        if missing_texts:
            exp_paragraphs.append(
                f"Required information missing from submission: {', '.join(missing_texts)}. "
                f"These inputs are mandatory for complete risk assessment and eligibility validation."
            )
        if dec.get("decided_at"):
            exp_paragraphs.append(
                f"Status recorded at {dec['decided_at'][:19]} by role {dec.get('decided_role', 'SYSTEM')}."
            )
    else:
        if premium is not None:
            label = f"${premium:,.2f}" + (" (indicative, not offered)" if premium_note else "")
            exp_paragraphs.append(f"Calculated premium: {label}.")
        if dec.get("decided_at"):
            exp_paragraphs.append(
                f"Decision recorded at {dec['decided_at'][:19]} by role {dec.get('decided_role', 'SYSTEM')}."
            )

    explanation = " ".join(exp_paragraphs) if exp_paragraphs else "See key findings above."

    action = ""
    if outcome == "REFERRED":
        action = (
            f"Open {quote_id} → Underwriting review panel. "
            f"Authority required: {authority.replace('_', ' ').title()}."
        )
    elif outcome == "DECLINED":
        action = f"Quote {quote_id} was declined automatically. Review the reasons above if re-submission is considered."
    elif outcome == "APPROVED":
        action = f"Quote {quote_id} is approved. The applicant can accept the quote and proceed to payment."
    elif outcome == "PENDING_INFORMATION":
        action = f"Request the missing information listed above from the applicant."

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=explanation,
        recommended_action=action,
    )


def _tmpl_applicant_risk_profile(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    if ctx.not_found:
        return _tmpl_not_found(ctx, answer_id)
    f = ctx.facts
    app_id = f.get("applicant_id", "")
    age = f.get("age")
    location = f.get("location", "Unknown")
    app_type = f.get("applicant_type", "INDIVIDUAL")
    q_count = f.get("quote_count", 0)
    pol_count = f.get("policy_count", 0)
    asset_count = f.get("asset_count", 0)
    max_score = f.get("max_risk_score")
    avg_score = f.get("avg_risk_score")

    summary = (
        f"Applicant {app_id} ({app_type}, age {age or 'unknown'}, location: {location}): "
        f"{q_count} quote(s), {pol_count} polic(ies), {asset_count} asset(s)."
    )

    findings = []
    if max_score is not None:
        findings.append(f"Highest risk score across quotes: {max_score}")
    if avg_score is not None:
        findings.append(f"Average risk score: {avg_score}")
    for q in (f.get("recent_quotes") or [])[:3]:
        findings.append(
            f"Quote {q.get('quote_id')}: {q.get('status')} ({q.get('product')}, "
            f"risk score {q.get('risk_score')}, category {q.get('risk_category')})"
        )

    explanation = (
        f"The applicant has {asset_count} insured asset(s) and {q_count} quotes on record. "
        f"Risk scores and categories are set by the deterministic risk engine."
    )

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=explanation,
        recommended_action=f"Open applicant {app_id} in the Applicants section for full details.",
    )


def _tmpl_premium_explanation(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    if ctx.not_found:
        return _tmpl_not_found(ctx, answer_id)
    f = ctx.facts
    quote_id = f.get("quote_id", "")
    premium = f.get("premium")
    breakdown = f.get("premium_breakdown") or {}
    product = f.get("product", "Unknown")
    status = f.get("status", "")

    if premium is None:
        summary = f"No premium has been calculated for quote {quote_id} yet."
        return ChatResponse(**_base(ctx, answer_id), summary=summary,
                            key_findings=["Premium not yet calculated."],
                            explanation="Submit/evaluate the quote to generate a premium.",
                            recommended_action=f"Open quote {quote_id} and re-evaluate.")

    label = f"${premium:,.2f}"
    if status == "DECLINED":
        label += " (indicative — not offered, quote was declined)"

    summary = f"Premium for {product} quote {quote_id}: {label}."

    findings = []
    if breakdown:
        base_prem = breakdown.get("base_premium")
        adj_prem = breakdown.get("adjusted_premium")
        final = breakdown.get("final_premium")
        formula = breakdown.get("formula", "")
        if base_prem is not None:
            findings.append(f"Base premium: ${base_prem:,.2f}")
        if adj_prem is not None:
            findings.append(f"Adjusted premium (after risk/age/location factors): ${adj_prem:,.2f}")
        charges = breakdown.get("charges") or {}
        for chg, amt in charges.items():
            findings.append(f"{chg.replace('_', ' ').title()}: ${float(amt):,.2f}")
        if final is not None:
            findings.append(f"Final premium: ${final:,.2f}")
        if formula:
            findings.append(f"Formula: {formula}")
        factors = breakdown.get("factors") or {}
        if factors:
            findings.append(
                "Factors: " + ", ".join(f"{k}={v}" for k, v in factors.items())
            )

    explanation = (
        f"The premium is calculated by the deterministic premium engine using "
        f"rules version {f.get('rules_version', 'N/A')}. "
        f"Risk score: {f.get('risk_score')}, category: {f.get('risk_category')}."
    )

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=explanation,
        recommended_action=f"Open quote {quote_id} → Premium breakdown tab for full details.",
    )


def _tmpl_anomaly_explanation(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    if ctx.not_found:
        return _tmpl_not_found(ctx, answer_id)
    f = ctx.facts
    exc_id = f.get("exception_id", "")
    issue = f.get("issue_type", "UNKNOWN")
    severity = f.get("severity", "UNKNOWN")
    entity = f.get("affected_entity", "")
    record_id = f.get("affected_record_id", "")
    expected = f.get("expected_outcome", "")
    actual = f.get("actual_outcome", "")
    resolution = f.get("resolution_status", "OPEN")

    summary = (
        f"Exception {exc_id}: {issue} ({severity}) on {entity} {record_id}. "
        f"Resolution status: {resolution}."
    )

    findings = [
        f"Expected: {expected}",
        f"Actual: {actual}",
        f"Severity: {severity}",
        f"Affected {entity}: {record_id}",
        f"Detected at: {str(f.get('detected_at', ''))[:19]}",
    ]

    explanation = (
        "This exception was detected by the automated data quality check. "
        "It does not indicate a system error — it may reflect an intentional test anomaly "
        "or a data quality issue requiring review."
    )

    action = (
        f"Open Exceptions → {exc_id} to review and update the resolution status. "
        f"Then investigate the affected {entity} record {record_id}."
    )

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=explanation,
        recommended_action=action,
    )


def _tmpl_anomaly_summary(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    if ctx.not_found:
        return _tmpl_not_found(ctx, answer_id)
    f = ctx.facts
    total = f.get("total_findings", 0)
    run_id = f.get("run_id", "")
    validated_at = str(f.get("validated_at", ""))[:19]
    by_type = f.get("by_issue_type") or {}
    by_sev = f.get("by_severity") or {}

    summary = (
        f"Validation run {run_id} (completed {validated_at}): "
        f"{total} exception(s) detected."
    )

    findings = [f"Total findings: {total}"]
    for sev, cnt in sorted(by_sev.items()):
        findings.append(f"{sev} severity: {cnt}")
    for itype, cnt in sorted(by_type.items(), key=lambda x: -x[1])[:5]:
        findings.append(f"{itype}: {cnt}")

    explanation = (
        "These findings come from the deterministic data-quality detector. "
        "They are stored in the validated_exceptions table and can be reviewed and resolved "
        "in the Exceptions section."
    )

    eval_report = f.get("evaluation_report")
    if eval_report:
        prec = eval_report.get("precision")
        recall = eval_report.get("recall")
        if prec is not None and recall is not None:
            findings.append(
                f"Detector evaluation: precision={prec:.1%}, recall={recall:.1%} "
                f"(compared to stored evaluation labels — NOT used by the detector)."
            )

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=explanation,
        recommended_action="Open Exceptions in the ops console to review and resolve findings.",
    )


def _tmpl_policy_history(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    if ctx.not_found:
        return _tmpl_not_found(ctx, answer_id)
    f = ctx.facts
    pol_id = f.get("policy_id", "")
    status = f.get("status", "UNKNOWN")
    product = f.get("product", "")
    premium = f.get("premium")
    start = str(f.get("start_date", ""))
    expiry = str(f.get("expiry_date", ""))

    summary = (
        f"Policy {pol_id} ({product}, status: {status}): "
        f"${premium:,.2f} premium, " if premium else ""
        f"period {start} to {expiry}."
    )

    findings = []
    for h in (f.get("status_history") or [])[:5]:
        findings.append(
            f"Status: {h.get('from') or 'initial'} → {h.get('to')} "
            f"at {str(h.get('at', ''))[:19]}"
        )
    if f.get("endorsement_count", 0) > 0:
        findings.append(f"Endorsements: {f.get('endorsement_count')} on record")
    if f.get("renewal_count", 0) > 0:
        findings.append(f"Renewals: {f.get('renewal_count')} on record")
    if f.get("payment_count", 0) > 0:
        findings.append(f"Payments: {f.get('payment_count')} on record")
    if f.get("cancelled_at"):
        findings.append(f"Cancelled at: {str(f.get('cancelled_at'))[:10]}")

    explanation = (
        f"Policy {pol_id} is in {status} status. "
        "Status history, endorsements, renewals and payments are shown above."
    )

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=explanation,
        recommended_action=f"Open policy {pol_id} in the Policies section for full details.",
    )


def _tmpl_renewal_explanation(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    if ctx.not_found:
        return _tmpl_not_found(ctx, answer_id)
    f = ctx.facts
    renewal_id = f.get("renewal_id", "")
    policy_id = f.get("policy_id", "")
    status = f.get("status", "UNKNOWN")
    elig = f.get("eligibility_status", "UNKNOWN")
    reasons = f.get("reasons") or []
    offered = f.get("offered_premium")

    summary = (
        f"Renewal {renewal_id} for policy {policy_id}: status {status}, "
        f"eligibility {elig}."
    )

    findings = []
    for r in reasons[:5]:
        findings.append(str(r))
    if offered is not None:
        findings.append(f"Offered premium: ${offered:,.2f}")

    explanation = (
        f"Renewal eligibility is determined by the deterministic policy engine "
        f"based on policy status and the {f.get('new_start_date', '')} renewal date."
    )

    action = ""
    if status in ("GENERATED", "OFFERED"):
        action = f"Open policy {policy_id} → Renewals tab to review and respond."
    elif status == "DECLINED":
        action = f"Renewal {renewal_id} was declined. Review reasons above."

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=explanation,
        recommended_action=action,
    )


def _tmpl_audit_summary(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    if ctx.not_found:
        return _tmpl_not_found(ctx, answer_id)
    f = ctx.facts
    entity_id = f.get("entity_id", "")
    entity_type = f.get("entity_type", "")
    event_count = f.get("event_count", 0)

    summary = f"Audit trail for {entity_type} {entity_id}: {event_count} event(s) found."

    findings = []
    for e in (f.get("events") or [])[:10]:
        findings.append(
            f"{str(e.get('occurred_at', ''))[:19]} — {e.get('event_type')} "
            f"by {e.get('actor_role', 'SYSTEM')}"
        )

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation="The audit trail is append-only and records every state change.",
        recommended_action=f"Open the Audit log filtered to {entity_id} for full trail.",
    )


def _tmpl_senior_review_queue(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    f = ctx.facts
    total_ref = f.get("total_referred", 0)
    senior_req = f.get("senior_review_required", 0)
    items = f.get("items") or []

    summary = (
        f"{senior_req} quote(s) require Senior Underwriter review "
        f"(out of {total_ref} total referred)."
    )

    findings = []
    for item in items[:10]:
        qid = item.get("quote_id", "")
        prod = item.get("product", "")
        score = item.get("risk_score")
        reasons_text = "; ".join(
            r.get("message") if isinstance(r, dict) else str(r)
            for r in (item.get("reasons") or [])[:2]
        )
        findings.append(f"{qid} ({prod}, risk {score}): {reasons_text}")

    explanation = (
        "Quotes listed above are in REFERRED status and require SENIOR_UNDERWRITER authority "
        "to approve or decline. Only a user with Administrator role can act on these."
    )

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=explanation,
        recommended_action="Open Underwriting → Pending reviews. Filter by authority.",
    )


def _tmpl_aggregate_insight(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    f = ctx.facts
    total = f.get("total_quotes_analyzed", 0)
    outcome_dist = f.get("outcome_distribution") or {}
    top_rules = f.get("top_rule_ids") or []
    filter_prod = f.get("filter_product") or "all products"
    filter_risk = f.get("filter_risk_category") or "all risk categories"

    summary = (
        f"Aggregate insight across {total} quote(s) "
        f"({filter_prod}, {filter_risk})."
    )

    findings = [f"Total quotes analysed: {total}"]
    for outcome, cnt in sorted(outcome_dist.items(), key=lambda x: -x[1]):
        findings.append(f"{outcome}: {cnt} quote(s)")
    for item in top_rules[:5]:
        rid = item.get("rule_id", "")
        cnt = item.get("count", 0)
        findings.append(f"Rule {rid}: triggered {cnt} time(s)")

    avg = f.get("avg_risk_score")
    if avg is not None:
        findings.append(f"Average risk score: {avg}")

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation="Aggregates are computed by the backend from stored quote and decision records.",
        recommended_action="Open Underwriting → Decisions for detailed drill-down.",
    )


def _tmpl_rules_help(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    f = ctx.facts
    rv = f.get("rules_version", "N/A")
    thresholds = f.get("risk_thresholds") or {}
    decline = f.get("decline_risk_score")
    product_limits = f.get("product_limits") or {}

    summary = f"Business rules summary (version {rv})."

    findings = [
        f"Rules version: {rv}",
        f"Risk thresholds: LOW ≤ {thresholds.get('low_max')}, "
        f"MEDIUM ≤ {thresholds.get('medium_max')}, HIGH > {thresholds.get('medium_max')}",
        f"Auto-decline threshold: risk score ≥ {decline}",
    ]
    for prod, limits in product_limits.items():
        auto = limits.get("auto_approval_limit")
        analyst = limits.get("analyst_limit")
        reviewer = limits.get("reviewer_limit")
        findings.append(
            f"{prod}: auto-approve ≤ ${auto:,}, analyst ≤ ${analyst:,}, "
            f"reviewer ≤ ${reviewer:,}"
        )

    return ChatResponse(
        **_base(ctx, answer_id),
        summary=summary,
        key_findings=findings,
        explanation=(
            "All values come from rules_config.py — the single source of truth for "
            "all business rules. The AI copilot reads from this file and never hard-codes values."
        ),
        recommended_action="See docs/BUSINESS_RULES.md for the full rules catalogue.",
    )


def _tmpl_unsupported(ctx: GroundedContext, answer_id: str) -> ChatResponse:
    supported = [
        "explain_decision — why a quote was approved/referred/declined",
        "applicant_risk_profile — risk profile of an applicant",
        "premium_explanation — how a premium was calculated",
        "anomaly_explanation — details of a specific detected exception",
        "anomaly_summary — overview of all detected anomalies",
        "policy_history — history of a policy",
        "renewal_explanation — why a renewal was declined or withheld",
        "audit_summary — audit trail for a quote or policy",
        "senior_review_queue — quotes requiring senior underwriting review",
        "aggregate_insight — breakdown of outcomes/rules across quotes",
        "rules_help — current business rule values and thresholds",
    ]
    return ChatResponse(
        **_base(ctx, answer_id, confidence="low", limitations=ctx.limitations or ["Question type not supported."]),
        summary="I can't answer that type of question directly.",
        key_findings=[],
        explanation=(
            "The Underwriting Copilot can only explain stored records and rules. "
            "It cannot browse the web, make predictions, or answer general questions."
        ),
        recommended_action="Try one of the supported question types: " + "; ".join(supported[:3]) + ".",
    )


# Map intent → template function
_TEMPLATES = {
    "explain_decision": _tmpl_explain_decision,
    "applicant_risk_profile": _tmpl_applicant_risk_profile,
    "premium_explanation": _tmpl_premium_explanation,
    "anomaly_explanation": _tmpl_anomaly_explanation,
    "anomaly_summary": _tmpl_anomaly_summary,
    "policy_history": _tmpl_policy_history,
    "renewal_explanation": _tmpl_renewal_explanation,
    "audit_summary": _tmpl_audit_summary,
    "senior_review_queue": _tmpl_senior_review_queue,
    "aggregate_insight": _tmpl_aggregate_insight,
    "rules_help": _tmpl_rules_help,
    "unsupported": _tmpl_unsupported,
}

