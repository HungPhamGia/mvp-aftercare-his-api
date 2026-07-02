"""Smartbot BFF client: build the request server-side, read the SSE stream to
completion, assemble cards into one reply. Creds never reach the browser.

ponytail: the exact request/response shape is per the VNPT doc and may differ —
the raw exchange is logged once (SMARTBOT_DEBUG) so it can be confirmed.
"""
import json
import os

import httpx

from app.config import settings

DEBUG = os.getenv("SMARTBOT_DEBUG") == "1"


def _build_body(text: str, session_id: str, ma_ho_so: str, first_turn: bool) -> dict:
    body = {
        "bot_id": settings.BOT_ID,
        "sender_id": session_id,
        "session_id": session_id,
        "text": text,
        "input_channel": "api",
        "settings": {},
    }
    # Seed ma_ho_so only on the first turn of a session.
    if first_turn:
        body["metadata"] = {
            "button_variables": [{"variableName": "ma_ho_so", "value": str(ma_ho_so)}]
        }
    return body


def _assemble(events: list[dict]) -> dict:
    """Fold card_data from all collected events into one reply."""
    text_parts: list[str] = []
    quickreplies: list[str] = []
    handoff = False
    for ev in events:
        sb = (ev.get("object") or {}).get("sb") or {}
        for card in sb.get("card_data") or []:
            ctype = card.get("type")
            if ctype == "text":
                msg = card.get("text") or card.get("message") or card.get("value")
                if msg:
                    text_parts.append(msg)
            elif ctype == "quickreply":
                for opt in card.get("options") or card.get("buttons") or []:
                    label = opt.get("label") if isinstance(opt, dict) else opt
                    if label:
                        quickreplies.append(label)
            elif ctype == "chuyen_gdv":
                handoff = True
    return {"text": "\n".join(text_parts).strip(), "quickreplies": quickreplies, "handoff": handoff}


async def converse(text: str, session_id: str, ma_ho_so: str, first_turn: bool) -> dict:
    if not settings.smartbot_configured:
        # Stub so the Voicebot view works without VNPT creds.
        return {
            "text": f"[bot chưa cấu hình] Bạn vừa nói: “{text}”",
            "quickreplies": ["Tôi khỏe", "Tôi cần hỗ trợ"],
            "handoff": False,
        }

    body = _build_body(text, session_id, ma_ho_so, first_turn)
    headers = {
        "Authorization": f"Bearer {settings.SMARTBOT_ACCESS_TOKEN}",
        "Token-id": settings.SMARTBOT_TOKEN_ID,
        "Token-key": settings.SMARTBOT_TOKEN_KEY,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if DEBUG:
        print(f"[smartbot] -> {json.dumps(body, ensure_ascii=False)}", flush=True)

    events: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", settings.SMARTBOT_URL, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    payload = line[5:].strip() if line.startswith("data:") else line.strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        ev = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if DEBUG:
                        print(f"[smartbot] <- {payload}", flush=True)
                    events.append(ev)
                    status = ((ev.get("object") or {}).get("sb") or {}).get("card_data_info", {}).get("status")
                    if status in (0, 2):  # final
                        break
    except httpx.HTTPError as exc:
        # Upstream unreachable / auth failure — degrade instead of 500 so the
        # web UI stays usable. Real cause (e.g. 401) is logged for the operator.
        print(f"[smartbot] upstream error: {exc}", flush=True)
        return {
            "text": "Trợ lý tạm thời không phản hồi (lỗi kết nối tới Smartbot). "
                    "Vui lòng kiểm tra cấu hình BOT_ID/token.",
            "quickreplies": [], "handoff": False,
        }
    return _assemble(events)
