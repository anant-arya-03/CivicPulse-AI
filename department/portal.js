"use strict";

const element = (id) => document.getElementById(id);
const labels = {
  SUBMITTED: "New",
  ACKNOWLEDGED: "Acknowledged",
  IN_PROGRESS: "In progress",
  REOPENED: "Reopened",
  RESOLVED_PENDING_VERIFICATION: "Awaiting citizen verification",
  VERIFIED_RESOLVED: "Verified resolved",
  CLOSED: "Closed",
  CANCELLED: "Cancelled",
};
const actionable = new Set(["SUBMITTED", "ACKNOWLEDGED", "IN_PROGRESS", "REOPENED"]);
const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
let accessCode = "";
let session = 0;
let reports = [];
let selectedId = null;
let refreshing = false;
let updating = false;
let noticeTimer;
let photoUrls = [];
let photoRequest = 0;

async function requestResponse(code, path = "", update) {
  const headers = { Authorization: `Bearer ${code}`, Accept: "application/json" };
  if (update) headers["Content-Type"] = "application/json";
  const response = await fetch(`/api/v1/department/reports${path}`, {
    method: update ? "POST" : "GET",
    headers,
    credentials: "omit",
    cache: "no-store",
    signal: AbortSignal.timeout(12_000),
    body: update ? JSON.stringify({ update }) : undefined,
  });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    const error = new Error(result?.error?.message || "The inbox could not be reached. Try again.");
    error.status = response.status;
    throw error;
  }
  return response;
}

async function request(code, path, update) {
  return (await requestResponse(code, path, update)).json();
}

function showError(id, message = "") {
  element(id).textContent = message;
  element(id).hidden = !message;
}

function notify(message) {
  window.clearTimeout(noticeTimer);
  element("notice").textContent = message;
  noticeTimer = window.setTimeout(() => { element("notice").textContent = ""; }, 10_000);
}

function renderDetail() {
  const selected = reports.find((item) => item.id === selectedId);
  element("choose-report").hidden = Boolean(selected);
  element("report").hidden = !selected;
  if (!selected) return;
  element("report-reference").textContent = selected.reference;
  element("report-title").textContent = selected.subject;
  element("report-status").textContent = labels[selected.status] ?? selected.status;
  element("received").textContent = selected.received_at
    ? `Received ${dateFormat.format(new Date(selected.received_at))}`
    : "";
  element("report-body").textContent = selected.body;
  element("load-photos").hidden = !selected.attachment_ids.length || photoUrls.length > 0;
  const canUpdate = actionable.has(selected.status);
  element("start-work").hidden = !canUpdate || selected.status === "IN_PROGRESS";
  element("repair-complete").hidden = !canUpdate;
  element("repair-note").hidden = !canUpdate;
  element("start-work").disabled = updating;
  element("repair-complete").disabled = updating;
}

function renderReports() {
  const list = element("reports");
  const focused = document.activeElement?.dataset.reportId;
  list.replaceChildren();
  for (const report of reports) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const reference = document.createElement("span");
    const subject = document.createElement("strong");
    const status = document.createElement("span");
    button.type = "button";
    button.dataset.reportId = report.id;
    button.setAttribute("aria-pressed", String(report.id === selectedId));
    reference.className = "reference";
    reference.textContent = report.reference;
    subject.textContent = report.subject;
    status.className = "row-status";
    status.textContent = labels[report.status] ?? report.status;
    button.append(reference, subject, status);
    button.addEventListener("click", () => {
      if (selectedId !== report.id) clearPhotos();
      selectedId = report.id;
      showError("inbox-error");
      for (const row of list.querySelectorAll("button")) {
        row.setAttribute("aria-pressed", String(row.dataset.reportId === selectedId));
      }
      renderDetail();
    });
    item.append(button);
    list.append(item);
    if (focused === report.id) button.focus();
  }
  element("empty").hidden = reports.length !== 0;
  element("report-count").textContent = String(reports.length);
  renderDetail();
}

function signOut() {
  session += 1;
  accessCode = "";
  reports = [];
  selectedId = null;
  clearPhotos();
  window.clearTimeout(noticeTimer);
  element("notice").textContent = "";
  showError("inbox-error");
  renderReports();
  element("report-body").textContent = "";
  element("workspace").hidden = true;
  element("sign-out").hidden = true;
  element("gate").hidden = false;
  element("access-code").focus();
}

