const $ = (selector) => document.querySelector(selector);

const state = {
  userId: localStorage.getItem("course-review-user") || "demo",
  toastTimer: null,
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join("；")
      : data.detail;
    throw new Error(detail || `请求失败（HTTP ${response.status}）`);
  }
  return data;
}

function userQuery() {
  return `user_id=${encodeURIComponent(state.userId)}`;
}

function showToast(message, error = false) {
  const toast = $("#toast");
  clearTimeout(state.toastTimer);
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.hidden = false;
  state.toastTimer = setTimeout(() => { toast.hidden = true; }, 4500);
}

function setBusy(button, busy, label) {
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.textContent = label;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
  }
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

function sourceFor(metadata) {
  const location = metadata.page_number !== null && metadata.page_number !== undefined
    ? `第 ${metadata.page_number} 页`
    : `段落 ${metadata.paragraph_start}–${metadata.paragraph_end}`;
  return `${metadata.relative_path} · ${location}`;
}

async function checkHealth() {
  try {
    const health = await api("/api/health");
    $("#service-status").textContent = "seekdb 与 PowerContext 已连接";
    $("#status-dot").className = "status-dot ready";
    $("#service-status").title = `本地模型：${health.embedding_model}`;
  } catch (error) {
    $("#service-status").textContent = "服务连接异常";
    $("#status-dot").className = "status-dot error";
    showToast(error.message, true);
  }
}

function renderDocuments(documents) {
  $("#document-count").textContent = documents.length;
  const chunks = documents.reduce((total, item) => total + Number(item.chunk_count || 0), 0);
  $("#document-stats").textContent = documents.length
    ? `${documents.length} 个文件 · ${chunks} 个原文块 · 向量与全文索引`
    : "尚未导入资料";
  const list = $("#documents-list");
  list.replaceChildren();
  if (!documents.length) {
    list.append(element("p", "muted", "导入文件后，可在这里核对切块数量。"));
    return;
  }
  for (const document of documents) {
    const item = element("div", "document-item");
    item.append(element("span", "file-type", document.file_type));
    const info = element("div", "document-info");
    const name = element("strong", "", document.relative_path);
    name.title = document.relative_path;
    info.append(name, element("small", "", `${document.chunk_count} 块 · ${formatDate(document.imported_at)}`));
    item.append(info);
    list.append(item);
  }
}

function renderWeakPoints(points) {
  $("#weak-count").textContent = points.length;
  const list = $("#weak-points");
  list.replaceChildren();
  if (!points.length) {
    list.append(element("p", "muted", "还没有薄弱点，去检索一个问题吧。"));
    return;
  }
  for (const point of points) {
    const button = element("button", "weak-point");
    button.type = "button";
    button.title = "点击重新检索这个知识点";
    const top = element("div", "weak-point-top");
    top.append(element("strong", "", point.concept), element("span", "times", `查询 ${point.query_count} 次`));
    const recent = point.recent_queries?.at(-1) || point.concept;
    button.append(top, element("small", "", `最近：${recent}`));
    button.addEventListener("click", () => {
      $("#query").value = recent;
      $("#search-form").requestSubmit();
    });
    list.append(button);
  }
}

function renderReview(points) {
  const list = $("#review-list");
  list.replaceChildren();
  if (!points.length) {
    list.append(element("div", "empty-inline", "反复查询后，这里会自动生成复习清单。"));
    return;
  }
  for (const point of points) {
    const item = element("article", "review-item");
    const summary = element("div", "review-summary");
    summary.append(
      element("h3", "", point.concept),
      element("p", "", `已查询 ${point.query_count} 次 · 最近 ${formatDate(point.last_queried_at)}`),
      element("p", "", `记忆版本：${point.artifact_ref || "—"}`),
    );
    const materials = element("div", "review-materials");
    for (const material of point.materials || []) {
      const card = element("div", "review-material");
      card.append(
        element("strong", "", material.source || sourceFor(material.metadata)),
        element("p", "", material.text),
      );
      const button = element("button", "text-button", "查看原文与上下文 →");
      button.type = "button";
      button.addEventListener("click", () => openContext(material.chunk_id));
      card.append(button);
      materials.append(card);
    }
    if (!(point.materials || []).length) {
      materials.append(element("p", "muted", "关联原文已变化，请重新检索该知识点。"));
    }
    item.append(summary, materials);
    list.append(item);
  }
}

