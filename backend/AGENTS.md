# backend/AGENTS.md
Layout: `app/core` (rules_config, errors, security, enums, config) - `app/engines` (pure deterministic logic incl. validation_engine) - `app/services` (workflow, ids, seed, demo_scenarios, evaluation) - `app/models` + `app/database` - `app/api` (deps/auth, serializers, routes_*) - `app/schemas` (request bodies) - `app/data_generator` (config, profiles, pipeline, anomalies, export, runner, CLI) - `app/ai` (schemas, tools, intents, templates, prompts, providers, guard, ratelimit, service) - `migrations/` (Alembic 0001-0003) - `tests/` - `scripts/` (demo + doc generators).

## Status: Phases 0-5 done (see docs/PROJECT_STATUS.md). Next: Phase 6 deployment.

## Rules for changes
- New business behaviour -> `workflow.py`/engines + a test; routes stay thin (authenticate, authorise, call service, serialise).
- Any rule/threshold -> `core/rules_config.py`; bump `RULES_VERSION`; regenerate docs (commands in root AGENTS.md).
- Model change -> `alembic revision --autogenerate -m "..."` and keep `test_alembic_upgrade_matches_models` green.
- New/changed route -> `python -m scripts.generate_api_contract --write` (a test fails if stale).
- Generator changes must keep `test_fixed_seed_reproducibility_and_seed_sensitivity` green: no wall-clock, UUIDs or unseeded randomness inside generation; pass `now` to every workflow call; export rows sorted by PK.
- The detector (`validation_engine`) and `app/ai/**` must never import/query ground truth; only `services/evaluation.py` may.
- AI Copilot (`app/ai/**`) is strictly read-only and answers must be grounded in facts verified by `guard.py`.
- Routers must use `route_class=TransactionalRoute` (commit BEFORE the response; never commit in dependency exit code - it runs after the response and causes read-after-write races).
- Customer-facing routes must verify ownership (`_own`) and return 404 for foreign records.
- Mutation-check security/determinism tests when touching them (break the rule, confirm a test fails, restore).
