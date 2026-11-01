# Technical Decisions (assumptions where the spec was silent)
1. **Centralised rules** in one Python module (not DB/YAML) for type safety and testability; master-data tables are seeded from it. Changing rules = bump `RULES_VERSION`.
2. **Pure engines + single workflow service** so customer API, ops API and generator cannot diverge.
3. **Premium base = requested coverage × base_rate × coverage-option multiplier** ("insured value" = sum insured). Decimal/HALF_UP, tolerance 0.01.
4. **Premium is computed whenever eligible, including risk-declined quotes** (indicative; UI must not present it as an offer). Ineligible/needs-info → no premium.
5. **Medium risk is always referred** (spec demo scenario 2); low risk above the auto-approval limit is referred by coverage band; ≥85 score auto-declined (demo scenario 3).
6. **Role → authority:** Analyst=OPERATIONS_ANALYST, Risk reviewer=RISK_REVIEWER, Administrator=SENIOR_UNDERWRITER.
7. **Policy rows are created at issuance (ACTIVE)**; DRAFT/PENDING_* exist in the transition table for spec compliance but the pre-issuance stages are tracked on the Quote. Revisit if evaluators require policy rows earlier.
8. **Policy never mutated by endorsements**; effective terms = latest APPROVED endorsement.
9. **Renewal acceptance creates a new Policy** (`renewal_of_policy_id`), marks old RENEWED; renewal chain is a permitted overlap reason. Renewals that fail underwriting are recorded as CANCELLED with reasons; cancelled-policy renewals raise `RENEWAL_FOR_CANCELLED_POLICY` and create no record.
10. **Extra ID prefixes** (not in spec): UWD, RAS, ACC, PAY, AUD, GT, AUTH - same zero-padded convention.
11. **Fictional locations** with risk tiers; currency USD; all rates synthetic.
12. **Naive UTC datetimes** stored (SQLite/PG parity); `now` injectable.
13. **Demo auth** = opaque role sessions, clearly labelled demo; not production authentication.

## Phase 2-3 decisions
14. **Auth = signed demo sessions** (stdlib HMAC; no extra dependency). Customer sessions self-issue and are isolated by `customer_key` (stored on `Applicant.owner_key`); staff sessions need `STAFF_ACCESS_CODE`. Not production auth: no password hashing, MFA, revocation or rate limiting. Foreign customer IDs return **404** (not 403) to avoid confirming existence.
15. **Underwriting actions are addressed by `decision_id`** (spec path) and are refused with 409 if that decision has been superseded (optimistic concurrency), then delegated to `review_quote`.
16. **Routes never contain business rules**; DB session dependency commits per request and rolls back on any exception, so a refused action leaves no partial state.
17. **`as_of_date` for renewal generation is staff-only** (demo convenience to reach the renewal window); customers always use the real current date.
18. **Generation reuses the workflow service** with a simulated clock instead of bulk-inserting rows, so derived values (risk, premium, decisions, statuses, audit) are guaranteed engine-consistent; cost: ~2 minutes for the full scale.
19. **Volumes are totals including additive anomalies** (see `DATA_GENERATION.md`).
20. **Detector independence**: `validation_engine` has no access path to ground truth (AST-tested). Two detector rules were corrected after the first run exposed a real gap (renewals generated after cancellation but later EXPIRED), not tuned to the labels.
21. **JSON-null pitfall**: JSON columns store Python `None` as JSON `null`, not SQL NULL - validation filters in Python.
22. **INVALID_FOREIGN_KEY injection is SQLite-only** (requires disabling FK enforcement for one insert); other dialects skip it with a recorded note.
23. **Renewal-term policies count toward the 2,000 policies** and have no `quote_id` (`renewal_of_policy_id` links the chain).
24. **Medium risk is always referred** (spec demo scenario) which makes the generated referral rate high (~53% at full scale); this is a rule-config outcome, not a data defect.

## Phase 4 decisions
25. **Session in `sessionStorage`** (per tab): lets a customer and an operations user be signed in at once in two tabs; refresh keeps the session; 401 clears it.
26. **One centralised, injectable API client** (`makeApi({getToken, baseUrl})`): the app and the integration tests use the identical code path, so the contract is tested rather than mocked. No mocks/fixtures substitute backend data anywhere in the UI.
27. **Dynamic customer form** is rendered from `GET /customer/products` (`asset_fields`, coverage options, locations); only the demo-scenario prefill converts `year_built → property age` using the backend's reference year (a documented constant).
28. **UI never computes business results**; the only client-side logic is presentation (formatting, a non-binding "within your authority" hint mirroring the backend, soft form warnings). Declined quotes show no premium because the API withholds it from customers.
29. **Transactional routes** (`TransactionalRoute`): commit before response (fixes a read-after-write race found by live-server tests); error responses roll back.
30. **Code-splitting**: ops console and chart-heavy pages are lazy chunks.
31. **Tests boot the real backend** (Vitest `globalSetup`) instead of mocking `fetch`; chosen because it caught a genuine backend race that unit/ASGI-in-process tests could not.
32. **No browser available** in the build environment, so visual QA was not performed; UI correctness is asserted through DOM tests.

## Phase 5 decisions (AI Copilot)
33. **Read-only Copilot**: The AI copilot is strictly an explanatory and summarization assistant. It has zero tool capabilities to mutate database records, decide claims, approve quotes, or override business rules. Underwriters must click provided record links to execute actions through existing workflow forms.
34. **Dual-mode architecture with mandatory fallback**: The system defaults to deterministic template rendering (`templates.py`) when offline or unconfigured. If `GROQ_API_KEY` is set, it calls Groq (`openai/gpt-oss-20b`); any timeout, 4xx, 5xx, or malformed JSON cleanly degrades to the deterministic template without raising 500 errors.
35. **Anti-hallucination guard**: All LLM completions pass through a deterministic post-generation verifier (`guard.py`). Any completion citing an unknown record ID, unverified monetary amount (beyond ±1.0 tolerance), or making forbidden state-changing claims is rejected and replaced by the grounded fallback.
36. **Zero GroundTruth access**: An AST static test proves `app/ai/**` has zero imports or queries of `GroundTruth` or `services/evaluation.py`. Ground truth remains strictly for offline evaluation.
37. **Prompt injection isolation**: Untrusted data from database records is isolated inside `<facts>...</facts>` blocks with system instructions to ignore embedded instructions. PII is redacted prior to serialization.
38. **Audit isolation (`NON_DATASET`)**: AI chat logs are persisted in `ai_interactions` (migration `0003`) for operational auditability, but declared in `NON_DATASET` so synthetic data exports, validation counts, and reproducibility checksums remain byte-for-byte identical.
