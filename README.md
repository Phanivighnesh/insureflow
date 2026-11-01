# InsureFlow - Smart Insurance Operations Platform (DEMO / synthetic data)

AI-assisted insurance underwriting and policy lifecycle platform: a customer portal and an operations console built in React, served by a single FastAPI backend, relational database, and deterministic rules engines. All insurance products, rates, and records are synthetic; no real customer personal data is used. Payment processing is for demonstration purposes only (no payment card data collected or processed). Authentication uses an isolated session mechanism for evaluation and demonstration.

---

## Live Demonstration Environment

InsureFlow is publicly deployed and accessible at the following URLs:

- **Live Application:** https://insureflow-six.vercel.app/
- **Backend API:** https://insureflow-api-tpmy.onrender.com

The primary application entry point is the **Live Application** URL above, which hosts the unified customer portal and operations console. The **Backend API** provides the underlying REST services and interactive Swagger documentation at `https://insureflow-api-tpmy.onrender.com/docs`.

---

## Status

See `docs/PROJECT_STATUS.md` and `docs/REQUIREMENTS_TRACEABILITY.md` for full requirement tracking.

| Component / Subsystem | Status | Details |
|---|---|---|
| Business rules, engines, workflow, policy lifecycle | Complete (Verified) | Pure deterministic Python engines in `backend/app/engines/` covered by unit tests. |
| REST API (64 endpoints), RBAC, Alembic migrations | Complete (Verified) | SQLite default with verified migrations 0001-0004; PostgreSQL DDL compiles. |
| Synthetic data generation (3,000 / 4,000 / 2,000 / 1,200) | Complete (Verified) | Fixed seed 20261022; 8 labelled anomaly types; full reproducibility across 42 files. |
| Customer portal (React) | Complete (Verified) | Application wizard, dynamic quote results, demo payment, account dashboard. |
| Operations console (React) | Complete (Verified) | Overview metrics, records management, underwriting referrals queue, governance. |
| Underwriting AI Copilot (`/ops/copilot`) | Complete (Verified) | Groq `openai/gpt-oss-20b` integration with offline deterministic template fallback and anti-hallucination guard. |
| Cloud deployment (Vercel / Render / PostgreSQL) | Complete (Deployed) | Production frontend deployed to Vercel; containerized FastAPI backend and PostgreSQL database deployed to Render. |

---

## Prerequisites

Before setting up InsureFlow locally, ensure that your environment meets the following requirements:

- **Python**: Version 3.11 or 3.12 (Python 3.12 recommended).
- **Node.js**: Version 18.x or 20.x LTS.
- **Package Manager**: `npm` version 9.x or later.
- **Database**: SQLite 3 (included with standard Python runtime) for local development; PostgreSQL 15+ (optional for production-like testing).
- **Git**: Version 2.30 or later.

---

## Local Setup and Execution

### 1. Backend Setup

Open a terminal and navigate to the `backend` directory:

```bash
cd backend
```

Create and activate a virtual environment:

- **macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- **Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure environment variables:

```bash
cp ../.env.example .env
```

Start the backend API server:

```bash
uvicorn app.main:app --reload --port 8000
```

- API Base URL: `http://localhost:8000`
- Interactive OpenAPI / Swagger Documentation: `http://localhost:8000/docs`
- Alternative ReDoc Documentation: `http://localhost:8000/redoc`

*Note:* On initial startup, the backend automatically creates the SQLite database (`backend/insureflow.db`) and seeds baseline master data. If running with a managed database, execute Alembic migrations:

```bash
alembic upgrade head
```

### 2. Frontend Setup

Open a separate terminal window and navigate to the `frontend` directory:

```bash
cd frontend
```

Install Node.js dependencies:

```bash
npm install
```

Start the Vite development server:

```bash
npm run dev
```

- Customer Portal & Operations Console URL: `http://localhost:5173`
- The Vite development server automatically proxies all `/api` requests to `http://localhost:8000`.

---

## Demo Access and Role-Based Access Control

The platform provides role-based access for four distinct actors across two user interfaces:

| Actor | Login Path | Access Mechanism | Permissions & Scope |
|---|---|---|---|
| Customer | `http://localhost:5173/login` | Click **Continue as demo customer** | Isolated session; create and view quote applications; execute demo payments; view issued policies, endorsements, and renewal offers. |
| Operations Analyst | `http://localhost:5173/ops/login` | Select role and enter staff access code | View all quotes, policies, and applicants; approve or refer quotes within standard authority limits; view Underwriting Copilot. |
| Risk Reviewer | `http://localhost:5173/ops/login` | Select role and enter staff access code | Review high-risk referrals and compliance exceptions; execute manual override decisions; access system governance and validation. |
| Administrator | `http://localhost:5173/ops/login` | Select role and enter staff access code | Senior underwriting authority; execute synthetic dataset generation; run data validation; download system exports. |

