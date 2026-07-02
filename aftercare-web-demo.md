# AfterCare Web Demo — Build Spec (for Claude Code)

> **How to use:** put this file as `CLAUDE.md` at the repo root, then ask Claude Code to build it
> step by step (see Build steps). Build ONE FastAPI app: a 4-view frontend + a Smartbot **BFF** +
> reuse of the HIS / question-gen API over Supabase. Deploy: Render (single web service, HTTPS).
> Scope: **text<->text only** (speech deferred).

Goal flow: view a patient -> generate & approve their questions -> run the call (text voicebot) ->
view the answers.

## Stack (use exactly)
- Python 3.11+, FastAPI, uvicorn
- `httpx` (async) — BFF -> Smartbot
- SQLAlchemy 2.x + `psycopg[binary]` — Supabase Postgres
- `openai` — question generation
- `pydantic-settings`, `python-dotenv`
- Frontend: plain HTML + vanilla JS + CSS (no framework, no build step), `fetch` only; served by
  FastAPI via StaticFiles

## Reused vs new
- **Reuse if already present** (from the HIS API spec): Supabase models/connection + these
  endpoints — `GET /his/patients`, `GET /his/patient/{ma_ho_so}`, `POST /questions/generate`,
  `PUT /questions/{set_id}/approve`, `GET /his/patient/{ma_ho_so}/call-results`. If absent,
  implement per the contracts below.
- **New in this task:** the **BFF** (`POST /bff/conversation`), the **4-view frontend**, and
  `PUT /questions/{set_id}` (save edits before approval).

## Rules (DO / DON'T)
- **DO** load every secret from env via pydantic-settings: `DATABASE_URL`, `OPENAI_API_KEY`,
  `BOT_ID`, `SMARTBOT_ACCESS_TOKEN`, `SMARTBOT_TOKEN_ID`, `SMARTBOT_TOKEN_KEY`. Ship `.env.example`.
- **DON'T** put any secret or Smartbot token in frontend code — the browser only ever calls OUR
  endpoints. This is the entire reason for the BFF.
- **DON'T** recreate or drop the Supabase schema — it already exists; align models to it.
- **DON'T** use `localStorage` / `sessionStorage` — keep UI state in JS memory.
- **DON'T** send `so_the_bhyt` / full `chan_doan` / `xet_nghiem` to the bot; mask `so_the_bhyt` in the UI.
- Supabase: SQLAlchemy via the **Supavisor session pooler** (port `5432`, username
  `postgres.[PROJECT_REF]`, `?sslmode=require`, engine `pool_pre_ping=True`). NOT PostGREST / `supabase-py`.

## Smartbot integration (the BFF — get this exact)
Endpoint: `POST https://assistant-stream.vnpt.vn/v1/conversation`
Headers: `Authorization: Bearer ${SMARTBOT_ACCESS_TOKEN}`, `Token-id: ${SMARTBOT_TOKEN_ID}`,
`Token-key: ${SMARTBOT_TOKEN_KEY}`, `Content-Type: application/json`, `Accept: text/event-stream`.
Request body:
```json
{
  "bot_id": "${BOT_ID}",
  "sender_id": "<per session>",
  "session_id": "<per session>",
  "text": "<user message>",
  "input_channel": "api",
  "metadata": { "button_variables": [ {"variableName": "ma_ho_so", "value": "<id>"} ] },
  "settings": {}
}
```
- Send `metadata.button_variables` ONLY on the **first turn** of a session (seeds `ma_ho_so`).
  All values are strings.
- Response is an **SSE stream**. Each event is JSON; cards are at `object.sb.card_data` (a list);
  `object.sb.card_data_info.status`: `0`=final no-stream, `1`=partial, `2`=final-with-stream.
  **Read events until status is `0` or `2`**, then assemble.
- From `card_data`: `type:"text"` -> message text; `type:"quickreply"` -> button labels;
  `type:"chuyen_gdv"` -> set a `handoff` flag.
- ⚠️ The exact request shape Smartbot expects/sends may differ slightly from the doc — log the raw
  exchange once and confirm before locking it in.

**BFF endpoint:** `POST /bff/conversation`
- Request (from browser): `{ "text": str, "session_id": str, "ma_ho_so": str, "first_turn": bool }`
- Behavior: build the Smartbot request server-side (creds from env), inject `button_variables` when
  `first_turn` is true, read the SSE to completion, assemble the reply. (Non-streaming to the
  browser for the MVP — collect then return JSON.)
