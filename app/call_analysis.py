"""Summarise a finished follow-up call and classify its risk tier.

Uses GPT when OPENAI_API_KEY is set; falls back to a keyword heuristic so the
demo still classifies offline (or when the key is out of quota).

ponytail: heuristic keyword lists, not a model — good enough to drive the demo
tier colour; the GPT path is the real one.
"""
import json

from app.config import settings

RED_KW = [
    "chảy dịch", "chảy mủ", " mủ", "khó thở", "đau ngực", "chảy máu",
    "huyết khối", "tím", "39°", "39 độ", "38.5", "38.6", "38.7", "38.8", "38.9",
    "ngất", "co giật", "lơ mơ",
]
AMBER_KW = [
    "sốt", "đau tăng", "sưng", "tê", "đỏ", "khàn", "chóng mặt",
    "buồn nôn", "nôn", "mệt", "ra huyết", "khó chịu",
]


def _is_patient(turn: dict) -> bool:
    who = str(turn.get("who", "")).lower()
    return "trợ lý" not in who and "bot" not in who


def _patient_text(transcript: list[dict]) -> str:
    return " ".join(t.get("text", "") for t in transcript if _is_patient(t)).lower()


def _heuristic(transcript: list[dict]) -> dict:
    text = _patient_text(transcript)
    tier = "green"
    if any(k in text for k in AMBER_KW):
        tier = "amber"
    if any(k in text for k in RED_KW):
        tier = "red"
    label = {"red": "nguy cơ cao", "amber": "cần theo dõi", "green": "ổn định"}[tier]
    # short extractive summary: the patient's turns, trimmed.
    said = [t.get("text", "") for t in transcript if _is_patient(t) and t.get("text")]
    body = " ".join(said)[:280]
    summary = f"Bệnh nhân cho biết: {body} → phân loại {label}."
    return {"summary": summary, "tier": tier, "escalated": tier == "red", "source": "heuristic"}


def _gpt(transcript: list[dict]) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=8)
    convo = "\n".join(f"{t.get('who')}: {t.get('text')}" for t in transcript)
    prompt = (
        "Bạn là điều dưỡng theo dõi hậu phẫu. Dưới đây là bản ghi cuộc gọi theo dõi "
        "giữa trợ lý và bệnh nhân. Hãy: (1) tóm tắt ngắn gọn tình trạng bệnh nhân bằng "
        "tiếng Việt; (2) phân loại mức nguy cơ 'red' (nguy cơ cao, cần bác sĩ xử lý ngay), "
        "'amber' (cần theo dõi thêm) hoặc 'green' (ổn định). "
        'Trả về JSON: {"summary":"...","tier":"red|amber|green","escalated":true/false}.\n\n'
        f"BẢN GHI:\n{convo}"
    )
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    data = json.loads(resp.choices[0].message.content)
    tier = data.get("tier") if data.get("tier") in ("red", "amber", "green") else "amber"
    return {
        "summary": data.get("summary") or "(không có tóm tắt)",
        "tier": tier,
        "escalated": bool(data.get("escalated")) or tier == "red",
        "source": "gpt",
    }


def analyze(transcript: list[dict]) -> dict:
    if settings.OPENAI_API_KEY:
        try:
            return _gpt(transcript)
        except Exception as e:  # noqa: BLE001 — demo must not crash on AI errors
            print(f"[call_analysis] GPT failed, using heuristic: {e}", flush=True)
    return _heuristic(transcript)


if __name__ == "__main__":  # tiny self-check
    t = [
        {"who": "Trợ lý", "text": "Anh có sốt không?"},
        {"who": "Anh Bảo", "text": "Có, tôi sốt 38.7 và vết mổ chảy dịch."},
    ]
    r = _heuristic(t)
    assert r["tier"] == "red" and r["escalated"], r
    g = _heuristic([{"who": "Trợ lý", "text": "?"}, {"who": "BN", "text": "Tôi khỏe, ăn uống tốt."}])
    assert g["tier"] == "green", g
    print("call_analysis self-check OK")
