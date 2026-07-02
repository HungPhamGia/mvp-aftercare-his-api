"""Build a draft post-op follow-up question set.

Always includes the red-flag CORE questions (never AI-removable). Adds
personalized non-core questions: from OpenAI when OPENAI_API_KEY is set,
otherwise from a deterministic template so the demo runs offline.

ponytail: answer_type / source are not DB columns — source is derived from
red_flag (red_flag => "core"), answer_type is derived on read. Add columns
only if these must survive a reload.
"""
import json

from app.config import settings

# Red-flag escalation questions — always present, locked from deletion.
CORE: list[dict] = [
    {"text": "Anh/chị có bị sốt cao trên 38.5°C không?", "expected_var": "sot"},
    {"text": "Vết mổ có sưng đỏ, chảy dịch hay có mủ không?", "expected_var": "vet_mo"},
    {"text": "Cơn đau có tăng nhiều và không giảm khi dùng thuốc không?", "expected_var": "dau"},
    {"text": "Anh/chị có bị chảy máu bất thường không?", "expected_var": "chay_mau"},
    {"text": "Anh/chị có thấy khó thở hoặc đau ngực không?", "expected_var": "kho_tho"},
]

# Generic non-core fallback questions.
TEMPLATE: list[dict] = [
    {"text": "Anh/chị có uống thuốc đầy đủ theo đơn không?", "expected_var": "tuan_thu_thuoc"},
    {"text": "Việc ăn uống và tiêu hóa của anh/chị thế nào?", "expected_var": "an_uong"},
    {"text": "Anh/chị có nhớ lịch tái khám sắp tới không?", "expected_var": "tai_kham"},
]


def _answer_type(q: dict) -> str:
    return "boolean" if q.get("red_flag") else "text"


def _ai_draft(patient: dict) -> list[dict]:
    """Personalized non-core questions via OpenAI. Returns [] on any failure."""
    from openai import OpenAI

    # Fail fast: no SDK retries + short timeout, so a bad/quota-exhausted key
    # falls back to the template immediately instead of hanging the request.
    client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=8)
    prompt = (
        "Bạn là điều dưỡng theo dõi hậu phẫu. Dựa trên thông tin bệnh nhân, "
        "soạn 3-5 câu hỏi theo dõi NGẮN bằng tiếng Việt (không hỏi về dấu hiệu "
        "nguy hiểm cấp cứu — đã có sẵn). Trả về JSON: "
        '{"questions":[{"text":"...","expected_var":"snake_case"}]}.\n\n'
        f"Phẫu thuật: {patient.get('phau_thuat')}\n"
        f"Thuốc kê: {patient.get('thuoc_ke')}\n"
        f"Ghi chú theo dõi: {patient.get('ghi_chu_theo_doi')}"
    )
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    data = json.loads(resp.choices[0].message.content)
    out = []
    for q in data.get("questions", []):
        if q.get("text"):
            out.append({"text": q["text"], "expected_var": q.get("expected_var")})
    return out


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def ai_suggest_questions(patient: dict, existing: set[str]) -> list[dict]:
    """Suggest NEW follow-up questions not already in `existing` (normalized
    texts of the disease + patient sets). Returns [] on failure. When no
    OPENAI key, falls back to the generic TEMPLATE minus anything already present.

    ponytail: dedup is exact-after-normalize (lowercase + collapse spaces); a
    semantic dedup would need embeddings — overkill for the demo.
    """
    def _fresh(items: list[dict]) -> list[dict]:
        out = []
        for q in items:
            t = (q.get("text") or "").strip()
            if t and _norm(t) not in existing:
                out.append({"text": t, "expected_var": q.get("expected_var")})
        return out

    if not settings.OPENAI_API_KEY:
        return _fresh(TEMPLATE)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        have = "\n".join(f"- {t}" for t in sorted(existing)) or "(chưa có câu nào)"
        prompt = (
            "Bạn là điều dưỡng theo dõi hậu phẫu. Soạn 3-5 câu hỏi theo dõi NGẮN "
            "bằng tiếng Việt để BỔ SUNG cho bộ câu hỏi hiện có. TUYỆT ĐỐI không lặp "
            "lại hay diễn đạt lại các câu đã có; chỉ đưa câu MỚI thật sự có giá trị. "
            "Không hỏi về dấu hiệu nguy hiểm cấp cứu (đã có sẵn). "
            'Trả về JSON: {"questions":[{"text":"...","expected_var":"snake_case"}]}.\n\n'
            f"Loại bệnh: {patient.get('disease')}\n"
            f"Phẫu thuật: {patient.get('phau_thuat')}\n"
            f"Chẩn đoán: {patient.get('chan_doan')}\n"
            f"Thuốc kê: {patient.get('thuoc_ke')}\n"
            f"Ghi chú theo dõi: {patient.get('ghi_chu_theo_doi')}\n\n"
            f"Các câu ĐÃ CÓ (không được lặp lại):\n{have}"
        )
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        data = json.loads(resp.choices[0].message.content)
        return _fresh(data.get("questions", []))
    except Exception as e:  # noqa: BLE001 — demo must not crash on AI errors
        print(f"[questions_gen] AI suggest failed, using template: {e}", flush=True)
        return _fresh(TEMPLATE)


def build_question_set(patient: dict) -> list[dict]:
    """Return ordered question dicts: core red-flags first, then non-core."""
    non_core = []
    if settings.OPENAI_API_KEY:
        try:
            non_core = _ai_draft(patient)
        except Exception as e:  # noqa: BLE001 — demo must not crash on AI errors
            print(f"[questions_gen] OpenAI draft failed, using template: {e}", flush=True)
    if not non_core:
        non_core = TEMPLATE

    questions = []
    for q in CORE:
        questions.append({**q, "red_flag": True})
    questions.extend({**q, "red_flag": False} for q in non_core)

    for i, q in enumerate(questions):
        q["order_index"] = i
        q["source"] = "core" if q["red_flag"] else "ai"
        q["answer_type"] = _answer_type(q)
    return questions