function renderAudit(audit) {
  const searches = $("#search-logs");
  searches.replaceChildren();
  if (!audit.searches.length) {
    searches.append(element("p", "muted", "暂无检索记录"));
  }
  for (const log of audit.searches.slice(0, 6)) {
    const item = element("div", "audit-item");
    const top = element("div", "audit-item-top");
    top.append(element("strong", "", log.query_text), element("span", "http-status", log.status));
    item.append(top, element("p", "", `${log.search_mode} · ${log.result_count} 条 · ${log.latency_ms} ms`));
    item.append(element("p", "", `${formatDate(log.created_at)} · ${log.search_id}`));
    searches.append(item);
  }

  const memories = $("#memory-logs");
  memories.replaceChildren();
  if (!audit.memory_operations.length) {
    memories.append(element("p", "muted", "暂无记忆记录"));
  }
  for (const log of audit.memory_operations.slice(0, 8)) {
    const item = element("div", "audit-item");
    const top = element("div", "audit-item-top");
    top.append(element("strong", "", log.operation), element("span", "http-status", `${log.http_method} ${log.status_code ?? "—"}`));
    item.append(top, element("p", "", log.endpoint));
    if (log.artifact_ref) item.append(element("p", "", log.artifact_ref));
    item.append(element("p", "", `${formatDate(log.created_at)} · Request ID: ${log.powercontext_request_id || "—"}`));
    memories.append(item);
  }

  const candidates = $("#candidate-logs");
  candidates.replaceChildren();
  const latest = audit.searches[0];
  const items = latest ? audit.search_items.filter((item) => item.search_id === latest.search_id) : [];
  if (!items.length) {
    candidates.append(element("p", "muted", "完成一次检索后可查看 RRF 与加权明细。"));
    return;
  }
  const table = element("table");
  const thead = element("thead");
  const header = element("tr");
  for (const label of ["Chunk ID", "RRF 排名", "RRF 分数", "薄弱点加权", "最终分数", "最终排名"]) {
    header.append(element("th", "", label));
  }
  thead.append(header);
  const tbody = element("tbody");
  for (const item of items) {
    const row = element("tr");
    const id = element("td");
    id.append(element("code", "", item.chunk_id));
    row.append(
      id,
      element("td", "", item.rrf_rank),
      element("td", "", Number(item.rrf_score).toFixed(6)),
      element("td", "", Number(item.weak_boost).toFixed(4)),
      element("td", "", Number(item.final_score).toFixed(6)),
      element("td", "", item.final_rank),
    );
    tbody.append(row);
  }
  table.append(thead, tbody);
  candidates.append(table);
}

function renderResults(data) {
  const meta = $("#search-meta");
  meta.hidden = false;
  meta.textContent = `${data.results.length} 条结果 · ${data.candidate_count} 个融合候选 · ${data.latency_ms} ms · Search ID ${data.search_id}`;
  const list = $("#search-results");
  list.replaceChildren();
  if (!data.results.length) {
    const empty = element("div", "empty-state");
    empty.append(element("h3", "", "没有找到相关原文"), element("p", "", "换个关键词，或先导入包含该知识点的课程资料。"));
    list.append(empty);
    return;
  }
  for (const result of data.results) {
    const card = element("article", "result-card");
    const top = element("div", "result-top");
    top.append(element("span", "result-rank", String(result.final_rank).padStart(2, "0")));
    const heading = element("div", "result-heading");
    heading.append(
      element("h3", "", result.metadata.knowledge_point || result.metadata.section_path),
      element("span", "result-source", result.source),
    );
    top.append(heading);
    card.append(top, element("p", "result-text", result.text));
    const footer = element("div", "result-footer");
    const scores = element("div", "score-tags");
    scores.append(element("span", "score-tag", `RRF #${result.rrf_rank}`));
    if (result.weak_boost > 0) scores.append(element("span", "score-tag boosted", `薄弱点加权 +${result.weak_boost}`));
    const button = element("button", "text-button", "查看上下文 →");
    button.type = "button";
    button.addEventListener("click", () => openContext(result.chunk_id));
    footer.append(scores, button);
    card.append(footer);
    list.append(card);
  }
}

async function openContext(chunkId) {
  const dialog = $("#context-dialog");
  const content = $("#context-content");
  content.replaceChildren(element("p", "muted", "正在读取原文上下文…"));
  dialog.showModal();
  try {
    const data = await api(`/api/chunks/${encodeURIComponent(chunkId)}?${userQuery()}`);
    content.replaceChildren();
    for (const block of data.context) {
      const section = element("section", `context-block${block.is_target ? " target" : ""}`);
      section.append(
        element("strong", "", `${block.is_target ? "命中原文 · " : "上下文 · "}${sourceFor(block.metadata)}`),
        element("p", "", block.text),
      );
      content.append(section);
    }
  } catch (error) {
    content.replaceChildren(element("p", "muted", error.message));
  }
}

async function loadDocuments() {
  const data = await api(`/api/documents?${userQuery()}`);
  renderDocuments(data.documents);
}