function clearPhotos() {
  photoRequest += 1;
  for (const url of photoUrls) URL.revokeObjectURL(url);
  photoUrls = [];
  element("photos").replaceChildren();
  element("load-photos").disabled = false;
}

async function loadPhotos() {
  const report = reports.find((item) => item.id === selectedId);
  if (!report) return;
  const requestId = ++photoRequest;
  element("load-photos").disabled = true;
  showError("inbox-error");
  try {
    const blobs = await Promise.all(report.attachment_ids.map(async (id) => {
      const response = await requestResponse(accessCode, `/${report.id}/attachments/${id}`);
      return response.blob();
    }));
    if (requestId !== photoRequest) return;
    photoUrls = blobs.map((blob) => URL.createObjectURL(blob));
    for (const [index, url] of photoUrls.entries()) {
      const photo = document.createElement("img");
      photo.src = url;
      photo.alt = `Submitted evidence photo ${index + 1}`;
      element("photos").append(photo);
    }
    renderDetail();
  } catch (error) {
    if (requestId === photoRequest) showError("inbox-error", error.message);
  } finally {
    if (requestId === photoRequest) element("load-photos").disabled = false;
  }
}

async function refresh() {
  if (!accessCode || refreshing || updating || document.hidden) return;
  refreshing = true;
  const activeSession = session;
  try {
    const inbox = await request(accessCode);
    if (activeSession !== session || updating) return;
    const existing = new Set(reports.map((item) => item.id));
    const incoming = inbox.reports.filter((item) => !existing.has(item.id));
    if (incoming.length === 1) {
      notify(`New report received: ${incoming[0].reference}.`);
    } else if (incoming.length > 1) {
      notify(`${incoming.length} new reports received.`);
    }
    if (JSON.stringify(reports) !== JSON.stringify(inbox.reports)) {
      reports = inbox.reports;
      renderReports();
    }
    element("connection-status").textContent = "Live updates";
  } catch (error) {
    if (activeSession !== session) return;
    if (error.status === 401) {
      signOut();
      showError("sign-in-error", error.message);
    } else {
      element("connection-status").textContent = "Reconnecting";
    }
  } finally {
    refreshing = false;
  }
}

async function updateReport(update) {
  if (!selectedId || updating) return;
  const activeSession = session;
  updating = true;
  renderDetail();
  showError("inbox-error");
  try {
    const report = await request(accessCode, `/${selectedId}/status`, update);
    if (activeSession !== session) return;
    reports = reports.map((item) => item.id === report.id ? report : item);
    renderReports();
    notify(update === "repair_complete"
      ? `Repair reported for ${report.reference}. The citizen can now verify it.`
      : `Work started on ${report.reference}.`);
    if (selectedId === report.id) {
      element("report-title").setAttribute("tabindex", "-1");
      element("report-title").focus();
    }
  } catch (error) {
    if (activeSession === session) showError("inbox-error", error.message);
  } finally {
    updating = false;
    renderDetail();
  }
}

element("sign-in").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = element("access-code");
  const submit = element("open-inbox");
  const code = input.value.trim();
  submit.disabled = true;
  showError("sign-in-error");
  try {
    const inbox = await request(code);
    accessCode = code;
    session += 1;
    input.value = "";
    reports = inbox.reports;
    element("department-name").textContent = inbox.department;
    element("connection-status").textContent = "Live updates";
    element("gate").hidden = true;
    element("workspace").hidden = false;
    element("sign-out").hidden = false;
    renderReports();
    element("inbox-title").focus();
  } catch (error) {
    showError("sign-in-error", error.message);
  } finally {
    submit.disabled = false;
  }
});

element("sign-out").addEventListener("click", signOut);
element("load-photos").addEventListener("click", () => void loadPhotos());
element("start-work").addEventListener("click", () => void updateReport("start_work"));
element("repair-complete").addEventListener("click", () => void updateReport("repair_complete"));
element("access-code").disabled = false;
element("open-inbox").disabled = false;
window.setInterval(() => void refresh(), 3_000);
document.addEventListener("visibilitychange", () => void refresh());
