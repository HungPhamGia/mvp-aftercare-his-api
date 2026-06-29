# Mock HIS — API Design

API service over the mock-HIS database (Postgres on Supabase). Two consumers:
- **Smartbot** (via API Card / Thẻ API) — strict `set_variables` contract.
- **Dashboard** (clinical-staff UI) — plain JSON.

Scope of this doc: **API design only — fetch + update.** (Question generation, flagging,
deploy/ops are separate concerns, added later.)

## Data the API touches
Flat HIS record table + a few operational tables. Business key = `ma_ho_so`.

```
benh_an  (one row per record; columns from aftercare_patients.csv)
  ma_ho_so PK, ho_ten, gioi_tinh, ngay_sinh, tuoi, so_the_bhyt,
  ngay_nhap_vien, ngay_xuat_vien, bac_si_phu_trach, ly_do_vao_vien,
  chan_doan, sinh_hieu, phau_thuat, thuoc_ke, xet_nghiem,
  ghi_chu_theo_doi, lich_tai_kham

call_results  (write-back target)
  id, ma_ho_so FK, question_set_id FK, session_id, started_at, ended_at,
  raw_answers JSONB, extracted JSONB, tier, summary, escalated, escalation_channel

question_sets / questions  (bot fetches the approved set)
  question_sets(id, ma_ho_so FK, status[draft|pending|approved], created_at, approved_at)
  questions(id, question_set_id FK, text, order_index, expected_var, red_flag, approved)
```
Don't recreate the schema — it already exists on Supabase; align models to the live tables.

## Endpoints

### Bot-facing — `set_variables` contract
- `POST /his/patient/fetch`
  - in: `{"set_variables": {"ma_ho_so": "..."}}` — **verify the exact request shape on the
    console; log the real incoming request before locking the model.**
  - out: `{"status":"success","code":200,"set_variables":{"ho_ten":"...","phau_thuat":"...",
    "ngay_xuat_vien":"...","ngay_hau_phau":"<computed>","bac_si_phu_trach":"..."}}`
  - **PHI minimization: never put `so_the_bhyt`, the full `chan_doan` (ICD codes), or
    `xet_nghiem` into `set_variables`.**
- `POST /his/questions/fetch`  (or `GET /his/record/{ma_ho_so}/questions`)
  - out: the **approved** question set (ordered items + `expected_var`); empty + a flag if none.

### Dashboard — plain JSON
- `GET /records` — list (`ho_ten`, `phau_thuat`, `ngay_xuat_vien`, latest `tier`).
- `GET /records/{ma_ho_so}` — full record + latest `call_result`.
- `GET /records/{ma_ho_so}/call-results` — history.

### Update / write-back
- `POST /his/call-result` — store `raw_answers`, `extracted`, `tier`, `summary`, `escalated`.
- `PUT /records/{ma_ho_so}/ghi-chu` — edit `ghi_chu_theo_doi`.
- `PUT /records/{ma_ho_so}/thuoc` — edit `thuoc_ke`.
- `PUT /records/{ma_ho_so}/monitoring` — set monitoring status / next-call schedule
  (AfterCare-side field, not part of the HIS export).
- `POST /questions` — create a question set for a record (items + `expected_var`).
- `PUT /questions/{set_id}/approve` — mark `approved`, lock.

## Database connection

**Use the Supavisor pooler, not the direct `db.[ref].supabase.co` host** — direct is IPv6-only
(unless you buy the IPv4 add-on) and Render egress isn't guaranteed IPv6, so it would fail. The
pooler is IPv4-compatible.

**Connection string** — copy from Dashboard → Connect → Session pooler. Shape:
```
postgresql+psycopg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres?sslmode=require
```
- Username **must** be `postgres.[PROJECT_REF]` (project ref after the dot) — omit it → auth fails.
- Port `5432` = **session mode** → use this for a persistent server like Render (supports prepared
  statements, behaves like normal Postgres). Port `6543` = transaction mode (see below).
- URL-encode special characters in the password (`@ : / # ?` …).
- Driver scheme: `postgresql+psycopg` (psycopg3) or `postgresql+psycopg2`; async → `postgresql+asyncpg`.

**Engine (`app/db.py`):**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings          # pydantic-settings; DATABASE_URL from env

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # IMPORTANT: drop dead conns (pooler idle timeout) before use
    pool_size=5,          # keep small; stay under Supabase "Max Client Connections"
    max_overflow=2,
    pool_recycle=1800,    # recycle every 30 min to avoid stale connections
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
- `pool_pre_ping=True` is the one people forget — pooled/cloud connections die when idle and you
  get "connection closed" on the next request without it.
- Keep `pool_size + max_overflow` modest; the pooler has its own client-connection cap
  (Dashboard → Database → Connection pooling). Several instances each holding a big pool exhaust it.

**SSL:** `?sslmode=require` works for psycopg2/psycopg3. **asyncpg ignores `sslmode`** — pass SSL
via `connect_args={"ssl": True}` instead.

**Transaction mode (port `6543`) — only if you need high concurrency:**
```python
from sqlalchemy.pool import NullPool
engine = create_engine(
    DATABASE_URL_6543,
    poolclass=NullPool,                       # let Supavisor own the pool
    connect_args={"prepare_threshold": None}, # psycopg3: disable prepared statements
    # asyncpg: connect_args={"statement_cache_size": 0}
)
```
Without disabling prepared statements you'll hit `prepared statement "..." already exists`.

**Schema:** the DB already exists on Supabase → models **align** to the live tables. Do **NOT**
call `Base.metadata.create_all()`. On startup, optionally reflect/verify and fail loudly on mismatch.

**Secrets:** `DATABASE_URL` (and any key) from `.env` via pydantic-settings — never hardcoded,
never sent to a browser. Ship `.env.example`. Don't use PostgREST / `supabase-py` (we need custom
contracts).

**Pitfalls checklist:**
- Pooler host, not `db.[ref]…` → avoids IPv6 failure on Render.
- Username carries `.PROJECT_REF` → avoids auth error.
- Port `5432` (session mode) for the persistent server.
- `pool_pre_ping=True` set → avoids "connection closed" after idle.
- Password URL-encoded; `sslmode=require` present.