async function loadMemoryAndReview() {
  const [memory, review] = await Promise.all([
    api(`/api/memory?${userQuery()}`),
    api(`/api/review?${userQuery()}`),
  ]);
  renderWeakPoints(memory.weak_points);
  renderReview(review.weak_points);
}

async function loadAudit() {
  renderAudit(await api(`/api/audit?${userQuery()}`));
}

async function loadDashboard() {
  const results = await Promise.allSettled([loadDocuments(), loadMemoryAndReview(), loadAudit()]);
  const failed = results.find((result) => result.status === "rejected");
  if (failed) showToast(failed.reason.message, true);
}

async function importSamples() {
  const button = $("#import-samples");
  setBusy(button, true, "正在导入…");
  const status = $("#import-status");
  status.className = "import-status";
  status.textContent = "正在切块、生成本地向量并写入 seekdb…";
  try {
    const data = await api("/api/import-samples", {
      method: "POST",
      body: JSON.stringify({ user_id: state.userId }),
    });
    renderDocuments(data.documents);
    const imported = data.outcomes.filter((item) => item.status === "imported").length;
    const skipped = data.outcomes.filter((item) => item.status === "skipped").length;
    status.classList.add("success");
    status.textContent = `示例资料处理完成：新导入 ${imported} 个，跳过 ${skipped} 个。`;
    showToast("示例资料已就绪，可以开始检索。 ");
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function importFiles(files) {
  if (!files.length) return;
  const status = $("#import-status");
  const picker = $("#file-picker");
  const supported = files.filter((file) => /\.(md|txt|pdf)$/i.test(file.name));
  if (!supported.length) {
    status.className = "import-status error";
    status.textContent = "所选文件夹中没有 Markdown、TXT 或 PDF 文件。";
    return;
  }
  picker.textContent = "正在导入…";
  status.className = "import-status";
  status.textContent = `正在处理 ${supported.length} 个文件，首次运行可能需要加载本地向量模型…`;
  const body = new FormData();
  body.append("user_id", state.userId);
  for (const file of supported) body.append("files", file, file.webkitRelativePath || file.name);
  try {
    const data = await api("/api/import", { method: "POST", body });
    renderDocuments(data.documents);
    const imported = data.outcomes.filter((item) => item.status === "imported").length;
    const failed = data.outcomes.filter((item) => item.status === "failed");
    const skipped = data.outcomes.filter((item) => item.status === "skipped").length;
    status.classList.add(failed.length ? "error" : "success");
    status.textContent = `处理完成：新导入 ${imported} 个，跳过 ${skipped} 个，失败 ${failed.length} 个。${failed.length ? ` ${failed[0].file}：${failed[0].error}` : ""}`;
    showToast(failed.length ? "部分文件导入失败，请查看详情。" : "课程资料导入完成。", failed.length > 0);
  } catch (error) {
    status.classList.add("error");
    status.textContent = error.message;
    showToast(error.message, true);
  } finally {
    picker.textContent = "选择文件夹并导入";
    $("#file-input").value = "";
  }
}

$("#user-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("#user-id");
  if (!input.reportValidity()) return;
  state.userId = input.value.trim();
  localStorage.setItem("course-review-user", state.userId);
  $("#search-results").replaceChildren();
  $("#search-results").append(element("div", "empty-state", "已切换学习空间，请输入问题开始检索。"));
  $("#search-meta").hidden = true;
  await loadDashboard();
  showToast(`已进入学习空间 ${state.userId}`);
});

$("#file-input").addEventListener("change", (event) => importFiles([...event.target.files]));
$("#import-samples").addEventListener("click", importSamples);
$("#refresh-audit").addEventListener("click", async () => {
  const button = $("#refresh-audit");
  setBusy(button, true, "刷新中…");
  try { await loadAudit(); } catch (error) { showToast(error.message, true); } finally { setBusy(button, false); }
});

for (const button of document.querySelectorAll("[data-query]")) {
  button.addEventListener("click", () => {
    $("#query").value = button.dataset.query;
    $("#query").focus();
  });
}

$("#search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = $("#query").value.trim();
  if (!query) return;
  const button = $("#search-button");
  setBusy(button, true, "检索中…");
  try {
    const data = await api("/api/search", {
      method: "POST",
      body: JSON.stringify({ user_id: state.userId, query }),
    });
    renderResults(data);
    await Promise.all([loadMemoryAndReview(), loadAudit()]);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
});

$("#close-context").addEventListener("click", () => $("#context-dialog").close());
$("#context-dialog").addEventListener("click", (event) => {
  if (event.target === $("#context-dialog")) $("#context-dialog").close();
});

$("#user-id").value = state.userId;
checkHealth();
loadDashboard();
