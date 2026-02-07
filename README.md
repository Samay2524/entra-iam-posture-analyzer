# Entra IAM Posture Analyzer + AI Review Copilot

This project is a local IAM posture analysis lab tool for Microsoft Entra ID tenants. It ingests identity/RBAC/service principal data, detects risky configurations with explainable rules, generates prioritized review tasks, and produces reviewer-friendly AI summaries without making any changes in Entra. The React UI uses Tailwind styling.

## What this solves
- Centralizes IAM posture insights (users, roles, service principals).
- Flags risky access and misconfigurations with explainable findings.
- Produces task queues for access reviews and remediation.
- Uses AI to accelerate human review and ticket drafting.

## Why this is different
- Deterministic rules + explainable findings (not a black box).
- AI outputs structured reviewer packets (consistent, auditable).
- Produces mock enterprise ticket artifacts for workflows.

## Architecture
```
                    +----------------------------+
                    |       React UI             |
                    |    (Tailwind CSS)          |
                    +-------------+--------------+
                                  |
                                  v
 +---------------------+    +-------------+     +----------------------+
 |  Entra Graph API    |<-->| FastAPI API |<--->| SQLite (MVP DB)       |
 +---------------------+    |  Ingest     |     | Postgres-ready schema |
                            |  Rules/AI   |     +----------------------+
                            |  Exports    |
                            +------+------+ 
                                   |
                                   v
                            connectors_out/
                            (mocked outputs)
```

## Setup (quick)
1) Copy `.env.example` to `.env` and set values.
2) Run with Docker:
```
docker compose up --build
```
3) Open UI at `http://localhost:8501` and use **Setup → Start**.

For a full step‑by‑step guide, see `SETUP.md`.

## Screenshots
Add 1–2 screenshots of the Dashboard + AI report view. This helps reviewers
understand the product without running it.

## Local dev (optional)
1) Create and activate a virtual environment:
```
python -m venv .venv
source .venv/bin/activate
```
2) Install dependencies:
```
pip install -r requirements.txt
```
3) Start the backend:
```
uvicorn api.main:app --reload
```
4) Start the UI:
```
cd web
npm install
npm run dev -- --host 0.0.0.0 --port 8501
```

Backend runs at `http://localhost:8000`.

## Repo layout
- `api/` FastAPI backend (Graph ingest, rules, AI, exports)
- `web/` React + Vite UI (current)
- `ui/` Legacy Streamlit UI (deprecated; not used)

## Required env vars
- `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` for Entra app-only auth.
- `GEMINI_API_KEY` for AI summaries.
- `DATABASE_URL` (defaults to SQLite).

## Graph permissions (read-only)
Required Microsoft Graph **Application permissions**:
- `User.Read.All`
- `Group.Read.All`
- `RoleManagement.Read.Directory`
- `Directory.Read.All`
- `Application.Read.All`
Grant admin consent after adding them.

## Demo flow
1) In Setup → Advanced options, click “Use Demo Data”.
2) Click “Generate Reports”.
3) Open Dashboard, pick an identity.
4) The AI summary and report are created automatically.
5) Reports are saved to `connectors_out/iam_report_<id>.json`.

## Roadmap
- Conditional Access policy checks
- PIM role assignments + activation windows
- Export formats: PDF/CSV
- Human approval workflows and audit trails

## Sample output
See `examples/iam_report_sample.json` for a sample report payload.

## Disclaimer
This is a lab prototype. It does not make production changes. AI recommendations are suggestions only; humans make the final access decisions. No automated removals are performed in Entra.

## License
MIT (see `LICENSE`).
