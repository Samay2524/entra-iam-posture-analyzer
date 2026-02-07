# Setup Guide (Entra IAM Posture Analyzer)

This guide is for first‑time setup so others can connect **their own Entra tenant** and run reports.

## 1) Create an Entra App (Application permissions)
1. Go to **Microsoft Entra admin center → App registrations → New registration**.
2. Name it (e.g., `Entra IAM Posture Analyzer`).
3. Click **Register**.

## 2) Add API permissions (Application)
1. Open the app → **API permissions → Add permission**.
2. Select **Microsoft Graph → Application permissions**.
3. Add these read‑only permissions:
   - `User.Read.All`
   - `Group.Read.All`
   - `RoleManagement.Read.Directory`
   - `Directory.Read.All`
   - `Application.Read.All`
4. Click **Grant admin consent**.

## 3) Create a Client Secret
1. Open the app → **Certificates & secrets**.
2. Create a **New client secret**.
3. Copy the **secret value** (not the ID).

## 4) Create `.env`
Copy `.env.example` to `.env` and set:
```
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
GEMINI_API_KEY=your-gemini-api-key
```

## 5) Run with Docker (recommended)
```
docker compose up --build
```
Open:
- UI: `http://localhost:8501`
- API: `http://localhost:8000`

## 6) Use the Setup tab
1. Click **Start (Verify → Sync → Generate)**.
2. Go to **Dashboard** and select an identity.
3. AI summary + report generate automatically.

## Reports
Generated reports are stored in:
```
connectors_out/iam_report_<id>.json
```
In the UI you can also download **All Reports (PDF)**.

## Notes
- This tool is **read‑only** for Entra.
- AI output is advisory and intended for human review.
