from datetime import timedelta, timezone
from typing import Dict, List
from sqlalchemy.orm import Session
from .models import (
    Credential,
    Finding,
    Identity,
    IdentityType,
    RiskScore,
    RoleAssignment,
    RoleDefinition,
    ServicePrincipalOwner,
    Severity,
)
from .task_engine import TASK_MAPPING, create_task_if_needed
from .utils import now_utc, to_json


RULE_WEIGHTS = {
    "ORPHANED_USER": (Severity.MED, 10),
    "DISABLED_WITH_PRIVILEGE": (Severity.HIGH, 25),
    "PRIVILEGED_ROLE_ASSIGNED": (Severity.HIGH, 20),
    "STALE_PRIVILEGED_USER": (Severity.HIGH, 22),
    "SERVICE_PRINCIPAL_NO_OWNER": (Severity.MED, 12),
    "SERVICE_PRINCIPAL_SECRET_EXPIRING": (Severity.MED, 12),
    "SERVICE_PRINCIPAL_SECRET_EXPIRED": (Severity.HIGH, 20),
    "SERVICE_PRINCIPAL_TOO_MANY_CREDENTIALS": (Severity.MED, 10),
    "PRIVILEGE_SPRAWL": (Severity.HIGH, 18),
}


def run_analysis(db: Session) -> Dict[str, int]:
    now = now_utc()
    db.query(Finding).delete()
    db.query(RiskScore).delete()
    db.commit()

    identities = db.query(Identity).all()
    created_findings = 0
    for identity in identities:
        findings: List[Finding] = []
        drivers: List[str] = []
        score = 0

        role_assignments = (
            db.query(RoleAssignment, RoleDefinition)
            .join(RoleDefinition, RoleAssignment.role_definition_id == RoleDefinition.id)
            .filter(RoleAssignment.identity_id == identity.id)
            .all()
        )
        privileged_roles = [r for r in role_assignments if r[1].is_privileged]

        if identity.type == IdentityType.USER and identity.account_enabled and not identity.manager_entra_id:
            findings.append(_finding(identity.id, "ORPHANED_USER", {"manager": None}))

        if identity.account_enabled is False and privileged_roles:
            findings.append(
                _finding(
                    identity.id,
                    "DISABLED_WITH_PRIVILEGE",
                    {"privileged_roles": [r[1].display_name for r in privileged_roles]},
                )
            )

        if privileged_roles:
            findings.append(
                _finding(
                    identity.id,
                    "PRIVILEGED_ROLE_ASSIGNED",
                    {"roles": [r[1].display_name for r in privileged_roles]},
                )
            )

        last_signin = _to_aware(identity.last_signin_at)
        if privileged_roles and last_signin:
            if last_signin < now - timedelta(days=60):
                findings.append(
                    _finding(
                        identity.id,
                        "STALE_PRIVILEGED_USER",
                        {"last_signin_at": last_signin.isoformat()},
                    )
                )

        if identity.type == IdentityType.SERVICE_PRINCIPAL:
            owners = (
                db.query(ServicePrincipalOwner)
                .filter(ServicePrincipalOwner.service_principal_identity_id == identity.id)
                .count()
            )
            if owners == 0:
                findings.append(_finding(identity.id, "SERVICE_PRINCIPAL_NO_OWNER", {"owners": 0}))

            creds = db.query(Credential).filter(Credential.service_principal_identity_id == identity.id).all()
            active_creds = [
                c for c in creds if not c.expires_at or _to_aware(c.expires_at) > now
            ]
            if len(active_creds) > 3:
                findings.append(
                    _finding(identity.id, "SERVICE_PRINCIPAL_TOO_MANY_CREDENTIALS", {"count": len(active_creds)})
                )
            for cred in creds:
                expires_at = _to_aware(cred.expires_at)
                if expires_at and expires_at < now:
                    findings.append(
                        _finding(
                            identity.id,
                            "SERVICE_PRINCIPAL_SECRET_EXPIRED",
                            {"credential": cred.display_name, "expires_at": expires_at.isoformat()},
                        )
                    )
                elif expires_at and expires_at < now + timedelta(days=14):
                    findings.append(
                        _finding(
                            identity.id,
                            "SERVICE_PRINCIPAL_SECRET_EXPIRING",
                            {"credential": cred.display_name, "expires_at": expires_at.isoformat()},
                        )
                    )

        if len(privileged_roles) >= 2:
            findings.append(
                _finding(
                    identity.id,
                    "PRIVILEGE_SPRAWL",
                    {"roles": [r[1].display_name for r in privileged_roles]},
                )
            )

        for finding in findings:
            severity, weight = RULE_WEIGHTS[finding.code]
            finding.severity = severity
            finding.risk_score_delta = weight
            created_findings += 1
            score += weight
            drivers.append(finding.code)
            db.add(finding)
            task_info = TASK_MAPPING.get(finding.code)
            if task_info:
                create_task_if_needed(db, identity.id, task_info)

        score = min(score, 100)
        db.add(
            RiskScore(
                identity_id=identity.id,
                total_score=score,
                computed_at=now,
                drivers_json=to_json({"drivers": drivers}),
            )
        )

    db.commit()
    return {"findings": created_findings, "identities": len(identities)}


def _finding(identity_id: int, code: str, evidence: Dict) -> Finding:
    severity, weight = RULE_WEIGHTS[code]
    return Finding(
        identity_id=identity_id,
        code=code,
        severity=severity,
        title=code.replace("_", " ").title(),
        evidence_json=to_json(evidence),
        detected_at=now_utc(),
        risk_score_delta=weight,
    )


def _to_aware(value):
    if not value:
        return None
    if getattr(value, "tzinfo", None) is None:
        return value.replace(tzinfo=timezone.utc)
    return value
