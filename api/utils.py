import json
from datetime import datetime, timezone
from typing import Any, Dict


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, default=str)


def from_json(payload: str) -> Dict[str, Any]:
    return json.loads(payload)


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
