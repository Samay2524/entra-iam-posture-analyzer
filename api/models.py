import enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from .db import Base


class IdentityType(str, enum.Enum):
    USER = "USER"
    SERVICE_PRINCIPAL = "SERVICE_PRINCIPAL"


class SourceType(str, enum.Enum):
    GRAPH = "GRAPH"
    DEMO = "DEMO"


class PrivilegeLevel(str, enum.Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class Severity(str, enum.Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    CRIT = "CRIT"


class TaskType(str, enum.Enum):
    ACCESS_REVIEW = "ACCESS_REVIEW"
    REMEDIATE = "REMEDIATE"
    PAM_ONBOARD = "PAM_ONBOARD"
    ROTATE_SECRET = "ROTATE_SECRET"
    ASSIGN_OWNER = "ASSIGN_OWNER"
    DISABLE_ACCOUNT = "DISABLE_ACCOUNT"


class TaskPriority(str, enum.Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TaskStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    DONE = "DONE"
    ESCALATED = "ESCALATED"


class DecisionType(str, enum.Enum):
    APPROVE = "APPROVE"
    REVOKE = "REVOKE"
    MODIFY = "MODIFY"
    EXCEPTION = "EXCEPTION"
    ESCALATE = "ESCALATE"


class AuditEventType(str, enum.Enum):
    INGEST = "INGEST"
    FINDING_CREATED = "FINDING_CREATED"
    TASK_CREATED = "TASK_CREATED"
    AI_GENERATED = "AI_GENERATED"
    DECISION_RECORDED = "DECISION_RECORDED"
    EXPORT_CREATED = "EXPORT_CREATED"


class Identity(Base):
    __tablename__ = "identities"
    id = Column(Integer, primary_key=True)
    entra_object_id = Column(String, index=True, unique=True, nullable=False)
    type = Column(Enum(IdentityType), nullable=False)
    display_name = Column(String, nullable=False)
    upn = Column(String)
    account_enabled = Column(Boolean)
    created_at = Column(DateTime)
    manager_entra_id = Column(String)
    owner_team = Column(String)
    last_signin_at = Column(DateTime)
    source = Column(Enum(SourceType), nullable=False, default=SourceType.DEMO)

    findings = relationship("Finding", back_populates="identity")
    risk_scores = relationship("RiskScore", back_populates="identity")


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    entra_group_id = Column(String, index=True, unique=True, nullable=False)
    display_name = Column(String, nullable=False)


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    id = Column(Integer, primary_key=True)
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)


class RoleDefinition(Base):
    __tablename__ = "role_definitions"
    id = Column(Integer, primary_key=True)
    entra_role_definition_id = Column(String, index=True, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    is_privileged = Column(Boolean, default=False, nullable=False)
    privilege_level = Column(Enum(PrivilegeLevel), nullable=False, default=PrivilegeLevel.LOW)


class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    id = Column(Integer, primary_key=True)
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False)
    role_definition_id = Column(Integer, ForeignKey("role_definitions.id"), nullable=False)
    scope = Column(Text)
    assigned_at = Column(DateTime)


class ServicePrincipalOwner(Base):
    __tablename__ = "service_principal_owners"
    id = Column(Integer, primary_key=True)
    service_principal_identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False)
    owner_identity_id = Column(Integer, ForeignKey("identities.id"))
    owner_text = Column(String)


class Credential(Base):
    __tablename__ = "credentials"
    id = Column(Integer, primary_key=True)
    service_principal_identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False)
    cred_type = Column(String, nullable=False)
    display_name = Column(String)
    created_at = Column(DateTime)
    expires_at = Column(DateTime)


class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True)
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False)
    code = Column(String, nullable=False)
    severity = Column(Enum(Severity), nullable=False)
    title = Column(String, nullable=False)
    evidence_json = Column(Text, nullable=False)
    detected_at = Column(DateTime, nullable=False)
    risk_score_delta = Column(Integer, nullable=False)

    identity = relationship("Identity", back_populates="findings")


class RiskScore(Base):
    __tablename__ = "risk_scores"
    id = Column(Integer, primary_key=True)
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False)
    total_score = Column(Integer, nullable=False)
    computed_at = Column(DateTime, nullable=False)
    drivers_json = Column(Text, nullable=False)

    identity = relationship("Identity", back_populates="risk_scores")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    priority = Column(Enum(TaskPriority), nullable=False)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.OPEN)
    assignee = Column(String)
    due_date = Column(DateTime)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    decision = Column(Enum(DecisionType), nullable=False)
    justification = Column(Text)
    exception_expiry = Column(DateTime)
    decided_by = Column(String)
    decided_at = Column(DateTime, nullable=False)


class AIPacket(Base):
    __tablename__ = "ai_packets"
    id = Column(Integer, primary_key=True)
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    model = Column(String, nullable=False)
    packet_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, nullable=False)
    actor = Column(String, nullable=False)
    event_type = Column(Enum(AuditEventType), nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String)
    details_json = Column(Text)
