from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


class TaskUpsert(BaseModel):
    id: Optional[int] = None
    identity_id: int
    task_type: str
    priority: str
    status: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None


class DecisionCreate(BaseModel):
    decision: str
    justification: Optional[str] = None
    exception_expiry: Optional[datetime] = None
    decided_by: Optional[str] = None


class AIPacketResponse(BaseModel):
    identity_id: int
    task_id: Optional[int]
    model: str
    packet: Any
    created_at: datetime


class ReportSummary(BaseModel):
    identities: int
    high_risk_identities: int
    open_tasks: int
    p1_tasks: int
    top_findings: List[dict]
