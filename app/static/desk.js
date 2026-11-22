import {at, drawAxis, drawSlip, tag} from "./exhibits.js";
import {drawTable, views} from "./register.js";

const state = {document: null, resume: null, pinned: null, history: [], stage: "zones", tab: 0, roll: "", busy: false};
const navigation = [...document.querySelectorAll("nav [data-view]")];
const form = at("plan-form");
const sample = at("sample");
const kerf = at("kerf");
const exportLink = at("export");
const formatter = new Intl.DateTimeFormat("zh-CN", {timeZone: "Asia/Shanghai", dateStyle: "short", timeStyle: "medium"});

async function fetchData(path, method = "GET", body) {
  const options = body === undefined ? {method} : {method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)};
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message ?? `请求失败 ${response.status}`);
  return data;
}

function notice(text = "", failed = false) {
  const node = at("operation");
  node.hidden = !text;
  node.textContent = text;
  node.dataset.error = String(failed);
}

function archiveControls() {
  const manifest = state.document?.manifest;
  const archived = manifest?.sample === sample.value && manifest?.kerf_mm === Number(kerf.value);
  for (const control of [sample, kerf, at("submit")]) control.disabled = state.busy;
  at("rerun").disabled = !archived || state.busy;
  at("print").disabled = !archived || state.busy || !state.roll;
  if (archived && !state.busy) exportLink.href = `/api/export/${manifest.id}`;
  else exportLink.removeAttribute("href");
  exportLink.setAttribute("aria-disabled", String(!archived || state.busy));
}

function heading() {
  const manifest = state.document?.manifest;
  at("archive-state").textContent = state.busy ? "正在排版" : manifest ? "已归档" : state.document ? "样例预览" : "暂无卷宗";
  at("archive-ref").textContent = manifest?.id.slice(0, 12) ?? "—";
  at("archive-ref").title = manifest?.id ?? "";
  const stamp = at("archive-date");
  stamp.dateTime = manifest?.created_at ?? "";
  stamp.textContent = manifest ? `${formatter.format(new Date(manifest.created_at))} · UTC+08:00` : "";
  const totals = state.document?.snapshot.ledger.totals;
  for (const name of ["length", "piece", "blocked", "kerf", "unused", "delta"]) {
    at(name === "kerf" ? "kerf-total" : name).textContent = totals?.[name] ?? "—";
  }
}

function rollPanel() {
  const data = state.document?.snapshot;
  const rolls = data?.zones.rolls ?? [];
  if (!rolls.some((roll) => roll.id === state.roll)) state.roll = rolls[0]?.id ?? "";
  const picker = at("roll-picker");
  const sourceFocus = picker.contains(document.activeElement);
  picker.replaceChildren(...rolls.map((roll) => {
    const button = tag("button", roll.id);
    button.type = "button";
    button.dataset.roll = roll.id;
    button.dataset.held = String(roll.held);
    button.setAttribute("aria-pressed", String(roll.id === state.roll));
    return button;
  }));
  if (sourceFocus) picker.querySelector("[aria-pressed=true]")?.focus();
  const slip = data?.slips.find((item) => item.roll === state.roll);
  drawAxis(data?.ledger.rolls.find((roll) => roll.roll === state.roll), slip);
  const resume = state.resume?.rolls.find((item) => item.roll === state.roll) ?? null;
  drawSlip(slip, state.document?.manifest, data?.fit.kerf_mm, resume);
  resumePanel();
}

function resumePanel() {
  const manifest = state.document?.manifest;
  const sheet = state.resume;
  const form = at("receipt-form");
  form.hidden = !(manifest && sheet && state.roll);
  if (!form.hidden) {
    const row = sheet.rolls.find((item) => item.roll === state.roll);
    const next = row?.resume?.next_cut_mm;
    at("receipt-cut").placeholder = next ?? "535";
    at("receipt-cut").value = "";
    at("receipt-id").value = "";
  }
  const history = at("resume-history");
  const versions = sheet?.version ?? 0;
  const isOld = state.pinned !== null && state.pinned !== undefined;
  history.hidden = !manifest || !sheet;
  if (!history.hidden) {
    history.replaceChildren(tag("span", isOld
      ? `只读回看第 ${versions} 版 · 当前第 ${sheet.latest_version ?? versions} 版`
      : versions ? `确认单第 ${versions} 版 · 批次 ${manifest.id.slice(0, 12)}` : "尚无落刀回执"));
    if (isOld) {
      const back = tag("button", "回到当前版本");
      back.type = "button";
      back.dataset.versions = "latest";
      history.append(back);
    } else if (versions) {
      const link = tag("button", "查看旧版签条");
      link.type = "button";
      link.dataset.versions = "previous";
      history.append(link);
    }
  }
}

function recordsPanel() {
  const tabs = views(state.stage, state.document?.snapshot, state.roll, state.history, state.resume);
  at("view-title").textContent = navigation.find((button) => button.dataset.view === state.stage).textContent;
  const group = at("record-tabs");
  const restoreFocus = group.contains(document.activeElement);
  group.replaceChildren(...tabs.map(([label], index) => {
    const button = tag("button", label);
    button.type = "button";
    button.dataset.tab = index;
    button.setAttribute("aria-pressed", String(index === state.tab));
    return button;
  }));
  if (restoreFocus) group.querySelector("[aria-pressed=true]")?.focus();
  if (state.tab >= tabs.length) state.tab = 0;
  drawTable(tabs[state.tab]);
}