- **Default Staff Access Code:** `insureflow-demo` (configurable via `STAFF_ACCESS_CODE`).
- **Session Isolation:** Each customer session generates an isolated `owner_key` stored in browser storage. Customers cannot view or modify applications submitted by other sessions.
- **Two-Tab Testing:** Open the customer portal in one browser tab and the operations console in another tab to observe real-time submission visibility.

---

## Environment Variables and Configuration

Configuration settings are loaded using `python-dotenv` from `.env` in the project root, `backend/.env`, or the active environment. Real environment variables always take precedence over file values.

### Backend Configuration (`.env`)

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./insureflow.db` | SQLAlchemy connection string (`sqlite:///...` or `postgresql+psycopg2://...`). |
| `GROQ_API_KEY` | *(None / Optional)* | Groq Cloud API key for Live LLM mode in Underwriting Copilot. If omitted, the copilot runs using deterministic template fallback. |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Model identifier used for Groq chat completions. |
| `AI_ENABLED` | `true` | Enables or disables the AI Copilot endpoints. |
| `AI_TIMEOUT_SECONDS` | `20.0` | Timeout threshold in seconds before falling back to deterministic templates. |
| `AI_RATE_LIMIT_PER_MINUTE` | `20` | Maximum Copilot requests allowed per operator per minute. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed CORS origins. |
| `DEFAULT_SEED` | `20261022` | PRNG seed used for deterministic synthetic data generation. |
| `SESSION_SECRET` | `dev-only-insecure-secret-change-me` | Secret key used to sign demo session tokens. Override in shared environments. |
| `STAFF_ACCESS_CODE` | `insureflow-demo` | Passcode required for operations staff roles on `/ops/login`. |
| `SESSION_TTL_HOURS` | `12` | Expiration window for demo authentication tokens. |
| `DATA_DIR` | `./data` | Directory path where generated exports, manifests, and validation reports are stored. |

### Frontend Configuration (`frontend/.env.example`)

| Variable | Default Value | Description |
|---|---|---|
| `VITE_API_BASE` | *(Empty)* | URL of the deployed FastAPI backend (production). Leave empty in development to utilize Vite proxy. |
| `VITE_PROXY_TARGET` | `http://localhost:8000` | Target URL for the local development reverse proxy. |

---

## Synthetic Data Generation and Validation

The project includes an end-to-end data generation pipeline that produces realistic, referentially sound insurance records.

### Pre-Generated Dataset

The repository includes a generated dataset in `data/exports/full/`:
- `csv/`: Normalized relational tables in CSV format.
- `json/`: Relational tables in JSON format (tables under 5,000 rows).
- `seed_data.sql`: Raw SQL insertion script (41.8 MB).
- `ground_truth/`: Evaluation-only anomaly labels (`ground_truth.csv`, `ground_truth.json`).
- `manifest.json`: Checksums, record counts, and configuration metadata.
- `validation_report.json`: Precision, recall, and rule violation breakdown.
- `reproducibility_report.json`: Verification of identical checksums across regeneration runs.

### Generation Commands

To generate or regenerate datasets from the command line:

```bash
cd backend

# Generate starter dataset (scaled down for rapid development testing)
python -m app.data_generator --scale starter

# Generate full baseline dataset (replaces backend/insureflow.db and updates exports)
python -m app.data_generator --scale full --db sqlite:///./insureflow.db --out ../data/exports/full

# Execute reproducibility check (runs generator twice with fixed seed 20261022 and compares hashes)
python -m app.data_generator --seed 20261022 --scale full --repro-check
```

### Generating Synthetic Data Through the Operations Portal

The Operations Portal provides a graphical interface for generating synthetic insurance datasets directly from the web browser, offering an interactive alternative to the command-line interface. Users do not need access to a terminal or local Python environment when utilizing this feature.

This capability is fully supported in both the locally running application and the deployed production environment on Vercel. Generated records are immediately stored in the backend database (SQLite in development, PostgreSQL in production) and become accessible across both the customer portal and the operations console.

#### Step-by-Step Generation Workflow

