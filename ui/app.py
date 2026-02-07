import os
import json
import requests
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit.components.v1 import html


load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")


def tailwind_global_styles():
    html(
        """
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
        <style>
          :root {
            --bg: #f8fafc;
            --card: #ffffff;
            --ink: #0f172a;
            --muted: #64748b;
            --accent: #2563eb;
            --accent-dark: #1d4ed8;
            --border: #e2e8f0;
          }

          body { background-color: var(--bg); color: var(--ink); }
          .block-container { padding-top: 1.25rem; max-width: 1300px; }

          /* Sidebar */
          .stSidebar { background: #0b1220; }
          .stSidebar [data-testid="stSidebarNav"] { padding-top: 0.75rem; }
          .stSidebar .stRadio label,
          .stSidebar, .stSidebar div, .stSidebar p { color: #e2e8f0; }
          .stSidebar .stRadio div[role="radiogroup"] > label {
            background: #0f172a;
            border-radius: 10px;
            padding: 8px 12px;
            margin-bottom: 6px;
            border: 1px solid #1e293b;
          }

          /* Inputs + buttons */
          .stTextInput>div>div>input { border-radius: 0.6rem; border: 1px solid var(--border); }
          .stButton>button {
            border-radius: 0.75rem;
            font-weight: 600;
            border: 1px solid var(--accent);
            background: var(--accent);
            color: white;
            padding: 0.55rem 1rem;
          }
          .stButton>button:hover { background: var(--accent-dark); border-color: var(--accent-dark); }

          /* Cards + sections */
          .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 16px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
          }
          .card-title { font-weight: 700; font-size: 16px; margin-bottom: 6px; }
          .card-value { font-size: 22px; font-weight: 700; }
          .section-title { font-size: 20px; font-weight: 700; margin-bottom: 6px; }
          .section-sub { color: var(--muted); margin-bottom: 14px; }
          .hero {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0b1220 100%);
            color: white;
            border-radius: 16px;
            padding: 18px 20px;
            margin-bottom: 18px;
          }
          .hero-sub { color: #cbd5f5; font-size: 14px; }
          .stDataFrame { border-radius: 12px; overflow: hidden; }
        </style>
        """,
        height=0,
    )


def tailwind_header(title: str, subtitle: str):
    html(
        f"""
        <div class="hero">
            <div class="text-2xl font-semibold">{title}</div>
            <div class="hero-sub">{subtitle}</div>
        </div>
        """,
        height=120,
    )


