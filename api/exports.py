import json
import os
from typing import Dict, List
from sqlalchemy.orm import Session
from .ai_provider import get_latest_packet
from .models import Finding, Task, TaskType
from .utils import now_utc


EXPORT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "connectors_out"))


def ensure_export_dir() -> None:
    os.makedirs(EXPORT_DIR, exist_ok=True)


def build_ticket_payload(db: Session, task_id: int) -> Dict[str, str]:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise RuntimeError("Task not found")
    findings = db.query(Finding).filter(Finding.identity_id == task.identity_id).all()
    packet = get_latest_packet(db, task.identity_id, task_id=None)
    payload = {
        "title": f"Remediation for task {task.id}",
        "description": f"Task type: {task.task_type}. Priority: {task.priority}.",
        "acceptance_criteria": ["Validate risk drivers", "Document approval/revocation"],
        "risk_statement": "IAM risks detected in Entra tenant.",
        "identity_id": task.identity_id,
        "finding_ids": [finding.id for finding in findings],
        "generated_at": now_utc().isoformat(),
        "mocked": True,
    }
    if packet and packet.get("packet"):
        ai = packet["packet"]
        payload["ai_summary"] = ai.get("summary")
        payload["ai_recommendation"] = ai.get("recommendation")
        payload["ai_recommended_actions"] = ai.get("recommended_actions")
        payload["ai_ticket_draft"] = ai.get("ticket_draft")
    return payload


def export_ticket(db: Session, task_id: int) -> Dict[str, str]:
    ensure_export_dir()
    payload = build_ticket_payload(db, task_id)
    file_path = os.path.join(EXPORT_DIR, f"iam_report_{task_id}.json")
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2))
    return {"file": file_path}


def export_pam_onboarding(db: Session) -> None:
    ensure_export_dir()
    tasks = db.query(Task).filter(Task.task_type == TaskType.PAM_ONBOARD).all()
    for task in tasks:
        file_path = os.path.join(EXPORT_DIR, f"pam_onboarding_{task.identity_id}.json")
        if os.path.exists(file_path):
            continue
        payload = {
            "identity_id": task.identity_id,
            "task_id": task.id,
            "created_at": now_utc().isoformat(),
            "mocked": True,
            "note": "PAM onboarding output (mocked)",
        }
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2))


def list_exports() -> List[str]:
    ensure_export_dir()
    return sorted(os.listdir(EXPORT_DIR))


def list_report_payloads() -> List[Dict[str, str]]:
    ensure_export_dir()
    reports: List[Dict[str, str]] = []
    for name in sorted(os.listdir(EXPORT_DIR)):
        if not name.startswith("iam_report_") or not name.endswith(".json"):
            continue
        path = os.path.join(EXPORT_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            payload["file"] = name
            reports.append(payload)
        except Exception:
            continue
    return reports
