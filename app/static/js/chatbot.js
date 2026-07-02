/* =========================================================================
   AfterCare · chatbot.js — "Demo cuộc gọi AI".
   Pick a patient → the AI assistant places a mock call: a phone screen on the
   left, a live transcript on the right. The bot reads each scripted question
   aloud (browser TTS — to be swapped for SmartBot TTS); the clinician answers
   as the patient (typing, or the mic via Web Speech / future SmartVoice STT).
   On hang-up the transcript is saved and GPT summarises + classifies the tier.
   ========================================================================= */

function demoId() { return new URLSearchParams(location.search).get("id") || ""; }

const DEMO = {
  maHoSo: demoId(), patient: null, script: null,
  idx: 0, phase: "setup", transcript: [], answers: [],
  awaiting: false, ttsOn: true, startTs: 0, timerId: null, rec: null,
};

/* ---- helpers ---------------------------------------------------------- */
function isBot(t) { return /trợ lý/i.test(t.who); }
function speak(text) {
  if (!DEMO.ttsOn || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "vi-VN"; u.rate = 1;
  const v = (window.speechSynthesis.getVoices() || []).find(x => /vi/i.test(x.lang));
  if (v) u.voice = v;
  window.speechSynthesis.speak(u);
}
function fmtTimer(s) {
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/* ---- 1) setup screen -------------------------------------------------- */
function renderSetup() {
  DEMO.phase = "setup";
  const opts = PATIENTS.map(p => `<option value="${esc(p.mrn)}">${esc(p.name)} (${esc(p.mrn)})</option>`).join("");
  $("#demoRoot").innerHTML = `
    <section class="card demo-setup">
      <h2>Chọn bệnh nhân để demo</h2>
      <p class="muted-note">Trợ lý AI sẽ gọi và hỏi theo bộ câu hỏi của bệnh nhân (bản đã duyệt, hoặc bản mẫu nếu chưa duyệt).</p>
      <label class="f"><span>Bệnh nhân</span>
        <select class="select" id="demoPick"><option value="">— Chọn bệnh nhân —</option>${opts}</select></label>
      <label class="check"><input type="checkbox" id="demoTts" checked> Bot đọc câu hỏi thành tiếng</label>
      <div style="margin-top:16px">
        <button class="btn btn-leaf" id="demoStart" disabled>▶ Bắt đầu demo cuộc gọi</button>
      </div>
    </section>`;
  const pick = $("#demoPick");
  if (getPatient(DEMO.maHoSo)) pick.value = DEMO.maHoSo;
  const sync = () => { $("#demoStart").disabled = !pick.value; };
  sync();
  pick.addEventListener("change", sync);
  $("#demoStart").addEventListener("click", () => startCall(pick.value));
}

/* ---- 2) in-call screen ------------------------------------------------ */
async function startCall(mrn) {
  DEMO.maHoSo = mrn;
  DEMO.patient = getPatient(mrn);
  DEMO.ttsOn = $("#demoTts") ? $("#demoTts").checked : true;
  DEMO.idx = 0; DEMO.transcript = []; DEMO.answers = []; DEMO.awaiting = false;
  history.replaceState(null, "", location.pathname + "?id=" + encodeURIComponent(mrn));

  let s;
  try { s = await API.get("/his/patient/" + encodeURIComponent(mrn) + "/call-preview"); }
  catch (e) { toast("Không tải được kịch bản: " + e.message); return; }
  DEMO.script = s;
  DEMO.phase = "calling";
  renderCall();
  startTimer();
  // greeting → first question
  botTurn(s.greeting, false);
  setTimeout(askNext, 1400);
}

function renderCall() {
  const p = DEMO.patient || { name: DEMO.maHoSo, mrn: DEMO.maHoSo, surgery: "" };
  $("#demoRoot").innerHTML = `
    <div class="demo-call">
      <section class="phone">
        <div class="phone-notch"></div>
        <div class="phone-screen">
          <div class="ph-status" id="phStatus">Đang gọi…</div>
          <div class="ph-avatar">${esc(avatarInitials(p.name || "BN"))}</div>
          <div class="ph-name">${esc(p.name || "")}</div>
          <div class="ph-sub">${esc(p.mrn || "")}${p.surgery ? " · " + esc(p.surgery) : ""}</div>
          <div class="ph-timer" id="phTimer">00:00</div>
          <div class="ph-caption" id="phCaption">Đang kết nối…</div>
          <div class="ph-controls">
            <button class="ph-btn mic" id="micBtn" type="button" title="Nói (giữ để trả lời)">🎙</button>
            <button class="ph-btn end" id="endBtn" type="button" title="Kết thúc cuộc gọi">✕</button>
          </div>
        </div>
      </section>

      <section class="transcript-panel card">
        <div class="tp-head"><span class="live-dot"></span> Bản ghi trực tiếp</div>
        <div id="tpLog" class="tp-log" aria-live="polite"></div>
        <form id="answerForm" class="tp-input">
          <input id="answerText" class="input" type="text" autocomplete="off"
                 placeholder="Trả lời thay bệnh nhân (hoặc bấm 🎙 để nói)…">
          <button class="btn btn-leaf" type="submit">Gửi</button>
        </form>
      </section>
    </div>`;
  renderTranscript();
  $("#endBtn").addEventListener("click", () => endCall());
  $("#micBtn").addEventListener("click", toggleMic);
  $("#answerForm").addEventListener("submit", e => { e.preventDefault(); submitAnswer($("#answerText").value); });
}

function renderTranscript() {
  const log = $("#tpLog");
  if (!log) return;
  log.innerHTML = DEMO.transcript.map(t =>
    `<div class="chat-msg ${isBot(t) ? "bot" : "user"}"><span class="spk">${esc(t.who)}</span>${esc(t.text)}</div>`
  ).join("") || `<div class="chat-msg sys">Cuộc gọi đang bắt đầu…</div>`;
  log.scrollTop = log.scrollHeight;
}

function botTurn(text, isQuestion) {
  DEMO.transcript.push({ who: "Trợ lý", text });
  renderTranscript();
  const cap = $("#phCaption"); if (cap) cap.textContent = text;
  speak(text);
  DEMO.awaiting = !!isQuestion;
  const st = $("#phStatus");
  if (st) st.textContent = isQuestion ? "Đang chờ bệnh nhân trả lời…" : "Đang gọi…";
}

function askNext() {
  if (DEMO.phase !== "calling") return;
  const qs = DEMO.script.questions || [];
  if (DEMO.idx < qs.length) {
    botTurn(qs[DEMO.idx].text, true);
  } else {
    botTurn(DEMO.script.closing, false);
    setTimeout(() => endCall(), 2200);
  }
}

function submitAnswer(text) {
  text = (text || "").trim();
  if (!text || DEMO.phase !== "calling" || !DEMO.awaiting) return;
  const q = (DEMO.script.questions || [])[DEMO.idx];
  DEMO.transcript.push({ who: DEMO.patient ? DEMO.patient.name : "Bệnh nhân", text });
  DEMO.answers.push({ question: q ? q.text : null, expected_var: q ? q.expected_var : null, answer: text });
  DEMO.idx++; DEMO.awaiting = false;
  const inp = $("#answerText"); if (inp) inp.value = "";
  renderTranscript();
  setTimeout(askNext, 900);
}

/* ---- mic (Web Speech STT if available; SmartVoice later) -------------- */
function setMic(on) { const b = $("#micBtn"); if (b) b.classList.toggle("on", on); }
function toggleMic() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { toast("Trình duyệt chưa hỗ trợ nhận giọng nói — hãy gõ câu trả lời."); $("#answerText").focus(); return; }
  if (DEMO.rec) { DEMO.rec.stop(); return; }
  const rec = new SR();
  rec.lang = "vi-VN"; rec.interimResults = true; rec.continuous = false;
  DEMO.rec = rec; setMic(true);
  let finalText = "";
  rec.onresult = e => {
    let interim = "";
    for (const r of e.results) { if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript; }
    $("#answerText").value = (finalText + " " + interim).trim();
  };
  rec.onerror = () => { setMic(false); DEMO.rec = null; };
  rec.onend = () => {
    setMic(false); DEMO.rec = null;
    const t = ($("#answerText").value || "").trim();
    if (t) submitAnswer(t);
  };
  rec.start();
}

/* ---- timer ------------------------------------------------------------ */
function startTimer() {
  DEMO.startTs = Date.now();
  DEMO.timerId = setInterval(() => {
    const el = $("#phTimer");
    if (el) el.textContent = fmtTimer(Math.floor((Date.now() - DEMO.startTs) / 1000));
  }, 1000);
}
function stopTimer() { if (DEMO.timerId) { clearInterval(DEMO.timerId); DEMO.timerId = null; } }

/* ---- 3) end + save ---------------------------------------------------- */
async function endCall() {
  if (DEMO.phase === "ended") return;
  DEMO.phase = "ended";
  stopTimer();
  if (DEMO.rec) { try { DEMO.rec.stop(); } catch (e) {} }
  if (window.speechSynthesis) window.speechSynthesis.cancel();

  $("#demoRoot").innerHTML = `<section class="card demo-result"><h2>Đang lưu & phân tích cuộc gọi…</h2>
    <p class="muted-note">Hệ thống đang tóm tắt và phân loại mức nguy cơ.</p></section>`;

  let res;
  try {
    res = await API.post("/his/call-demo/save", {
      ma_ho_so: DEMO.maHoSo, transcript: DEMO.transcript, answers: DEMO.answers,
    });
  } catch (e) {
    $("#demoRoot").innerHTML = `<section class="card demo-result">
      <h2>Đã kết thúc cuộc gọi</h2>
      <p class="muted-note">Không lưu được vào hồ sơ: ${esc(e.message)}</p>
      <button class="btn btn-leaf" onclick="renderSetup()">Demo lại</button></section>`;
    return;
  }

  const tierLabel = { red: "Nguy cơ cao", amber: "Cần theo dõi", green: "Ổn định" }[res.tier] || res.tier;
  $("#demoRoot").innerHTML = `
    <section class="card demo-result">
      <div class="dr-head">
        <span class="badge ${esc(res.tier)}">${esc(tierLabel)}</span>
        <h2>Đã kết thúc & lưu vào hồ sơ ca</h2>
      </div>
      ${res.escalated ? `<div class="callout red" style="margin:10px 0"><b>⚠ Đã nâng cảnh báo</b> — cần bác sĩ phụ trách xem sớm.</div>` : ""}
      <div class="summary-block"><h4>Tóm tắt cuộc gọi ${res.source === "gpt" ? "(GPT)" : "(tự động)"}</h4>
        <p>${esc(res.summary)}</p></div>
      <div class="dr-actions">
        <a class="btn btn-leaf" href="case.html?id=${esc(DEMO.maHoSo)}">Xem chi tiết ca</a>
        <button class="btn" onclick="renderSetup()">Demo lại</button>
      </div>
    </section>`;
}

AfterCare.ready(renderSetup);