function draw() {
  heading();
  rollPanel();
  recordsPanel();
  archiveControls();
}

function setRun(document) {
  state.document = document;
  if (document.manifest) {
    sample.value = document.manifest.sample;
    kerf.value = document.manifest.kerf_mm;
  }
}

async function loadResume() {
  const manifest = state.document?.manifest;
  try {
    state.resume = manifest
      ? await fetchData(`/api/resume/${manifest.id}`)
      : await fetchData(`/api/resume?sample=${sample.value}&kerf_mm=${kerf.value}`);
    state.pinned = null;
  } catch (error) {
    state.resume = null;
    state.pinned = null;
  }
}

async function preview() {
  const query = new URLSearchParams({sample: sample.value, kerf_mm: kerf.value});
  setRun(await fetchData(`/api/preview?${query}`));
}

async function recent() {
  state.history = (await fetchData("/api/runs")).runs;
}

async function action(work) {
  if (state.busy) return;
  state.busy = true;
  notice();
  heading();
  archiveControls();
  try {
    await work();
    at("sync-state").textContent = "服务在线";
  } catch (error) {
    notice(`${error.message}，请核对后重试。`, true);
    at("sync-state").textContent = "作业失败";
  } finally {
    state.busy = false;
    draw();
  }
}

async function reload() {
  await loadResume();
  draw();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  action(async () => {
    const outcome = await fetchData("/api/runs", "POST", {sample: sample.value, kerf_mm: Number(kerf.value)});
    setRun(await fetchData(`/api/runs/${outcome.manifest.id}`));
    await recent();
    await loadResume();
    notice(outcome.reused ? "沿用原归档" : "卷宗已归档");
  });
});
sample.addEventListener("change", () => {
  if (kerf.reportValidity()) action(async () => {
    await preview();
    await loadResume();
    draw();
  });
  else archiveControls();
});
kerf.addEventListener("input", archiveControls);
at("rerun").addEventListener("click", () => action(async () => {
  const id = state.document.manifest.id;
  await fetchData(`/api/runs/${id}/rerun`, "POST");
  notice("重算与归档一致");
}));
at("print").addEventListener("click", () => window.print());
for (const button of navigation) button.addEventListener("click", () => {
  state.stage = button.dataset.view;
  state.tab = 0;
  navigation.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  recordsPanel();
});
at("record-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-tab]");
  if (button) {
    state.tab = Number(button.dataset.tab);
    recordsPanel();
  }
});
function chooseRoll(roll) {
  state.roll = roll;
  rollPanel();
  if (state.stage === "zones" || state.stage === "resume") recordsPanel();
  archiveControls();
}
at("roll-picker").addEventListener("click", (event) => {
  const button = event.target.closest("[data-roll]");
  if (button) chooseRoll(button.dataset.roll);
});
at("record-table").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button?.dataset.roll) chooseRoll(button.dataset.roll);
  if (button?.dataset.open) action(async () => {
    setRun(await fetchData(`/api/runs/${button.dataset.open}`));
    await loadResume();
    draw();
  });
});

at("receipt-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const manifest = state.document?.manifest;
  if (!manifest || !state.roll) return;
  const receipt = at("receipt-id").value.trim();
  const cut = Number(at("receipt-cut").value);
  if (!receipt || !Number.isInteger(cut) || cut < 1) {
    notice("回执号与整数落刀位置都要填。", true);
    return;
  }
  action(async () => {
    const result = await fetchData(`/api/resume/${manifest.id}/receipts`, "POST",
      {receipt_id: receipt, roll: state.roll, cuts: [cut]});
    notice(result.replayed ? "同一回执已登记过，未重复落刀" : `落刀已登记，确认单第 ${result.version} 版`);
    await reload();
  });
});
at("resume-history").addEventListener("click", (event) => {
  const button = event.target.closest("[data-versions]");
  if (!button || !state.resume) return;
  action(async () => {
    const manifest = state.document.manifest;
    if (button.dataset.versions === "latest") {
      state.pinned = null;
      await loadResume();
      notice("已回到当前版本的续裁确认单");
      draw();
      return;
    }
    const overview = await fetchData(`/api/resume/${manifest.id}/history`);
    const latest = overview.versions.at(-1)?.version;
    if (latest === undefined) {
      notice("还没有已存版本的签条。");
      return;
    }
    const previous = overview.versions.at(-2)?.version ?? 0;
    const archive = await fetchData(`/api/resume/${manifest.id}/versions/${previous}`);
    state.resume = {...archive.document, version: archive.version, latest_version: latest,
      stored_versions: overview.versions.length, receipts: overview.receipts};
    state.pinned = archive.version;
    notice(`只读回看第 ${archive.version} 版签条；当前第 ${latest} 版仍保留，已切记录未删除`);
    draw();
  });
});

action(async () => {
  await recent();
  if (state.history.length) setRun(await fetchData(`/api/runs/${state.history[0].id}`));
  else await preview();
  await loadResume();
});
