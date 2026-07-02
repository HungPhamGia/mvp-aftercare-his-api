/* =========================================================================
   AfterCare · questions.js — generate / edit / approve a patient's question
   set via /questions/*. Core (red_flag) items cannot be deleted.
   ========================================================================= */

function qId() { return new URLSearchParams(location.search).get("id") || ""; }

const QS = { maHoSo: qId(), setId: null, status: null, questions: [] };

function setStatus(label, tone) {
  const el = $("#qStatus");
  el.className = "pill " + (tone || "muted");
  el.textContent = label;
}

/* keep the editor DOM values in sync with QS.questions before any save */
function syncFromDom() {
  $all("#qList .qrow").forEach((row, i) => {
    if (QS.questions[i]) QS.questions[i].text = $(".qtext", row).value;
  });
}

function renderList() {
  const list = $("#qList");
  list.innerHTML = QS.questions.map((q, i) => {
    const core = q.source === "core" || q.red_flag;
    return `<li class="qrow ${core ? "core" : ""}">
      <span class="qnum">${i + 1}</span>
      <div class="qbody">
        <textarea class="input qtext" rows="2">${esc(q.text)}</textarea>
        <div class="qmeta">
          <span class="pill ${core ? "red" : "info"}" style="padding:1px 8px">${core ? "Câu lõi (cảnh báo)" : "AI gợi ý"}</span>
          ${q.expected_var ? `<span class="mono">${esc(q.expected_var)}</span>` : ""}
        </div>
      </div>
      ${core ? "" : `<button class="btn btn-sm btn-danger qdel" type="button" data-del="${i}">Xóa</button>`}
    </li>`;
  }).join("");
  $all("#qList [data-del]").forEach(b => b.addEventListener("click", () => {
    syncFromDom();
    QS.questions.splice(+b.dataset.del, 1);
    renderList();
  }));
  $("#btnAdd").style.display = QS.setId ? "inline-block" : "none";
  const has = QS.questions.length > 0 && QS.setId != null;
  $("#btnSave").disabled = !has;
  $("#btnApprove").disabled = !(has && QS.status !== "approved");
}

async function generate() {
  setStatus("Đang tạo…", "amber");
  try {
    const res = await API.post("/questions/generate", { ma_ho_so: QS.maHoSo });
    QS.setId = res.set_id; QS.status = res.status; QS.questions = res.questions || [];
    setStatus("Bản nháp: " + res.status, "amber");
    renderList();
    toast("Đã tạo " + QS.questions.length + " câu hỏi.");
  } catch (e) {
    setStatus("Lỗi tạo câu hỏi", "red");
    toast("Không tạo được câu hỏi: " + e.message);
  }
}

async function save() {
  if (!QS.setId) return;
  syncFromDom();
  try {
    const res = await API.put("/questions/" + QS.setId, {
      questions: QS.questions.map(q => ({
        id: q.id != null ? q.id : null, text: q.text, expected_var: q.expected_var || null,
        answer_type: q.answer_type || null, source: q.source || "ai", red_flag: !!q.red_flag,
      })),
    });
    QS.status = res.status; QS.questions = res.questions || [];
    setStatus("Đã lưu: " + res.status, "info");
    renderList();
    toast("Đã lưu bộ câu hỏi.");
  } catch (e) {
    toast("Lưu thất bại: " + e.message);
  }
}

async function approve() {
  if (!QS.setId) return;
  await save();               // persist edits first
  try {
    const res = await API.put("/questions/" + QS.setId + "/approve");
    QS.status = res.status;
    setStatus("Đã duyệt", "green");
    renderList();
    toast("Đã duyệt bộ câu hỏi — sẽ dùng cho cuộc gọi.");
  } catch (e) {
    toast("Duyệt thất bại: " + e.message);
  }
}

function addQuestion() {
  syncFromDom();
  QS.questions.push({ id: null, text: "", expected_var: null, answer_type: "text", source: "ai", red_flag: false });
  renderList();
}

AfterCare.ready(() => {
  const p = getPatient(QS.maHoSo);
  $("#qTop").innerHTML = `
    <a class="case-back" href="${QS.maHoSo ? "case.html?id=" + esc(QS.maHoSo) : "patients.html"}" aria-label="Quay lại">&#8592;</a>
    <div><div class="crumb">${QS.maHoSo ? "Chi tiết ca &rsaquo; " : ""}Bộ câu hỏi</div>
      <h1>Bộ câu hỏi${p ? " · " + esc(p.name) : (QS.maHoSo ? " · " + esc(QS.maHoSo) : "")}</h1></div>`;

  if (!QS.maHoSo) { setStatus("Thiếu mã hồ sơ", "red"); $("#btnGen").disabled = true; }
  $("#btnGen").addEventListener("click", generate);
  $("#btnSave").addEventListener("click", save);
  $("#btnApprove").addEventListener("click", approve);
  $("#btnAdd").addEventListener("click", addQuestion);
});
