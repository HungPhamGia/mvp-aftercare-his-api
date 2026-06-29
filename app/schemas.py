from datetime import datetime
from typing import Any

from pydantic import BaseModel


# --- Bot-facing: set_variables contract ---
class SetVariablesIn(BaseModel):
    # ponytail: shape per the doc. VERIFY against the real console request before
    # locking — log the incoming body in /his/patient/fetch first.
    set_variables: dict[str, Any]


class SetVariablesOut(BaseModel):
    status: str = "success"
    code: int = 200
    set_variables: dict[str, Any]


# --- Dashboard / write-back payloads ---
class CallResultIn(BaseModel):
    ma_ho_so: str
    question_set_id: int | None = None
    session_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    raw_answers: dict[str, Any] | None = None
    extracted: dict[str, Any] | None = None
    tier: str | None = None
    summary: str | None = None
    escalated: bool | None = None
    escalation_channel: str | None = None


class GhiChuIn(BaseModel):
    ghi_chu_theo_doi: str


class ThuocIn(BaseModel):
    thuoc_ke: str


class MonitoringIn(BaseModel):
    monitoring_status: str | None = None
    next_call_at: datetime | None = None


class QuestionIn(BaseModel):
    text: str
    order_index: int
    expected_var: str | None = None
    red_flag: bool | None = None


class QuestionSetIn(BaseModel):
    ma_ho_so: str
    questions: list[QuestionIn]