1. **Sign In as Administrator:** Navigate to `/ops/login` in the Operations Portal. Select the **Administrator** role, enter staff passcode `insureflow-demo`, and sign in. (Only users with the Administrator role hold the authority required to regenerate data.)
2. **Open Data & Validation:** From the operations console sidebar, select **Data & validation** (`/ops/data`).
3. **Configure Generation Parameters:**
   - **Scale:** Select either `Starter` (~150 applicants, 200 quotes, 100 policies, 60 renewals; completes in seconds) or `Full` (3,000 applicants, 4,000 quotes, 2,000 policies, 1,200 renewals; completes in approximately 2 minutes).
   - **Random Seed:** Specify an integer PRNG seed (default: `20261022`) to ensure deterministic output.
   - **Inject Labelled Anomalies:** Check or uncheck whether to inject synthetic data quality issues and policy violations. (Ground truth labels are stored in a dedicated evaluation table isolated from underwriting engines.)
4. **Initiate Generation:** Click the **Generate dataset** button.
5. **Acknowledge Destructive Overwrite:** A confirmation modal opens warning that dataset regeneration permanently replaces all existing applicants, quotes, policies, endorsements, renewals, audit records, and demo submissions. Check the box labeled *"I understand this cannot be undone"* and click **Delete & regenerate**.
6. **Automatic Background Processing:** The backend executes the generation pipeline asynchronously in the background. The user interface displays an active status indicator and automatically refreshes live database row counts, metrics cards, and validation reports upon completion.

*Note on Data Persistence:* This feature is designed for demonstration, testing, and evaluation. Because dataset regeneration is destructive, any customer applications or policies submitted during an interactive session will be replaced by the newly generated synthetic records.

### Dataset Scope and Volume

At `scale=full`, the pipeline produces:
- **Applicants:** 3,000
- **Quotes:** 4,000 across 3 product lines (`PROD-001` Motor, `PROD-002` Property, `PROD-003` Commercial)
- **Policies:** 2,000
- **Renewals:** 1,200
- **Injected Anomaly Scenarios (130 instances):**
  - Policy issued without recorded customer acceptance (20)
  - Premium formula calculation mismatch (20)
  - Endorsement coverage exceeding product limits (20)
  - Renewal offer created for cancelled policy (20)
  - Unauthorized policy period overlap (20)
  - Duplicate transaction / payment (10)
  - Invalid date sequence (10)
  - Invalid foreign key reference (10)

### Automated Anomaly Detection

Run the independent validation engine to evaluate anomalies against ground truth:

```bash
cd backend
python -c "from app.database.session import SessionLocal; from app.services.evaluation import evaluate_current_database; s = SessionLocal(); res = evaluate_current_database(s); print(f'Detected: {res.detected_count}, Precision: {res.metrics.precision}, Recall: {res.metrics.recall}, F1: {res.metrics.f1_score}')"
```

The validation engine evaluates business rules against records without importing or accessing the `GroundTruth` table. Detection performance yields:
- **Precision:** 1.0 (0 false positives)
- **Recall:** 1.0 (0 false negatives)
- **F1 Score:** 1.0

---

## Underwriting AI Copilot

The Underwriting AI Copilot (`/ops/copilot`) assists operations analysts and underwriters by providing natural language explanations of quote decisions, risk assessments, rule exceptions, and coverage limits.

### Safety and Compliance Architecture

1. **Deterministic Authority:** LLMs never make underwriting decisions, approve or decline quotes, or modify premium values. All decisions are determined exclusively by Python engines in `backend/app/engines/`.
2. **Read-Only Context:** AI tools run with read-only database connections and cannot mutate database state.
3. **Anti-Hallucination Guard:** The output validation guard (`backend/app/ai/guard.py`) scans all responses against backend facts. Responses with fabricated record IDs, inconsistent numeric values, or unauthorized mutation claims are rejected.
4. **Deterministic Template Fallback:** If `GROQ_API_KEY` is not provided, or if the external API times out or experiences connectivity issues, the copilot automatically falls back to deterministic template generation (`backend/app/ai/templates.py`).
5. **Audit Logging:** Every copilot interaction is recorded in the append-only `ai_interactions` table with latency, model, token hashes, and guard status.
6. **AST Isolation:** Automated AST checks confirm that `backend/app/ai/` contains no imports or references to `GroundTruth`.

---

## Testing Procedures

The test suite consists of 137 backend tests and 18 frontend integration tests.

### Backend Test Suite

