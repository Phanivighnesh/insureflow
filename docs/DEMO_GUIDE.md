# Demo Guide (5-minute walkthrough)
Start both servers (see README). Use **two browser tabs**: A = customer portal, B = operations console. Everything below is computed by the backend engines — nothing is scripted in the UI.

## The five "Try Demo Scenarios" (Products page or inside the application wizard)
| Scenario | Product | What the backend produces (verified in tests) |
|---|---|---|
| Low-risk motor application | Motor | **Approved automatically** (rule UW-APR-001), premium **$1,118.00** |
| Medium-risk property application | Property | **Referred** to Operations Analyst (medium risk) |
| High-risk motor application | Motor | **Declined** (UW-DEC-002, risk ≥ 85); customer sees reasons and **no premium** |
| Commercial application with missing fire exposure | Commercial | **More information needed** (missing mandatory data is never treated as zero risk); fill the form on the result page to re-evaluate |
| Approved property application (full journey) | Property | **Approved**, premium **$686.75** → accept → demo payment → policy |

## Suggested script
1. **Tab A** `/login` → *Continue as demo customer* → **Products** → *Load into application* on "Approved property application" → Continue ×3 → **Submit**. Result page shows decision, rule IDs, eligibility checks, risk factors and premium breakdown.
2. **Tab B** `/ops/login` → Analyst + code `insureflow-demo` → **Quotes** → search the quote ID (or applicant name): the *same* record, with audit trail.
3. **Tab A**: *Accept this quote* → in the **DEMO PAYMENT** panel choose *Failed payment* → Pay: **no policy is issued**. Choose *Successful payment* → Pay: policy issued → *View policy*.
4. **Tab B**: **Policies** → the same policy; open it for lifecycle timeline, premium snapshot, endorsements and renewals.
5. **Tab A**: load "Medium-risk property application" → submit → status *Referred* (page auto-refreshes). **Tab B** → **Underwriting** queue → open → **Approve** (confirmation dialog) → Tab A now shows *Approved*.
6. **Tab A** policy page → *Request change* with new coverage above the product limit → recorded and **auto-rejected** with `ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT`; a valid change goes to **Tab B → Endorsements** for approval.
7. **Tab B** (sign in as *Administrator*) → **Data & validation** → *Generate dataset* (starter or full; confirmation required) → *Run validation* → **Exceptions** (8 anomaly types, precision/recall against separately stored ground truth).
8. **Tab B** → **AI Copilot** (`/ops/copilot`):
   - View status badge (Live Groq `openai/gpt-oss-20b` if `GROQ_API_KEY` is configured, or deterministic `Template mode`).
   - Click suggested question: *"What is the auto-approval limit for property?"* → view the $500,000 threshold and governing rule `UW-RULE-001`.
   - Query a real quote: *"Why was QTE-2026-004001 declined?"* → view the detailed breakdown of the asset value boundary breach ($49,991 < $50,000) and why rule `UW-DEC-001` overrode the low risk score.
   - Click the rendered `Quote QTE-...` chip to jump directly into the quote review.
   - From any Quote detail, Policy detail, or Exception modal, click the **"Ask Copilot"** button to jump into Copilot with pre-filled context.

## Things to try that should be refused
Customer opening `/ops` (redirected); a second customer tab opening the first customer's quote URL (404); analyst approving a referral that needs reviewer authority (403 — the queue shows "No — escalate"); regenerating data as a non-administrator (button disabled; API 403).
