import logging
import random
from datetime import timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from .graph_client import GraphClient, GraphPermissionError
from .models import (
    Credential,
    Group,
    GroupMembership,
    Identity,
    IdentityType,
    RoleAssignment,
    RoleDefinition,
    ServicePrincipalOwner,
    SourceType,
)
from .models import PrivilegeLevel
from .utils import now_utc, parse_dt


logger = logging.getLogger("ingest")

PRIVILEGED_ROLE_NAMES = {
    "Global Administrator",
    "Privileged Role Administrator",
    "Security Administrator",
    "User Administrator",
    "Application Administrator",
}


def _upsert_identity(db: Session, entra_id: str, defaults: Dict) -> Identity:
    identity = db.query(Identity).filter(Identity.entra_object_id == entra_id).first()
    if identity:
        for key, value in defaults.items():
            setattr(identity, key, value)
        return identity
    identity = Identity(entra_object_id=entra_id, **defaults)
    db.add(identity)
    return identity


def run_graph_ingest(db: Session) -> Dict:
    """Pull data from Graph.  Each section is independent – a 403 on one
    section will NOT crash the whole ingestion.  Instead we collect warnings
    and return them so the UI can tell the user what's missing."""

    client = GraphClient()
    token = client.get_token()

    counts: Dict[str, int] = {}
    warnings: List[str] = []
    user_map: Dict[str, Identity] = {}
    group_map: Dict[str, Group] = {}

    # ── 1. USERS ──────────────────────────────────────────────────────
    try:
        user_items: List[dict] = []
        # Try with signInActivity first
        user_select = "id,displayName,userPrincipalName,accountEnabled,createdDateTime,signInActivity"
        try:
            user_items = client.get_paginated("/users", token, params={"$select": user_select})
        except (GraphPermissionError, RuntimeError) as exc:
            if "403" in str(exc) or "Insufficient privileges" in str(exc):
                logger.warning("signInActivity needs extra license – retrying without it")
                user_items = client.get_paginated(
                    "/users", token,
                    params={"$select": "id,displayName,userPrincipalName,accountEnabled,createdDateTime"},
                )
            else:
                raise

        for user in user_items:
            # Manager lookup (safe – skip on 403)
            manager, mgr_err = client.get_single_safe(f"/users/{user['id']}/manager", token)
            if mgr_err and "403" not in ";".join(warnings):
                warnings.append(f"Could not read user managers ({mgr_err})")

            identity = _upsert_identity(
                db,
                user["id"],
                {
                    "type": IdentityType.USER,
                    "display_name": user.get("displayName") or "Unknown User",
                    "upn": user.get("userPrincipalName"),
                    "account_enabled": user.get("accountEnabled"),
                    "created_at": parse_dt(user.get("createdDateTime")),
                    "manager_entra_id": manager.get("id") if manager else None,
                    "last_signin_at": parse_dt(
                        user.get("signInActivity", {}).get("lastSignInDateTime")
                    ) if isinstance(user.get("signInActivity"), dict) else None,
                    "source": SourceType.GRAPH,
                },
            )
            user_map[user["id"]] = identity

        counts["users"] = len(user_items)
        logger.info("Ingested %d users", len(user_items))
    except GraphPermissionError as exc:
        warnings.append(f"Users: {exc}")
        counts["users"] = 0
        logger.error("Cannot read users: %s", exc)
    except RuntimeError as exc:
        warnings.append(f"Users: {exc}")
        counts["users"] = 0
        logger.error("Cannot read users: %s", exc)

    db.flush()

    # ── 2. GROUPS + MEMBERS ───────────────────────────────────────────
    try:
        group_items, grp_err = client.get_paginated_safe(
            "/groups", token, params={"$select": "id,displayName"},
        )
        if grp_err:
            warnings.append(f"Groups: {grp_err}")
        for group in group_items:
            group_row = db.query(Group).filter(Group.entra_group_id == group["id"]).first()
            if not group_row:
                group_row = Group(
                    entra_group_id=group["id"],
                    display_name=group.get("displayName") or "Unnamed Group",
                )
                db.add(group_row)
            else:
                group_row.display_name = group.get("displayName") or group_row.display_name
            group_map[group["id"]] = group_row

        db.flush()

        for group in group_items:
            members, mem_err = client.get_paginated_safe(
                f"/groups/{group['id']}/members", token,
            )
            if mem_err and "group members" not in ";".join(warnings):
                warnings.append(f"Group members: {mem_err}")
            group_row = group_map[group["id"]]
            for member in members:
                if member.get("@odata.type") != "#microsoft.graph.user":
                    continue
                identity = user_map.get(member["id"])
                if not identity:
                    continue
                exists = (
                    db.query(GroupMembership)
                    .filter(
                        GroupMembership.identity_id == identity.id,
                        GroupMembership.group_id == group_row.id,
                    )
                    .first()
                )
                if not exists:
                    db.add(GroupMembership(identity_id=identity.id, group_id=group_row.id))

        counts["groups"] = len(group_items)
        logger.info("Ingested %d groups", len(group_items))
    except Exception as exc:
        warnings.append(f"Groups: {exc}")
        counts["groups"] = 0
        logger.error("Groups section failed: %s", exc)

    db.flush()

    # ── 3. ROLE DEFINITIONS + ASSIGNMENTS ─────────────────────────────
    try:
        role_defs, rd_err = client.get_paginated_safe(
            "/roleManagement/directory/roleDefinitions", token,
        )
        if rd_err:
            warnings.append(f"Role definitions: {rd_err}")

        role_def_map: Dict[str, RoleDefinition] = {}
        for role_def in role_defs:
            is_priv = role_def.get("displayName") in PRIVILEGED_ROLE_NAMES
            role_row = (
                db.query(RoleDefinition)
                .filter(RoleDefinition.entra_role_definition_id == role_def["id"])
                .first()
            )
            if not role_row:
                role_row = RoleDefinition(
                    entra_role_definition_id=role_def["id"],
                    display_name=role_def.get("displayName") or "Unnamed Role",
                    is_privileged=is_priv,
                    privilege_level=PrivilegeLevel.HIGH if is_priv else PrivilegeLevel.LOW,
                )
                db.add(role_row)
            else:
                role_row.display_name = role_def.get("displayName") or role_row.display_name
                role_row.is_privileged = is_priv
            role_def_map[role_def["id"]] = role_row

        db.flush()

        role_assignments, ra_err = client.get_paginated_safe(
            "/roleManagement/directory/roleAssignments", token,
        )
        if ra_err:
            warnings.append(f"Role assignments: {ra_err}")

        ra_count = 0
        for assignment in role_assignments:
            identity = user_map.get(assignment.get("principalId"))
            if not identity:
                continue
            role_row = role_def_map.get(assignment.get("roleDefinitionId"))
            if not role_row:
                continue
            exists = (
                db.query(RoleAssignment)
                .filter(
                    RoleAssignment.identity_id == identity.id,
                    RoleAssignment.role_definition_id == role_row.id,
                    RoleAssignment.scope == assignment.get("directoryScopeId"),
                )
                .first()
            )
            if not exists:
                db.add(
                    RoleAssignment(
                        identity_id=identity.id,
                        role_definition_id=role_row.id,
                        scope=assignment.get("directoryScopeId"),
                        assigned_at=parse_dt(assignment.get("createdDateTime")),
                    )
                )
                ra_count += 1

        counts["role_definitions"] = len(role_defs)
        counts["role_assignments"] = ra_count
        logger.info("Ingested %d role defs, %d assignments", len(role_defs), ra_count)
    except Exception as exc:
        warnings.append(f"Roles: {exc}")
        counts["role_definitions"] = 0
        counts["role_assignments"] = 0
        logger.error("Roles section failed: %s", exc)

    db.flush()

    # ── 4. SERVICE PRINCIPALS + CREDS + OWNERS ────────────────────────
    try:
        service_principals, sp_err = client.get_paginated_safe(
            "/servicePrincipals", token,
            params={"$select": "id,displayName,appId,passwordCredentials,keyCredentials"},
        )
        if sp_err:
            warnings.append(f"Service principals: {sp_err}")

        for sp in service_principals:
            identity = _upsert_identity(
                db,
                sp["id"],
                {
                    "type": IdentityType.SERVICE_PRINCIPAL,
                    "display_name": sp.get("displayName") or "Unnamed Service Principal",
                    "upn": None,
                    "account_enabled": None,
                    "created_at": None,
                    "manager_entra_id": None,
                    "owner_team": None,
                    "last_signin_at": None,
                    "source": SourceType.GRAPH,
                },
            )
            # Owners (safe)
            owners, ow_err = client.get_paginated_safe(
                f"/servicePrincipals/{sp['id']}/owners", token,
            )
            if ow_err and "SP owners" not in ";".join(warnings):
                warnings.append(f"SP owners: {ow_err}")
            for owner in owners:
                owner_identity = user_map.get(owner.get("id"))
                db.add(
                    ServicePrincipalOwner(
                        service_principal_identity_id=identity.id,
                        owner_identity_id=owner_identity.id if owner_identity else None,
                        owner_text=None if owner_identity else owner.get("displayName"),
                    )
                )
            # Password credentials
            for cred in sp.get("passwordCredentials", []):
                db.add(
                    Credential(
                        service_principal_identity_id=identity.id,
                        cred_type="PASSWORD",
                        display_name=cred.get("displayName"),
                        created_at=parse_dt(cred.get("startDateTime")),
                        expires_at=parse_dt(cred.get("endDateTime")),
                    )
                )
            # Key credentials
            for cred in sp.get("keyCredentials", []):
                db.add(
                    Credential(
                        service_principal_identity_id=identity.id,
                        cred_type="CERT",
                        display_name=cred.get("displayName"),
                        created_at=parse_dt(cred.get("startDateTime")),
                        expires_at=parse_dt(cred.get("endDateTime")),
                    )
                )

        counts["service_principals"] = len(service_principals)
        logger.info("Ingested %d service principals", len(service_principals))
    except Exception as exc:
        warnings.append(f"Service principals: {exc}")
        counts["service_principals"] = 0
        logger.error("Service principals section failed: %s", exc)

    db.commit()
    return {"counts": counts, "warnings": warnings}