- Response (to browser): `{ "text": str, "quickreplies": [str], "handoff": bool }`

## API contracts (the frontend uses these)
- `GET /health` -> `{"status":"ok"}`  (Render health check + warm-up)
- `GET /his/patients` -> `[{ ma_ho_so, ho_ten, phau_thuat, ngay_xuat_vien, latest_tier }]`
- `GET /his/patient/{ma_ho_so}` -> `{ ma_ho_so, ho_ten, gioi_tinh, tuoi, phau_thuat,
  ngay_xuat_vien, chan_doan, thuoc_ke, ghi_chu_theo_doi, lich_tai_kham }`  (NO `so_the_bhyt`)
- `POST /questions/generate` body `{ ma_ho_so }` ->
  `{ set_id, status:"pending_review", questions:[{ id, text, expected_var, answer_type, source, red_flag }] }`
- `PUT /questions/{set_id}` body `{ questions:[...] }` -> saves edits, returns the updated set
  (status stays `pending_review`; REJECT deletion of `source:"core"` items)
- `PUT /questions/{set_id}/approve` -> `{ set_id, status:"approved" }`
- `GET /his/patient/{ma_ho_so}/call-results` ->
  `[{ session_id, ended_at, tier, summary, escalated, answers:[{ question, expected_var, raw, value }] }]`

## Frontend (4 views, single page + nav)
1. **Patients** — list (`GET /his/patients`); click -> detail (`GET /his/patient/{id}`); buttons
   "Generate questions" and "Start call" carry `ma_ho_so`.
2. **Generate Questions** — `POST /questions/generate`; render questions as an **editable** list
   (edit text/expected_var/answer_type, add/remove, reorder; `core` items locked from deletion);
   "Save" -> `PUT /questions/{set_id}`; "Approve" -> `PUT /questions/{set_id}/approve`.
3. **Voicebot** — text chat tied to the selected `ma_ho_so`. First message sends `first_turn:true`;
   POST each turn to `/bff/conversation`; render `text` + `quickreplies` (clickable -> sends that
   text); show a banner if `handoff:true`.
4. **Answers** — `GET /his/patient/{ma_ho_so}/call-results`; show tier, summary, escalated, and the
   per-question answers.

## Layout
```
app/
|- main.py            # FastAPI app, mounts routers, serves static/, /health
|- config.py          # pydantic-settings (env)
|- db.py              # SQLAlchemy engine (Supabase session pooler, pool_pre_ping)
|- smartbot.py        # Smartbot client: build request, read SSE, assemble cards
|- routers/
|   |- bff.py         # POST /bff/conversation
|   |- patients.py    # GET /his/patients, /his/patient/{id}
|   |- questions.py   # POST /questions/generate, PUT /questions/{id}, /approve
|   |- results.py     # GET /his/patient/{id}/call-results
|- services/
|   |- questions_gen.py   # GPT draft + red-flag core merge
|- static/
    |- index.html
    |- app.js
    |- styles.css
.env.example
requirements.txt
```

## Build steps (in order; verify each before moving on)
1. **Scaffold** — FastAPI app, `config.py`, `db.py` (Supabase session pooler), `.env.example`,
   `requirements.txt`, `/health`, empty `static/index.html`. *Verify:* app starts; `/health` -> 200.
2. **BFF + Voicebot text** — `smartbot.py` + `POST /bff/conversation` + the Voicebot view.
   *Verify:* typing a message returns the bot's reply against a trivial bot.
3. **Patients view** — `patients.py` + the Patients view from Supabase. *Verify:* list + detail render.
4. **Generate Questions view** — `questions_gen.py` + `questions.py` (generate/update/approve) +
   the editable UI. *Verify:* generate -> edit -> save -> approve persists in Supabase.
5. **Answers view** — `results.py` + the Answers view. *Verify:* a written `call_result` shows up.
6. **Wire** — selecting a patient flows `ma_ho_so` into Generate and Voicebot (first turn seeds it).

## Out of scope (do not build)
- Speech / audio, telephony, SmartVoice (deferred).
- Auth / login (mock data; demo only).
- The Smartbot scenario itself (configured on the VNPT console, not code).
- The flagging rule-engine internals (`tier` is supplied/stored; the engine is a separate task).
