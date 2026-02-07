from datetime import timedelta
from typing import Dict
from sqlalchemy.orm import Session
from .models import Task, TaskPriority, TaskStatus, TaskType
from .utils import now_utc


TASK_MAPPING: Dict[str, Dict[str, str]] = {
    "SERVICE_PRINCIPAL_SECRET_EXPIRING": {"task_type": TaskType.ROTATE_SECRET, "priority": TaskPriority.P2},
    "SERVICE_PRINCIPAL_SECRET_EXPIRED": {"task_type": TaskType.ROTATE_SECRET, "priority": TaskPriority.P1},
    "SERVICE_PRINCIPAL_NO_OWNER": {"task_type": TaskType.ASSIGN_OWNER, "priority": TaskPriority.P1},
    "STALE_PRIVILEGED_USER": {"task_type": TaskType.ACCESS_REVIEW, "priority": TaskPriority.P1},
    "DISABLED_WITH_PRIVILEGE": {"task_type": TaskType.REMEDIATE, "priority": TaskPriority.P1},
    "PRIVILEGED_ROLE_ASSIGNED": {"task_type": TaskType.ACCESS_REVIEW, "priority": TaskPriority.P2},
}


def create_task_if_needed(db: Session, identity_id: int, task_info: Dict[str, str]) -> Task:
    existing = (
        db.query(Task)
        .filter(
            Task.identity_id == identity_id,
            Task.task_type == task_info["task_type"],
            Task.status != TaskStatus.DONE,
        )
        .first()
    )
    now = now_utc()
    if existing:
        existing.priority = task_info["priority"]
        existing.updated_at = now
        return existing
    task = Task(
        identity_id=identity_id,
        task_type=task_info["task_type"],
        priority=task_info["priority"],
        status=TaskStatus.OPEN,
        created_at=now,
        updated_at=now,
        due_date=now + timedelta(days=7),
    )
    db.add(task)
    return task