# ── Demo seed ─────────────────────────────────────────────────────────

def demo_seed(db: Session) -> Dict[str, int]:
    now = now_utc()
    user_rows = []
    for idx in range(1, 6):
        identity = _upsert_identity(
            db,
            f"demo-user-{idx}",
            {
                "type": IdentityType.USER,
                "display_name": f"Demo User {idx}",
                "upn": f"demo{idx}@example.com",
                "account_enabled": idx % 2 == 0,
                "created_at": now - timedelta(days=120 + idx),
                "manager_entra_id": None if idx == 1 else "demo-user-1",
                "owner_team": None,
                "last_signin_at": now - timedelta(days=10 * idx),
                "source": SourceType.DEMO,
            },
        )
        user_rows.append(identity)

    db.flush()  # ensure user IDs are assigned

    # Upsert group
    group = db.query(Group).filter(Group.entra_group_id == "demo-group-1").first()
    if not group:
        group = Group(entra_group_id="demo-group-1", display_name="Demo Admin Group")
        db.add(group)
        db.flush()
    existing_gm = (
        db.query(GroupMembership)
        .filter(GroupMembership.identity_id == user_rows[0].id, GroupMembership.group_id == group.id)
        .first()
    )
    if not existing_gm:
        db.add(GroupMembership(identity_id=user_rows[0].id, group_id=group.id))

    # Upsert role definition
    role_def = db.query(RoleDefinition).filter(
        RoleDefinition.entra_role_definition_id == "demo-role-global-admin"
    ).first()
    if not role_def:
        role_def = RoleDefinition(
            entra_role_definition_id="demo-role-global-admin",
            display_name="Global Administrator",
            is_privileged=True,
            privilege_level="HIGH",
        )
        db.add(role_def)
        db.flush()
    existing_ra = (
        db.query(RoleAssignment)
        .filter(
            RoleAssignment.identity_id == user_rows[0].id,
            RoleAssignment.role_definition_id == role_def.id,
        )
        .first()
    )
    if not existing_ra:
        db.add(
            RoleAssignment(
                identity_id=user_rows[0].id,
                role_definition_id=role_def.id,
                scope="/",
                assigned_at=now - timedelta(days=90),
            )
        )

    sp_identity = _upsert_identity(
        db,
        "demo-sp-1",
        {
            "type": IdentityType.SERVICE_PRINCIPAL,
            "display_name": "Demo App Service Principal",
            "upn": None,
            "account_enabled": None,
            "created_at": now - timedelta(days=300),
            "manager_entra_id": None,
            "owner_team": "Platform",
            "last_signin_at": None,
            "source": SourceType.DEMO,
        },
    )
    db.flush()  # ensure sp_identity.id is populated before FK reference
    db.add(
        Credential(
            service_principal_identity_id=sp_identity.id,
            cred_type="PASSWORD",
            display_name="demo-secret-1",
            created_at=now - timedelta(days=80),
            expires_at=now + timedelta(days=random.randint(-5, 10)),
        )
    )
    db.commit()
    return {"identities": len(user_rows) + 1, "groups": 1}