Execute the pytest suite from the `backend` directory:

```bash
cd backend
python -m pytest -q
```

Test coverage includes:
- Pure engine calculations: eligibility, risk assessment, premium breakdown, policy lifecycle transitions.
- Workflow actions: quote submission, acceptance, demo payment, policy issuance, endorsements, renewals.
- Anomaly injection and validation engine rules.
- API route authentication, RBAC boundaries, cross-customer isolation, and pagination.
- AI Copilot: intent classification, safe tools, anti-hallucination guard, AST isolation, and rate limiting.

### Frontend Test Suite

Execute the Vitest test suite from the `frontend` directory:

```bash
cd frontend
npm test
```

Test coverage includes:
- End-to-end customer journey: wizard prefill, submission, quote calculation, demo payment, and policy issuance.
- Operations console workflow: application review, manual referral approval, and endorsement management.
- Underwriting Copilot interface: chat session persistence, quick prompt chips, record deep-links, and error handling.

### TypeScript Compilation and Production Build

Verify strict TypeScript compliance and production asset compilation:

```bash
cd frontend
npm run typecheck
npm run build
```

---

## Project Architecture and Repository Map

### System Architecture

The platform is structured into five distinct operational layers:

1. **User Interfaces (React + Vite + TypeScript)**
   - **Customer Portal**: Multi-step application wizard with dynamic field rendering per product line, instant risk and premium calculation display, demo payment processing, and policyholder dashboard.
   - **Operations Console**: Comprehensive administrative workspace featuring underwriting queue management, manual referral review, endorsement approval, policy lifecycle tracking, data anomaly detection, and Underwriting AI Copilot chat.

2. **API and Security Layer (FastAPI)**
   - Role-based access control protecting customer and operations endpoints.
   - Demo session token management and cross-customer data isolation (`owner_key` filtering).
   - Dedicated route modules: `routes_customer.py`, `routes_ops.py`, `routes_ai.py`, `routes_data.py`, and `routes_auth.py`.

3. **Application and Workflow Services**
   - **Unified Workflow Service (`workflow.py`)**: Centralized state transition coordinator shared by the API and synthetic data generator.
   - **Evaluation Service (`evaluation.py`)**: Metrics calculation engine that evaluates validation findings against ground truth.
   - **AI Orchestration (`service.py`)**: Manages intent detection, safe context retrieval, anti-hallucination verification, and fallback handling.

4. **Deterministic Business Engines**
   - **Central Configuration (`rules_config.py`)**: Single source of truth for versioned rules, coverage limits, factor tables, and authority thresholds.
   - **Pure Calculation Engines**: `eligibility_engine.py`, `risk_engine.py`, `premium_engine.py`, `underwriting_engine.py`, `policy_engine.py`, and `validation_engine.py`. All engines are stateless and pure.

5. **Persistence and Relational Storage**
   - **SQLAlchemy 2.0 Entities**: 21 relational tables with foreign key constraints, bridge tables, and deterministic primary keys.
   - **Append-Only Event Tables**: `audit_events`, `policy_status_history`, and `ai_interactions` retain complete audit history without destructive updates.

### Repository Map

```
insureflow/
  backend/
    app/
      ai/                  # Underwriting AI Copilot (service, guard, prompts, templates, tools)
      api/                 # FastAPI endpoints (customer, ops, data, auth, AI routes)
      core/                # System settings, security, rules_config.py, enums, errors
      data_generator/      # Synthetic generator (pipeline, profiles, anomalies, export)
      database/            # SQLAlchemy database engine, session factory, base metadata
      engines/             # Deterministic engines (eligibility, risk, premium, policy, validation)
      models/              # Relational models and table definitions (21 entities)
      schemas/             # Pydantic v2 validation and response serialization schemas
      services/            # Workflow transitions, evaluation, deterministic ID generator
      main.py              # Application entrypoint, CORS configuration, lifespan events
    migrations/            # Alembic schema migrations (0001, 0002, 0003)
    scripts/               # Contract generator, rules documentation generator, demo CLI
    tests/                 # Backend test suite (137 tests)
    Dockerfile             # Production container build specification
    requirements.txt       # Python package dependencies
    alembic.ini            # Alembic environment and connection configuration
  frontend/
    src/
      api/                 # REST API client, TypeScript interfaces, error handling
      auth/                # Demo session context, role verification, token persistence
      components/          # In-repo UI kit, PolicyView modal, domain summary cards
      layouts/             # CustomerLayout and OpsLayout with navigation shell
      lib/                 # Formatters, authority level helpers, prefill utilities
      pages/
        customer/          # Customer portal views (Public, Apply, Quote, Account)
        ops/               # Ops console views (Overview, Records, Lifecycle, Governance, Copilot)
      App.tsx              # Application router, TanStack Query client setup
      main.tsx             # React application mount
    tests/                 # Vitest test suite (18 journey and UI integration tests)
    package.json           # Node.js dependencies and script definitions
    tsconfig.json          # Strict TypeScript configuration
    vite.config.ts         # Vite build configuration and development reverse proxy
  data/
    exports/               # Baseline generated exports (starter and full datasets)
  docs/                    # Project documentation, specifications, and reports
  render.yaml              # Render web service and database deployment blueprint
  .env.example             # Template for local environment configuration
  README.md                # Primary project documentation
```

