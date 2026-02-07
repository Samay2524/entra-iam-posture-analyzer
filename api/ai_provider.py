import json
import os
from typing import Any, Dict, Optional
import requests
from sqlalchemy.orm import Session
from .models import AIPacket
from .utils import now_utc, to_json, from_json


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-3-27b-it")
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_ai_packet(
    db: Session,
    identity_id: int,
    payload: Dict[str, Any],
    task_id: Optional[int] = None,
) -> Dict[str, Any]:
    cached = get_latest_packet(db, identity_id, task_id)
    if cached:
        return cached

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from .env")

    instruction = (
        "You are an IAM review copilot. Return strict JSON only and follow this schema:\n"
        "{"
        '"summary":"",'
        '"top_risks":[""],'
        '"recommendation":"APPROVE|REVOKE|MODIFY|EXCEPTION|ESCALATE",'
        '"recommended_actions":[{"action":"","why":"","evidence":""}],'
        '"ticket_draft":{"title":"","description":"","acceptance_criteria":[""],"risk_statement":""},'
        '"questions_for_reviewer":[""]'
        "}\n"
        "Never include markdown or extra keys."
    )

    prompt = {"instruction": instruction, "payload": payload}
    content = [{"parts": [{"text": json.dumps(prompt, default=str)}]}]

    response, model_used = _call_gemini(api_key, content)
    packet = _parse_json(response)
    if packet is None:
        content = [
            {
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "instruction": "Return valid JSON only. No markdown. No extra keys.",
                                "payload": payload,
                            },
                            default=str,
                        )
                    }
                ]
            }
        ]
        response, model_used = _call_gemini(api_key, content)
        packet = _parse_json(response)
        if packet is None:
            raise RuntimeError("Failed to parse JSON from Gemini response")

    record = AIPacket(
        identity_id=identity_id,
        task_id=task_id,
        model=model_used,
        packet_json=to_json(packet),
        created_at=now_utc(),
    )
    db.add(record)
    db.commit()
    return {"packet": packet, "model": model_used, "created_at": record.created_at}


def get_latest_packet(db: Session, identity_id: int, task_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    cached = (
        db.query(AIPacket)
        .filter(AIPacket.identity_id == identity_id, AIPacket.task_id == task_id)
        .order_by(AIPacket.created_at.desc())
        .first()
    )
    if not cached:
        return None
    return {"packet": from_json(cached.packet_json), "model": cached.model, "created_at": cached.created_at}


def _call_gemini(api_key: str, content: list) -> tuple[Dict[str, Any], str]:
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-1.5-flash")
    for model in [GEMINI_MODEL, fallback_model]:
        url = f"{GEMINI_ENDPOINT}/{model}:generateContent?key={api_key}"
        resp = requests.post(
            url,
            json={
                "contents": content,
                "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"},
            },
        )
        if resp.ok:
            return resp.json(), model
        if resp.status_code in (400, 404) and model != fallback_model:
            # Try fallback model if the requested model isn't available
            continue
        resp.raise_for_status()
    raise RuntimeError("Failed to call Gemini API with both primary and fallback models")


def _parse_json(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        candidates = response.get("candidates", [])
        if not candidates:
            return None
        text = candidates[0]["content"]["parts"][0]["text"]
        cleaned = _extract_json_text(text)
        return json.loads(cleaned)
    except Exception:
        return None


def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.replace("json", "", 1).strip()
    # Try to find the first JSON object or array in the text
    start_obj = stripped.find("{")
    end_obj = stripped.rfind("}")
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        return stripped[start_obj : end_obj + 1]
    start_arr = stripped.find("[")
    end_arr = stripped.rfind("]")
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        return stripped[start_arr : end_arr + 1]
    return stripped