def api_post(path: str, payload=None):
    try:
        resp = requests.post(f"{API_URL}{path}", json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        detail = ""
        if hasattr(exc, "response") and exc.response is not None:
            detail = exc.response.text
        st.error(f"API error: {exc} {detail}")
        return None


def api_get(path: str, params=None):
    try:
        resp = requests.get(f"{API_URL}{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        detail = ""
        if hasattr(exc, "response") and exc.response is not None:
            detail = exc.response.text
        st.error(f"API error: {exc} {detail}")
        return None


def section(title: str, subtitle: str = ""):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{subtitle}</div>', unsafe_allow_html=True)


def info_card(title: str, value: str, subtitle: str = ""):
    subtitle_html = f'<div class="section-sub" style="margin:6px 0 0;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'''
        <div class="card">
          <div class="card-title">{title}</div>
          <div class="card-value">{value}</div>
          {subtitle_html}
        </div>
        ''',
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="Entra IAM Posture Analyzer", layout="wide")
tailwind_global_styles()

page = st.sidebar.radio(
    "Navigation",
    ["Setup", "Dashboard", "Identity Detail", "Reports"],
)


if page == "Setup":
    tailwind_header("Entra IAM Posture Analyzer", "Connect, ingest, and analyze IAM posture")
    col1, col2, col3 = st.columns(3)
    with col1:
        info_card("Tenant ID", os.getenv("TENANT_ID", "—"))
    with col2:
        info_card("Client ID", os.getenv("CLIENT_ID", "—"))
    with col3:
        info_card("Gemini API Key", "Loaded" if os.getenv("GEMINI_API_KEY") else "Missing")

    st.markdown('<div class="section-title">Setup Flow</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Run these in order: test permissions → ingest → analyze.</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="card">
            <div class="card-title">Step 1 — Test Permissions</div>
            <div class="section-sub">Validate Graph access before ingest.</div>
          </div>
          <div class="card">
            <div class="card-title">Step 2 — Ingest Graph Data</div>
            <div class="section-sub">Pull identities, groups, roles, and apps.</div>
          </div>
          <div class="card">
            <div class="card-title">Step 3 — Run Analysis</div>
            <div class="section-sub">Create findings, scores, and tasks.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    colA, colB, colC = st.columns(3)
    with colA:
        if st.button("Run Test", use_container_width=True):
                test_result = api_get("/ingest/test")
                if test_result and "permissions" in test_result:
                    for perm, perm_status in test_result["permissions"].items():
                        if "✅" in perm_status:
                            st.success(f"{perm}: {perm_status}")
                        else:
                            st.error(f"{perm}: {perm_status}")
                    roles = test_result.get("token_roles", [])
                    token_meta = test_result.get("token_meta", {})
                    if roles:
                        st.info(f"**Token roles:** {', '.join(roles)}")
                    else:
                        st.error(
                            "⚠️ No roles in token. Add **Application** permissions + grant admin consent."
                        )
                    if token_meta:
                        st.caption(
                            f"Token meta → tid: {token_meta.get('tid')}, appid: {token_meta.get('appid')}"
                        )
                elif test_result:
                    st.json(test_result)
    with colB:
        if st.button("Run Ingestion", use_container_width=True):
            with st.spinner("Pulling data from Microsoft Graph..."):
                result = api_post("/ingest/run")
            if result:
                res = result.get("result", result)
                counts = res.get("counts", {})
                warnings = res.get("warnings", [])
                st.success(
                    f"✅ Ingested: {counts.get('users', 0)} users, "
                    f"{counts.get('groups', 0)} groups, "
                    f"{counts.get('role_assignments', 0)} role assignments, "
                    f"{counts.get('service_principals', 0)} service principals"
                )
                if warnings:
                    st.warning("⚠️ Some sections had permission issues (data was still ingested for the rest).")
                    for w in warnings:
                        st.caption(f"  • {w}")
    with colC:
        if st.button("Run Analysis", use_container_width=True):
            result = api_post("/analyze/run")
            if result:
                st.success(json.dumps(result, indent=2))

    with st.expander("Demo + Maintenance"):
        st.markdown('<div class="section-sub">Use demo data, clear tokens, or reset the database.</div>', unsafe_allow_html=True)
        colD, colE, colF = st.columns(3)
        with colD:
            if st.button("Use Demo Data", use_container_width=True):
                result = api_post("/ingest/demo_seed")
                if result:
                    st.success(json.dumps(result, indent=2))
        with colE:
            if st.button("Clear Token Cache", use_container_width=True):
                cleared = api_post("/ingest/clear_cache")
                if cleared:
                    st.success("Token cache cleared. Re-test permissions now.")
        with colF:
            if st.button("Reset Database", use_container_width=True):
                result = api_post("/reset")
                if result:
                    st.success("Database reset. You can now ingest data again.")


if page == "Dashboard":
    tailwind_header("Dashboard", "Prioritized tasks and risk overview")
    summary = api_get("/reports/summary")
    if not summary:
        st.stop()
    section("Overview", "Quick snapshot of risk and workload.")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        info_card("Identities", str(summary["identities"]))
    with col2:
        info_card("High/Critical", str(summary["high_risk_identities"]))
    with col3:
        info_card("Open Tasks", str(summary["open_tasks"]))
    with col4:
        info_card("P1 Tasks", str(summary["p1_tasks"]))

    section("Task Queue", "Filter and prioritize remediation work.")
    with st.expander("Filters"):
        filters = st.columns(5)
        status = filters[0].selectbox("Status", ["", "OPEN", "IN_REVIEW", "DONE", "ESCALATED"])
        priority = filters[1].selectbox("Priority", ["", "P1", "P2", "P3"])
        task_type = filters[2].selectbox(
            "Task Type",
            ["", "ACCESS_REVIEW", "REMEDIATE", "PAM_ONBOARD", "ROTATE_SECRET", "ASSIGN_OWNER", "DISABLE_ACCOUNT"],
        )
        identity_type = filters[3].selectbox("Identity Type", ["", "USER", "SERVICE_PRINCIPAL"])
        severity = filters[4].selectbox("Severity", ["", "LOW", "MED", "HIGH", "CRIT"])
    tasks = api_get(
        "/tasks",
        params={
            "status": status or None,
            "priority": priority or None,
            "task_type": task_type or None,
            "identity_type": identity_type or None,
            "severity": severity or None,
        },
    )
    if not tasks:
        st.stop()
    st.dataframe(pd.DataFrame(tasks))


if page == "Identity Detail":
    tailwind_header("Identity Detail", "Review identity posture and AI copilot")
    identities = api_get("/identities")
    if not identities:
        st.stop()
    identity_map = {f"{item['display_name']} ({item['id']})": item["id"] for item in identities}
    selected = st.selectbox("Select Identity", list(identity_map.keys())) if identity_map else None
    if selected:
        identity_id = identity_map[selected]
        details = api_get(f"/identities/{identity_id}")
        if details:
            section("Identity Overview", "Key attributes and risk context.")
            colA, colB, colC = st.columns(3)
            with colA:
                info_card("Name", details.get("display_name", "—"))
            with colB:
                info_card("Type", details.get("type", "—"))
            with colC:
                info_card("UPN", details.get("upn") or "—")

            colD, colE, colF, colG = st.columns(4)
            with colD:
                info_card("Enabled", str(details.get("account_enabled")))
            with colE:
                info_card("Roles", str(len(details.get("roles", []))))
            with colF:
                info_card("Findings", str(len(details.get("findings", []))))
            with colG:
                info_card("Credentials", str(len(details.get("credentials", []))))

        tab1, tab2, tab3 = st.tabs(["Task Actions", "AI Copilot", "Decisions & Export"])
        with tab1:
            section("Task Actions", "Create or update remediation work.")
            task_type = st.selectbox(
                "Task Type",
                ["ACCESS_REVIEW", "REMEDIATE", "PAM_ONBOARD", "ROTATE_SECRET", "ASSIGN_OWNER", "DISABLE_ACCOUNT"],
            )
            priority = st.selectbox("Priority", ["P1", "P2", "P3"])
            status = st.selectbox("Status", ["OPEN", "IN_REVIEW", "DONE", "ESCALATED"])
            assignee = st.text_input("Assignee")
            if st.button("Create/Update Task"):
                payload = {
                    "identity_id": identity_id,
                    "task_type": task_type,
                    "priority": priority,
                    "status": status,
                    "assignee": assignee or None,
                }
                result = api_post("/tasks", payload=payload)
                if result:
                    st.success(result)
        with tab2:
            section("AI Copilot", "Generate reviewer-ready summaries and ticket drafts.")
            if st.button("Generate AI Packet"):
                packet = api_post(f"/ai/{identity_id}")
                if packet:
                    st.json(packet["packet"])
        with tab3:
            section("Decision", "Record reviewer decisions and create exports.")
            decision = st.selectbox("Decision", ["APPROVE", "REVOKE", "MODIFY", "EXCEPTION", "ESCALATE"])
            justification = st.text_area("Justification")
            decision_task_id = st.text_input("Task ID for Decision")
            if st.button("Mark Task Done / Escalate"):
                if decision_task_id:
                    result = api_post(
                        f"/tasks/{decision_task_id}/decision",
                        payload={"decision": decision, "justification": justification or None},
                    )
                    if result:
                        st.success(result)
            task_id = st.text_input("Task ID for Ticket Export (optional)")
            if st.button("Generate Ticket JSON"):
                if task_id:
                    result = api_post(f"/export/ticket/{task_id}")
                    if result:
                        st.success(result)


if page == "Reports":
    tailwind_header("Reports", "Audit-ready exports and logs")
    tab1, tab2 = st.tabs(["Audit Events", "Exports"])
    with tab1:
        section("Audit Events", "Recent activity across ingest, analysis, and decisions.")
        events = api_get("/audit")
        if events:
            st.dataframe(pd.DataFrame(events))
    with tab2:
        section("Exports", "Mock integration outputs.")
        files = api_get("/export/files")
        if files:
            st.json(files)
