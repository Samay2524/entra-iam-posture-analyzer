import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .ai_provider import generate_ai_packet, get_latest_packet
from .db import Base, engine, get_db
from .exports import (
    build_ticket_payload,
    export_pam_onboarding,
    export_ticket,
    list_exports,
    list_report_payloads,
)
from .ingest import demo_seed, run_graph_ingest
from .models import (
    AuditEvent,
    Decision,
    Finding,
    Identity,
    RoleAssignment,
    RoleDefinition,
    ServicePrincipalOwner,
    Credential,
    GroupMembership,
    Group,
    Task,
    TaskStatus,
)
from .risk_engine import run_analysis
from .schemas import DecisionCreate, TaskUpsert
from .utils import now_utc, to_json


load_dotenv()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Entra IAM Posture Analyzer + AI Review Copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _audit(db: Session, actor: str, event_type: str, entity_type: str, entity_id: Optional[str], details: Dict[str, Any]):
    db.add(
        AuditEvent(
            ts=now_utc(),
            actor=actor,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=to_json(details),
        )
    )


@app.post("/ingest/run")
def ingest_run(db: Session = Depends(get_db)):
    try:
        result = run_graph_ingest(db)
        _audit(db, "system", "INGEST", "REPORT", None, {"mode": "graph", "counts": result.get("counts", {})})
        db.commit()
        return {"status": "ok", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/ingest/test")
def ingest_test():
    """Test which Graph permissions the app actually has.
    Also decodes the JWT token to show what roles/permissions are embedded."""
    try:
        import base64, json as _json
        from .graph_client import GraphClient
        client = GraphClient()
        token = client.get_token()
        results = client.test_permissions(token)

        # Decode JWT payload (middle segment) to show granted roles + tenant/app info
        token_roles = []
        token_meta = {}
        try:
            payload_b64 = token.split(".")[1]
            # fix padding
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = _json.loads(base64.b64decode(payload_b64))
            token_roles = payload.get("roles", [])
            token_meta = {
                "appid": payload.get("appid"),
                "tid": payload.get("tid"),
                "aud": payload.get("aud"),
                "iss": payload.get("iss"),
            }
        except Exception:
            token_roles = ["(could not decode token)"]

        return {
            "status": "ok",
            "permissions": results,
            "token_roles": token_roles,
            "token_meta": token_meta,
            "hint": "If token_roles is empty, your app has NO Application permissions granted. "
                    "Go to Entra → App registrations → your app → API permissions → "
                    "Add permission → Microsoft Graph → Application permissions → "
                    "add User.Read.All, Group.Read.All, RoleManagement.Read.Directory, "
                    "Directory.Read.All, Application.Read.All → then click 'Grant admin consent'. "
                    "Also verify TENANT_ID/CLIENT_ID in .env match token_meta.tid/appid.",
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ingest/clear_cache")
def ingest_clear_cache():
    """Clear MSAL token cache so new permissions are picked up."""
    try:
        from .graph_client import GraphClient
        client = GraphClient()
        client.clear_cache()
        return {"status": "ok", "message": "MSAL cache cleared"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/reset")
def reset_db(db: Session = Depends(get_db)):
    """Drop and recreate all tables. Use when you need a clean slate."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return {"status": "ok", "message": "Database reset complete"}


@app.post("/ingest/demo_seed")
def ingest_demo(db: Session = Depends(get_db)):
    result = demo_seed(db)
    _audit(db, "system", "INGEST", "REPORT", None, {"mode": "demo", **result})
    db.commit()
    return {"status": "ok", "result": result}


@app.post("/analyze/run")
def analyze_run(db: Session = Depends(get_db)):
    result = run_analysis(db)
    _audit(db, "system", "FINDING_CREATED", "REPORT", None, result)
    db.commit()
    return {"status": "ok", "result": result}


@app.get("/identities")
def get_identities(
    identity_type: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Identity)
    if identity_type:
        query = query.filter(Identity.type == identity_type)
    if source:
        query = query.filter(Identity.source == source)
    identities = query.all()
    return [_identity_summary(db, identity) for identity in identities]


@app.get("/identities/{identity_id}")
def get_identity(identity_id: int, db: Session = Depends(get_db)):
    identity = db.query(Identity).filter(Identity.id == identity_id).first()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    return _identity_detail(db, identity)


@app.get("/identities/{identity_id}/findings")
def get_identity_findings(identity_id: int, db: Session = Depends(get_db)):
    findings = db.query(Finding).filter(Finding.identity_id == identity_id).all()
    return [
        {
            "id": finding.id,
            "code": finding.code,
            "severity": finding.severity,
            "title": finding.title,
            "evidence": finding.evidence_json,
            "detected_at": finding.detected_at,
        }
        for finding in findings
    ]


@app.get("/tasks")
def get_tasks(
    identity_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    task_type: Optional[str] = None,
    identity_type: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Task)
    if identity_id:
        query = query.filter(Task.identity_id == identity_id)
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if task_type:
        query = query.filter(Task.task_type == task_type)
    tasks = query.order_by(Task.priority.asc()).all()
    results = []
    for task in tasks:
        identity = db.query(Identity).filter(Identity.id == task.identity_id).first()
        finding_severities = (
            db.query(Finding.severity).filter(Finding.identity_id == task.identity_id).all()
        )
        max_severity = None
        if finding_severities:
            order = {"LOW": 1, "MED": 2, "HIGH": 3, "CRIT": 4}
            max_severity = max([sev[0] for sev in finding_severities], key=lambda s: order.get(s, 0))
        if identity_type and identity and identity.type != identity_type:
            continue
        if severity and max_severity != severity:
            continue
        results.append(
            {
                "id": task.id,
                "identity_id": task.identity_id,
                "identity_type": identity.type if identity else None,
                "max_severity": max_severity,
                "task_type": task.task_type,
                "priority": task.priority,
                "status": task.status,
                "assignee": task.assignee,
                "due_date": task.due_date,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            }
        )
    return results


@app.post("/tasks")
def upsert_task(payload: TaskUpsert, db: Session = Depends(get_db)):
    if payload.id:
        task = db.query(Task).filter(Task.id == payload.id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    else:
        task = Task(created_at=now_utc(), updated_at=now_utc())
        db.add(task)
    task.identity_id = payload.identity_id
    task.task_type = payload.task_type
    task.priority = payload.priority
    task.status = payload.status or task.status or TaskStatus.OPEN
    task.assignee = payload.assignee
    task.due_date = payload.due_date
    task.updated_at = now_utc()
    db.commit()
    _audit(db, "user", "TASK_CREATED", "TASK", str(task.id), {"task_type": task.task_type})
    db.commit()
    return {"status": "ok", "task_id": task.id}


@app.post("/tasks/{task_id}/decision")
def record_decision(task_id: int, payload: DecisionCreate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    decision = Decision(
        task_id=task_id,
        decision=payload.decision,
        justification=payload.justification,
        exception_expiry=payload.exception_expiry,
        decided_by=payload.decided_by or "reviewer",
        decided_at=now_utc(),
    )
    db.add(decision)
    task.status = TaskStatus.DONE if payload.decision in ["APPROVE", "REVOKE"] else task.status
    task.updated_at = now_utc()
    _audit(db, "user", "DECISION_RECORDED", "TASK", str(task_id), {"decision": payload.decision})
    db.commit()
    return {"status": "ok"}


@app.post("/ai/{identity_id}")
def generate_ai(identity_id: int, task_id: Optional[int] = None, db: Session = Depends(get_db)):
    identity = db.query(Identity).filter(Identity.id == identity_id).first()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    payload = _build_ai_payload(db, identity, task_id)
    result = generate_ai_packet(db, identity_id, payload, task_id=task_id)
    _audit(db, "system", "AI_GENERATED", "IDENTITY", str(identity_id), {"task_id": task_id})
    db.commit()
    return {
        "identity_id": identity_id,
        "task_id": task_id,
        "model": result["model"],
        "packet": result["packet"],
        "created_at": result["created_at"],
    }


@app.get("/ai/{identity_id}")
def get_ai(identity_id: int, db: Session = Depends(get_db)):
    identity = db.query(Identity).filter(Identity.id == identity_id).first()
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    packet = get_latest_packet(db, identity_id, task_id=None)
    if not packet:
        raise HTTPException(status_code=404, detail="No AI packet found")
    return {
        "identity_id": identity_id,
        "task_id": None,
        "model": packet["model"],
        "packet": packet["packet"],
        "created_at": packet["created_at"],
    }


@app.post("/export/ticket/{task_id}")
def export_ticket_endpoint(task_id: int, db: Session = Depends(get_db)):
    result = export_ticket(db, task_id)
    _audit(db, "system", "EXPORT_CREATED", "REPORT", str(task_id), {"file": result["file"]})
    db.commit()
    return {"status": "ok", "file": result["file"]}


@app.get("/export/ticket/{task_id}/preview")
def export_ticket_preview(task_id: int, db: Session = Depends(get_db)):
    try:
        payload = build_ticket_payload(db, task_id)
        return {"status": "ok", "payload": payload}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/export/files")
def export_files(db: Session = Depends(get_db)):
    export_pam_onboarding(db)
    return {"files": list_exports()}


@app.get("/export/reports")
def export_reports():
    return {"reports": list_report_payloads()}


@app.get("/reports/summary")
def report_summary(db: Session = Depends(get_db)):
    identities = db.query(Identity).count()
    high_risk = (
        db.query(Identity)
        .join(Finding, Finding.identity_id == Identity.id)
        .filter(Finding.severity.in_(["HIGH", "CRIT"]))
        .distinct()
        .count()
    )
    open_tasks = db.query(Task).filter(Task.status != TaskStatus.DONE).count()
    p1_tasks = db.query(Task).filter(Task.priority == "P1", Task.status != TaskStatus.DONE).count()
    top_findings = (
        db.query(Finding.code, Finding.severity)
        .group_by(Finding.code, Finding.severity)
        .all()
    )
    return {
        "identities": identities,
        "high_risk_identities": high_risk,
        "open_tasks": open_tasks,
        "p1_tasks": p1_tasks,
        "top_findings": [{"code": f[0], "severity": f[1]} for f in top_findings],
    }


@app.get("/audit")
def audit_events(db: Session = Depends(get_db)):
    events = db.query(AuditEvent).order_by(AuditEvent.ts.desc()).limit(200).all()
    return [
        {
            "id": event.id,
            "ts": event.ts,
            "actor": event.actor,
            "event_type": event.event_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "details": event.details_json,
        }
        for event in events
    ]


def _identity_summary(db: Session, identity: Identity) -> Dict[str, Any]:
    risk_score = (
        db.query(Finding)
        .filter(Finding.identity_id == identity.id)
        .count()
    )
    return {
        "id": identity.id,
        "display_name": identity.display_name,
        "type": identity.type,
        "upn": identity.upn,
        "account_enabled": identity.account_enabled,
        "risk_findings": risk_score,
    }


def _identity_detail(db: Session, identity: Identity) -> Dict[str, Any]:
    role_rows = (
        db.query(RoleAssignment, RoleDefinition)
        .join(RoleDefinition, RoleAssignment.role_definition_id == RoleDefinition.id)
        .filter(RoleAssignment.identity_id == identity.id)
        .all()
    )
    roles = [
        {
            "role": role_def.display_name,
            "privileged": role_def.is_privileged,
            "scope": assignment.scope,
        }
        for assignment, role_def in role_rows
    ]
    findings = db.query(Finding).filter(Finding.identity_id == identity.id).all()
    owners = (
        db.query(ServicePrincipalOwner)
        .filter(ServicePrincipalOwner.service_principal_identity_id == identity.id)
        .all()
    )
    credentials = (
        db.query(Credential)
        .filter(Credential.service_principal_identity_id == identity.id)
        .all()
    )
    return {
        "id": identity.id,
        "display_name": identity.display_name,
        "type": identity.type,
        "upn": identity.upn,
        "account_enabled": identity.account_enabled,
        "created_at": identity.created_at,
        "manager_entra_id": identity.manager_entra_id,
        "last_signin_at": identity.last_signin_at,
        "roles": roles,
        "owners": [
            {"owner_identity_id": owner.owner_identity_id, "owner_text": owner.owner_text} for owner in owners
        ],
        "credentials": [
            {
                "cred_type": cred.cred_type,
                "display_name": cred.display_name,
                "created_at": cred.created_at,
                "expires_at": cred.expires_at,
            }
            for cred in credentials
        ],
        "findings": [
            {
                "code": finding.code,
                "severity": finding.severity,
                "title": finding.title,
                "evidence": finding.evidence_json,
            }
            for finding in findings
        ],
    }


def _build_ai_payload(db: Session, identity: Identity, task_id: Optional[int] = None) -> Dict[str, Any]:
    role_rows = (
        db.query(RoleAssignment, RoleDefinition)
        .join(RoleDefinition, RoleAssignment.role_definition_id == RoleDefinition.id)
        .filter(RoleAssignment.identity_id == identity.id)
        .all()
    )
    findings = db.query(Finding).filter(Finding.identity_id == identity.id).all()
    owners = (
        db.query(ServicePrincipalOwner)
        .filter(ServicePrincipalOwner.service_principal_identity_id == identity.id)
        .all()
    )
    credentials = (
        db.query(Credential)
        .filter(Credential.service_principal_identity_id == identity.id)
        .all()
    )
    groups = (
        db.query(Group)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .filter(GroupMembership.identity_id == identity.id)
        .all()
    )
    task = db.query(Task).filter(Task.id == task_id).first() if task_id else None
    return {
        "identity": {
            "type": identity.type,
            "display_name": identity.display_name,
            "upn": identity.upn,
            "enabled": identity.account_enabled,
            "manager": identity.manager_entra_id,
            "owners": [
                {"owner_identity_id": owner.owner_identity_id, "owner_text": owner.owner_text} for owner in owners
            ],
            "last_signin_at": identity.last_signin_at,
        },
        "group_memberships": {"count": len(groups), "groups": [group.display_name for group in groups[:5]]},
        "role_assignments": [
            {"role": role_def.display_name, "privileged": role_def.is_privileged, "scope": assignment.scope}
            for assignment, role_def in role_rows
        ],
        "credentials": [
            {
                "cred_type": cred.cred_type,
                "display_name": cred.display_name,
                "created_at": cred.created_at,
                "expires_at": cred.expires_at,
            }
            for cred in credentials
        ],
        "findings": [
            {"code": finding.code, "severity": finding.severity, "evidence": finding.evidence_json}
            for finding in findings
        ],
        "risk_score": sum([finding.risk_score_delta for finding in findings]),
        "task": {
            "task_type": task.task_type if task else None,
            "priority": task.priority if task else None,
            "due_date": task.due_date if task else None,
        },
    }


@app.get("/")
def root():
    return {"status": "ok", "message": "Entra IAM Posture Analyzer API"}