---

## Utility Scripts and Contract Verification

The repository provides automated scripts for synchronizing contracts and documentation:

```bash
cd backend

# Regenerate API contract documentation and OpenAPI JSON specification
python -m scripts.generate_api_contract --write

# Regenerate business rules documentation directly from rules_config.py
python -m scripts.generate_business_rules_doc > ../docs/BUSINESS_RULES.md

# Regenerate data dictionary documentation directly from models
python -m scripts.generate_data_dictionary > ../docs/DATA_DICTIONARY.md

# Run interactive command-line workflow demonstration
python -m scripts.run_demo
```

---

## Troubleshooting

### 1. Port Conflicts

- **Issue:** `Error: [Errno 48] Address already in use: ('0.0.0.0', 8000)` or Vite port 5173 unavailable.
- **Resolution:**
  - Terminate processes using port 8000:
    - *Linux/macOS:* `lsof -ti:8000 | xargs kill -9`
    - *Windows (PowerShell):* `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force`
  - Or specify an alternative port for Uvicorn:
    `uvicorn app.main:app --port 8001`
    If changing the port, update `VITE_PROXY_TARGET` in `frontend/.env.example` accordingly.

### 2. Database Schema Drift or Locked Database

- **Issue:** `OperationalError: table ... has no column named ...` or `database is locked`.
- **Resolution:**
  - Run database migrations:
    ```bash
    cd backend
    alembic upgrade head
    ```
  - For local development reset, remove the SQLite database and re-initialize:
    ```bash
    rm backend/insureflow.db
    # Restart uvicorn to automatically re-seed baseline tables
    ```

### 3. Frontend Missing Dependencies or TypeScript Errors

- **Issue:** Module resolution failures or build errors during `npm run build`.
- **Resolution:**
  - Clear `node_modules` and re-install:
    ```bash
    cd frontend
    rm -rf node_modules package-lock.json
    npm install
    npm run typecheck
    ```

### 4. Copilot Fallback Activation

- **Issue:** Copilot responses display `Template Fallback` instead of `Groq API (Live LLM)`.
- **Resolution:**
  - Confirm that `GROQ_API_KEY` is present in `backend/.env` or the root `.env`.
  - Verify that the model specified in `GROQ_MODEL` is accessible (default: `openai/gpt-oss-20b`).
  - Check outgoing network connectivity to `https://api.groq.com`.
  - The fallback template engine operates deterministically when offline; no application crashes occur if external AI services are unavailable.

---

## Production Deployment Architecture Assessment

InsureFlow supports two validated production deployment topologies:

### Architecture Option 1: Managed Cloud Platform (Vercel + Render + Managed PostgreSQL)

- **Frontend Hosting (Vercel):**
  - High-performance global Edge CDN with automated HTTPS and instant cache invalidation.
  - Client-side routing is configured in `frontend/vercel.json` with SPA rewrite rules (`/(.*) -> /index.html`).
  - Communicates with the backend using the environment variable `VITE_API_BASE`.
- **Backend API Hosting (Render Web Service):**
  - Packaged as a Linux container via `backend/Dockerfile` running Python 3.12 and Uvicorn.
  - Automatic zero-downtime healthcheck polling at `/api/health`.
  - Automatic execution of database migrations (`alembic upgrade head`) on container startup.
- **Database (Managed PostgreSQL):**
  - Provisioned automatically as part of the Render infrastructure blueprint (`render.yaml`).
  - Connection pooling and relational constraints with psycopg2 dialect compatibility.
  - Survives application container rebuilds, redeployments, and service restarts.
