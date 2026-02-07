import os
import time
import logging
from typing import Dict, List, Optional, Tuple
import requests
import msal


GRAPH_BASE = "https://graph.microsoft.com/v1.0"
logger = logging.getLogger("graph_client")


class GraphPermissionError(Exception):
    """Raised when Graph returns 403 – Insufficient privileges."""
    def __init__(self, endpoint: str, detail: str):
        self.endpoint = endpoint
        self.detail = detail
        super().__init__(f"403 on {endpoint}: {detail}")


class GraphClient:
    def __init__(self):
        tenant_id = os.getenv("TENANT_ID")
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        if client_secret is not None and client_secret.strip() == "":
            client_secret = None
        if not tenant_id or not client_id:
            raise RuntimeError("TENANT_ID and CLIENT_ID must be set in .env")
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.scopes = [
            "User.Read.All",
            "Group.Read.All",
            "RoleManagement.Read.Directory",
            "Directory.Read.All",
            "Application.Read.All",
        ]
        self.cache_path = os.getenv("MSAL_CACHE_PATH", ".msal_cache.bin")
        self.cache = msal.SerializableTokenCache()
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r", encoding="utf-8") as handle:
                self.cache.deserialize(handle.read())

    def _build_app(self):
        if self.client_secret:
            return msal.ConfidentialClientApplication(
                self.client_id,
                client_credential=self.client_secret,
                authority=self.authority,
                token_cache=self.cache,
            )
        return msal.PublicClientApplication(self.client_id, authority=self.authority, token_cache=self.cache)

    def get_token(self) -> str:
        app = self._build_app()
        if self.client_secret:
            # Client credentials flow. MSAL caches tokens internally; clear cache
            # via /ingest/clear_cache if permissions were changed.
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            if "access_token" not in result:
                raise RuntimeError(f"Failed to acquire token: {result}")
            self._persist_cache()
            return result["access_token"]
        accounts = app.get_accounts()
        if accounts:
            silent = app.acquire_token_silent(self.scopes, account=accounts[0])
            if silent and "access_token" in silent:
                self._persist_cache()
                return silent["access_token"]
        flow = app.initiate_device_flow(scopes=self.scopes)
        if "user_code" not in flow:
            raise RuntimeError("Failed to start device flow")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Failed to acquire token: {result}")
        self._persist_cache()
        return result["access_token"]

    def _persist_cache(self) -> None:
        if self.cache.has_state_changed:
            with open(self.cache_path, "w", encoding="utf-8") as handle:
                handle.write(self.cache.serialize())

    def clear_cache(self) -> None:
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)
        # Reset in-memory cache
        self.cache = msal.SerializableTokenCache()

    def _headers(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def get_paginated(self, endpoint: str, token: str, params: Optional[dict] = None) -> List[dict]:
        url = f"{GRAPH_BASE}{endpoint}"
        items: List[dict] = []
        while url:
            resp = requests.get(url, headers=self._headers(token), params=params)
            if resp.status_code == 429:
                time.sleep(2)
                continue
            if resp.status_code == 403:
                raise GraphPermissionError(endpoint, resp.text)
            if not resp.ok:
                raise RuntimeError(f"Graph error {resp.status_code}: {resp.text}")
            data = resp.json()
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            params = None
        return items

    def get_single(self, endpoint: str, token: str) -> Optional[dict]:
        url = f"{GRAPH_BASE}{endpoint}"
        resp = requests.get(url, headers=self._headers(token))
        if resp.status_code == 404:
            return None
        if resp.status_code == 403:
            raise GraphPermissionError(endpoint, resp.text)
        if not resp.ok:
            raise RuntimeError(f"Graph error {resp.status_code}: {resp.text}")
        return resp.json()

    # ── Safe wrappers that return empty on 403 ────────────────────────
    def get_paginated_safe(self, endpoint: str, token: str, params: Optional[dict] = None) -> Tuple[List[dict], Optional[str]]:
        """Returns (items, error_msg|None). On 403, returns ([], error_msg)."""
        try:
            items = self.get_paginated(endpoint, token, params=params)
            return items, None
        except GraphPermissionError as exc:
            logger.warning("Permission denied on %s – skipping. Detail: %s", endpoint, exc.detail[:200])
            return [], f"403 on {endpoint}"

    def get_single_safe(self, endpoint: str, token: str) -> Tuple[Optional[dict], Optional[str]]:
        """Returns (data, error_msg|None). On 403 returns (None, error_msg)."""
        try:
            data = self.get_single(endpoint, token)
            return data, None
        except GraphPermissionError as exc:
            logger.warning("Permission denied on %s – skipping.", endpoint)
            return None, f"403 on {endpoint}"

    # ── Permission tester ─────────────────────────────────────────────
    def test_permissions(self, token: str) -> Dict[str, str]:
        """Try a lightweight call against each key endpoint and report pass/fail."""
        tests = {
            "User.Read.All": ("/users", {"$top": 1, "$select": "id"}),
            "Group.Read.All": ("/groups", {"$top": 1, "$select": "id"}),
            # roleDefinitions can be picky in some tenants; try minimal request first.
            "RoleManagement.Read.Directory": ("/roleManagement/directory/roleDefinitions", {"$top": 1}),
            "Application.Read.All": ("/servicePrincipals", {"$top": 1, "$select": "id"}),
            # Use organization as a minimal Directory.Read.All check
            "Directory.Read.All": ("/organization", {"$top": 1, "$select": "id"}),
        }
        results: Dict[str, str] = {}
        for perm_name, (endpoint, params) in tests.items():
            url = f"{GRAPH_BASE}{endpoint}"
            resp = requests.get(url, headers=self._headers(token), params=params)
            if not resp.ok and perm_name == "RoleManagement.Read.Directory":
                # Retry without params in case $top causes 400 in some tenants
                resp = requests.get(url, headers=self._headers(token))
            if resp.ok:
                results[perm_name] = "✅ OK"
            elif resp.status_code == 403:
                results[perm_name] = "❌ 403 – permission missing or no admin consent"
            else:
                snippet = resp.text[:120].replace("\n", " ")
                results[perm_name] = f"⚠️ {resp.status_code} – {snippet}"
        return results
