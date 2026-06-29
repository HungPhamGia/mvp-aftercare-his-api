from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BenhAn, CallResult, Monitoring, Question, QuestionSet
from app.schemas import (
    CallResultIn, GhiChuIn, MonitoringIn, QuestionSetIn,
    SetVariablesIn, SetVariablesOut, ThuocIn,
)

app = FastAPI(title="Mock HIS API")


def row_to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def get_record_or_404(db: Session, ma_ho_so: str) -> BenhAn:
    rec = db.get(BenhAn, ma_ho_so)
    if rec is None:
        raise HTTPException(404, f"record {ma_ho_so} not found")
    return rec


def latest_call_result(db: Session, ma_ho_so: str) -> CallResult | None:
    return db.scalars(
        select(CallResult)
        .where(CallResult.ma_ho_so == ma_ho_so)
        .order_by(CallResult.id.desc())
        .limit(1)
    ).first()


# --- Bot-facing: set_variables contract ---
@app.post("/his/patient/fetch", response_model=SetVariablesOut)
def patient_fetch(body: SetVariablesIn, db: Session = Depends(get_db)):
    ma_ho_so = body.set_variables.get("ma_ho_so")
    if not ma_ho_so:
        raise HTTPException(400, "set_variables.ma_ho_so required")
    rec = get_record_or_404(db, ma_ho_so)

    # PHI minimization: omit so_the_bhyt, chan_doan (ICD), xet_nghiem.
    return SetVariablesOut(set_variables={
        "ho_ten": rec.ho_ten,
        "phau_thuat": rec.phau_thuat,
        "ngay_xuat_vien": str(rec.ngay_xuat_vien) if rec.ngay_xuat_vien else None,
        "lich_tai_kham": str(rec.lich_tai_kham) if rec.lich_tai_kham else None,
        "bac_si_phu_trach": rec.bac_si_phu_trach,
    })


@app.get("/his/record/{ma_ho_so}/questions")
def questions_fetch(ma_ho_so: str, db: Session = Depends(get_db)):
    qset = db.scalars(
        select(QuestionSet)
        .where(QuestionSet.ma_ho_so == ma_ho_so, QuestionSet.status == "approved")
        .order_by(QuestionSet.id.desc())
        .limit(1)
    ).first()
    if qset is None:
        return {"question_set_id": None, "questions": [], "has_approved_set": False}
    return {
        "question_set_id": qset.id,
        "has_approved_set": True,
        "questions": [
            {"text": q.text, "order_index": q.order_index, "expected_var": q.expected_var}
            for q in qset.questions
        ],
    }


# --- Dashboard (plain JSON) ---
@app.get("/records")
def list_records(db: Session = Depends(get_db)):
    rows = db.scalars(select(BenhAn)).all()
    # ponytail: latest tier via per-row lookup (N+1). Fine for MVP volume;
    # collapse into a window-function join if the list grows.
    out = []
    for r in rows:
        cr = latest_call_result(db, r.ma_ho_so)
        out.append({
            "ma_ho_so": r.ma_ho_so,
            "ho_ten": r.ho_ten,
            "phau_thuat": r.phau_thuat,
            "ngay_xuat_vien": r.ngay_xuat_vien,
            "tier": cr.tier if cr else None,
        })
    return out


@app.get("/records/{ma_ho_so}")
def get_record(ma_ho_so: str, db: Session = Depends(get_db)):
    rec = get_record_or_404(db, ma_ho_so)
    cr = latest_call_result(db, ma_ho_so)
    return {"record": row_to_dict(rec), "latest_call_result": row_to_dict(cr) if cr else None}


@app.get("/records/{ma_ho_so}/call-results")
def call_result_history(ma_ho_so: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(CallResult)
        .where(CallResult.ma_ho_so == ma_ho_so)
        .order_by(CallResult.id.desc())
    ).all()
    return [row_to_dict(r) for r in rows]


# --- Write-back ---
@app.post("/his/call-result")
def create_call_result(body: CallResultIn, db: Session = Depends(get_db)):
    get_record_or_404(db, body.ma_ho_so)
    cr = CallResult(**body.model_dump())
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return {"id": cr.id}


@app.put("/records/{ma_ho_so}/ghi-chu")
def update_ghi_chu(ma_ho_so: str, body: GhiChuIn, db: Session = Depends(get_db)):
    rec = get_record_or_404(db, ma_ho_so)
    rec.ghi_chu_theo_doi = body.ghi_chu_theo_doi
    db.commit()
    return {"ma_ho_so": ma_ho_so, "ghi_chu_theo_doi": rec.ghi_chu_theo_doi}


@app.put("/records/{ma_ho_so}/thuoc")
def update_thuoc(ma_ho_so: str, body: ThuocIn, db: Session = Depends(get_db)):
    rec = get_record_or_404(db, ma_ho_so)
    rec.thuoc_ke = body.thuoc_ke
    db.commit()
    return {"ma_ho_so": ma_ho_so, "thuoc_ke": rec.thuoc_ke}


@app.put("/records/{ma_ho_so}/monitoring")
def update_monitoring(ma_ho_so: str, body: MonitoringIn, db: Session = Depends(get_db)):
    get_record_or_404(db, ma_ho_so)
    mon = db.get(Monitoring, ma_ho_so)
    if mon is None:
        mon = Monitoring(ma_ho_so=ma_ho_so)
        db.add(mon)
    if body.monitoring_status is not None:
        mon.monitoring_status = body.monitoring_status
    if body.next_call_at is not None:
        mon.next_call_at = body.next_call_at
    mon.updated_at = datetime.now()
    db.commit()
    return {
        "ma_ho_so": ma_ho_so,
        "monitoring_status": mon.monitoring_status,
        "next_call_at": mon.next_call_at,
    }


@app.post("/questions")
def create_question_set(body: QuestionSetIn, db: Session = Depends(get_db)):
    get_record_or_404(db, body.ma_ho_so)
    qset = QuestionSet(ma_ho_so=body.ma_ho_so, status="draft", created_at=datetime.now())
    qset.questions = [
        Question(
            text=q.text, order_index=q.order_index,
            expected_var=q.expected_var, red_flag=q.red_flag, approved=False,
        )
        for q in body.questions
    ]
    db.add(qset)
    db.commit()
    db.refresh(qset)
    return {"question_set_id": qset.id, "status": qset.status}


@app.put("/questions/{set_id}/approve")
def approve_question_set(set_id: int, db: Session = Depends(get_db)):
    qset = db.get(QuestionSet, set_id)
    if qset is None:
        raise HTTPException(404, f"question_set {set_id} not found")
    qset.status = "approved"
    qset.approved_at = datetime.now()
    for q in qset.questions:
        q.approved = True
    db.commit()
    return {"question_set_id": qset.id, "status": qset.status}