- **AI Copilot Provider:**
  - Groq Cloud API (`openai/gpt-oss-20b`) for live natural language completions.
  - Automatic fallback to internal deterministic template engine if the external provider is offline.

### Architecture Option 2: Self-Hosted Container Stack (Docker Compose)

- Complete multi-container production stack orchestrated by root `docker-compose.yml`:
  - `db`: PostgreSQL 16 Alpine container with persistent named volume `postgres_data`.
  - `backend`: FastAPI container with automated migration execution and healthcheck validation.
  - `frontend`: Multi-stage build running Node 20 Alpine and served via Nginx Alpine on port 3000 (with built-in reverse proxy to backend).

---

## Production Deployment Execution

### Cloud Deployment (Vercel + Render)

Follow these steps to deploy InsureFlow to a publicly accessible cloud URL:

#### Step 1: Deploy Backend and Database on Render

1. Push your repository to a public or private GitHub repository.
2. Log into the [Render Dashboard](https://dashboard.render.com).
3. Click **New +** and select **Blueprint**.
4. Connect your GitHub repository. Render will automatically detect `render.yaml`.
5. Render will create two resources:
   - `insureflow-db`: Managed PostgreSQL database (Free tier).
   - `insureflow-api`: Docker web service configured with `/api/health` healthchecks.
6. Configure the following environment variables in the Render dashboard:
   - `STAFF_ACCESS_CODE`: Secret passcode for internal operations staff (e.g., `insureflow-demo`).
   - `GROQ_API_KEY`: *(Optional)* Your Groq API key to enable live LLM Copilot responses.
   - `CORS_ORIGINS`: Comma-separated list of allowed frontend origins (add your Vercel URL once generated).
7. Click **Apply**. Render will provision the database, execute `alembic upgrade head`, seed master data, and launch Uvicorn.
8. Copy your backend service URL (e.g., `https://insureflow-api.onrender.com`).

#### Step 2: Deploy Frontend on Vercel

1. Log into the [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** and select **Project**.
3. Import your GitHub repository.
4. In the project configuration:
   - **Framework Preset:** Vite.
   - **Root Directory:** Click Edit and select `frontend`.
5. Under **Environment Variables**, add:
   - `VITE_API_BASE`: The Render backend URL copied from Step 1 (e.g., `https://insureflow-api.onrender.com`).
6. Click **Deploy**. Vercel will run `npm run build` and output static assets to `dist/`.
7. Once deployed, copy your public frontend URL (e.g., `https://insureflow.vercel.app`).

#### Step 3: Finalize CORS Configuration

1. Return to the Render dashboard for `insureflow-api`.
2. Update the `CORS_ORIGINS` environment variable to include your Vercel URL:
   ```
   CORS_ORIGINS=http://localhost:5173,https://insureflow.vercel.app
   ```
3. Save changes. The backend will perform a zero-downtime restart.

---

### Self-Hosted Container Deployment (Docker Compose)

To run the complete production container stack locally or on a virtual private server (e.g., AWS EC2, DigitalOcean Droplet, Linode):

```bash
# Build and launch all three containers (database, backend, frontend) in detached mode
docker compose up --build -d

# Verify container status and health
docker compose ps

# Inspect backend logs
docker compose logs -f backend

# Seed full synthetic dataset inside the running container (optional)
docker compose exec backend python -m app.data_generator --scale full
```

Access endpoints:
- Customer Portal & Operations Console: `http://localhost:3000`
- Backend API & Swagger Documentation: `http://localhost:8000/docs`
- Healthcheck Endpoint: `http://localhost:8000/api/health`

To gracefully shut down the stack:

```bash
docker compose down
```

---

## Database Management, Backups, and Recovery

### Database Migration Management

All schema changes are tracked through Alembic migrations in `backend/migrations/versions/`:
- `0001_baseline_schema`: Relational schema for all core business entities.
- `0002_run_metadata_exceptions_ground_truth`: Data generation metadata and detected exception tracking.
- `0003_ai_interaction_table`: Append-only audit table for Underwriting Copilot interactions.

To apply migrations manually:

```bash
cd backend
alembic upgrade head
```

To roll back the most recent migration:

```bash
cd backend
alembic downgrade -1
```

### PostgreSQL Backup Procedure

To take a complete logical backup of the production database:

```bash
# Create custom-format compressed backup
pg_dump -h <DB_HOST> -U <DB_USER> -d insureflow -F c -b -v -f insureflow_backup.dump
```

### PostgreSQL Recovery Procedure

To restore the database from a backup file:

```bash
# Restore schema and data into target database
pg_restore -h <DB_HOST> -U <DB_USER> -d insureflow -v -c insureflow_backup.dump
```

---

## End-to-End Business Workflow Coverage

The platform implements the following verified workflows:

| Workflow Area | Status | Implementation Details |
|---|---|---|
| 1. Customer registration and auth | Complete (Verified) | Isolated browser session token generation (`/api/auth/demo-session`) with `owner_key` filtering. |
| 2. Customer application submission | Complete (Verified) | Product-specific quote wizards (`/api/customer/quotes`) for Motor, Property, and Commercial. |
| 3. Application validation | Complete (Verified) | Pure eligibility engine verifies asset values, age constraints, and mandatory fields. |
| 4. Underwriting and risk evaluation | Complete (Verified) | Weighted factor calculation producing risk scores and classification tiers (LOW, MEDIUM, HIGH). |
| 5. Application approval and rejection | Complete (Verified) | Deterministic outcome assignment (APPROVED, REFERRED, DECLINED, PENDING_INFORMATION). |
| 6. Policy issuance | Complete (Verified) | Atomic validation requiring active eligibility, approval, recorded customer acceptance, and demo payment. |
| 7. Policy retrieval and status updates | Complete (Verified) | Real-time policy lookup, mid-term endorsement requests, and policy lifecycle status tracking. |
| 8. Claim submission | Out of Scope | Not part of the Underwriting and Policy Lifecycle problem scope. Claims history is factored as an underwriting risk indicator (`previous_claims`), but post-issuance claims processing is unsupported. |
| 9. Claim review and processing | Out of Scope | Unsupported (see above). |
| 10. Operations console functionality | Complete (Verified) | 11 administrative pages including Underwriting Queue, Governance, Records, and Copilot. |
| 11. Role-based access restrictions | Complete (Verified) | Four distinct access tiers (`CUSTOMER`, `ANALYST`, `RISK_REVIEWER`, `ADMIN`) enforced by HTTP dependencies. |
| 12. Data persistence across sessions | Complete (Verified) | Persistent relational tables (SQLite / PostgreSQL) maintaining referential integrity across restarts. |

---

## Live Demonstration Runbook

### Demonstration Credentials and Roles

| Role | Access URL | Authentication Credentials | Primary Demonstration Focus |
|---|---|---|---|
| Demo Customer | `/login` | Click **Continue as demo customer** | Apply for insurance quote, review instant calculation, complete mock payment, view policy dashboard. |
| Operations Analyst | `/ops/login` | Select **Operations Analyst**, enter passcode `insureflow-demo` | Review underwriting referrals queue, approve quotes within standard authority limits, use Copilot for decision breakdown. |
| Risk Reviewer | `/ops/login` | Select **Risk Reviewer**, enter passcode `insureflow-demo` | Review high-risk applications, audit exceptions, verify governance checks. |
| Administrator | `/ops/login` | Select **Administrator**, enter passcode `insureflow-demo` | Senior underwriting approval, synthetic data generation, system validation engine execution. |

### Recommended Demonstration Sequence

1. **Step 1: Customer Quote Submission**
   - Navigate to `https://insureflow-six.vercel.app/login` (or `http://localhost:5173/login` locally) and sign in as Customer.
   - Click **Apply for Insurance** and select **Motor Comprehensive** (`PROD-001`).
   - Prefill application with sample values (Vehicle value: $35,000, 0 previous claims, clean record).
   - Review generated quote: note risk score calculation, factor breakdown, and transparent premium formula.
2. **Step 2: Acceptance and Demo Payment**
   - Click **Accept Quote**.
   - In the payment modal, select **Demonstration Payment**. Click **Simulate Failed Payment** to verify that no policy is issued without successful funds.
   - Click **Simulate Successful Payment**. Verify atomic policy issuance and note generated policy ID (`POL-2026-XXXXXX`).
3. **Step 3: Operations Console and Underwriting Review**
   - Open a separate browser tab or incognito window to `https://insureflow-six.vercel.app/ops/login` (or `http://localhost:5173/ops/login` locally).
   - Sign in as **Operations Analyst** with passcode `insureflow-demo`.
   - Observe immediate visibility of the newly issued customer policy on the **Overview** metrics dashboard.
   - Navigate to **Underwriting Center** (`/ops/underwriting`) to view applications flagged for manual referral.
4. **Step 4: Underwriting AI Copilot Exploration**
   - Navigate to `/ops/copilot`.
   - Select a prefilled prompt chip or enter: *"Why was QTE-2026-004001 declined?"*
   - Observe structured breakdown: eligibility violation reasons, risk score category, referenced record hyperlinks, and anti-hallucination disclaimers.
5. **Step 5: Governance and Anomaly Detection**
   - Sign in as **Risk Reviewer** on `/ops/login`.
   - Navigate to **Governance & Exceptions** (`/ops/governance`).
   - Review detected exceptions table. Filter by issue type (e.g., `POLICY_WITHOUT_ACCEPTANCE`, `PREMIUM_FORMULA_MISMATCH`).
   - Observe precision/recall metrics (F1 = 1.0) evaluated against separate ground truth.

### Demonstration Data Reset

To reset the demonstration environment to its clean baseline state:

```bash
cd backend
# Replaces current database with a fresh 4,000-quote full baseline dataset
python -m app.data_generator --scale full --db sqlite:///./insureflow.db --out ../data/exports/full
```

---

## Rollback and Disaster Recovery Procedures

1. **Frontend Rollback (Vercel):**
   - In the Vercel dashboard, select **Deployments**.
   - Locate the previous stable deployment and click **Promote to Production**. Rollback takes effect globally in under 5 seconds.
2. **Backend Container Rollback (Render):**
   - In the Render dashboard, navigate to `insureflow-api` -> **Deploys**.
   - Select any previous build and click **Rollback to this deploy**.
3. **Database Schema Rollback:**
   - Execute Alembic downgrade steps to revert table definitions:
     `alembic downgrade -1`
4. **Data Recovery:**
   - Restore the latest verified PostgreSQL backup using `pg_restore` as documented in the Database Management section.

---

## Known Limitations and Design Disclaimers

1. **Synthetic Data Only:** All customer profiles, asset valuations, and policy terms are procedurally generated. No real personally identifiable information (PII) is processed.
2. **Demonstration Payments:** Payment processing is simulated. No real credit card or banking data is collected, stored, or transmitted.
3. **Demo Session Authentication:** Session tokens are signed HMAC tokens intended for evaluation and demonstration. Production deployments with real user data should integrate with an enterprise identity provider (OAuth2, OIDC, or SAML).
4. **Claims Processing:** Claims lifecycle processing is out of scope. Claims history is evaluated purely as an underwriting risk factor.
5. **Live Cloud Deployment:** The platform is deployed live at `https://insureflow-six.vercel.app/` (frontend on Vercel) and `https://insureflow-api-tpmy.onrender.com` (backend on Render with PostgreSQL). Deployment manifests (`render.yaml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/vercel.json`, `docker-compose.yml`) remain available for reproducible staging or self-hosted deployments.

---

## Documentation Index

Detailed architectural guides, engine specifications, and verification reports are available in the `docs/` directory:

| Document | Purpose |
|---|---|
| `docs/AI_COPILOT.md` | Architecture, safety guard, prompt design, and provider fallback specifications for Underwriting Copilot. |
| `docs/ARCHITECTURE.md` | High-level system architecture, engine boundaries, and data flow. |
| `docs/API_CONTRACT.md` | Complete REST API endpoint reference and error envelope definitions. |
| `docs/BUSINESS_RULES.md` | Catalog of all product configurations, eligibility thresholds, factor tables, and authority matrices. |
| `docs/DATABASE_SCHEMA.md` | Entity-relationship diagrams, foreign key mappings, and lifecycle transition states. |
| `docs/DATA_DICTIONARY.md` | Comprehensive column-level data dictionary for all 21 database tables. |
| `docs/DATA_GENERATION.md` | Pipeline methodology for synthetic data creation, profiling, and anomaly generation. |
| `docs/DEMO_GUIDE.md` | Step-by-step evaluation walkthrough for customer and operations journeys. |
| `docs/FRONTEND.md` | Component hierarchy, state management, UI kit conventions, and testing approach. |
| `docs/PROJECT_STATUS.md` | Detailed implementation status and phase completion verification. |
| `docs/REPRODUCIBILITY_REPORT.md` | Checksums and multi-run comparison report demonstrating data generation determinism. |
| `docs/REQUIREMENTS_TRACEABILITY.md` | Mapping between original problem requirements and code implementation. |
| `docs/TEST_RESULTS.md` | Verified test run logs, assertion counts, and mutation testing results. |
| `docs/VALIDATION_REPORT.md` | Automated data quality checks, anomaly detection results, and precision/recall metrics. |
