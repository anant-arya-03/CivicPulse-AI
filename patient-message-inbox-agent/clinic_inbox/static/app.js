"use strict";
const byId = (id) => document.getElementById(id);
const text = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
const statuses = {
  new: "Unprocessed",
  awaiting_review: "Awaiting review",
  done: "Reviewed",
  error: "Needs attention",
};
const flags = {
  from_safety_screen: "Safety screen",
  cancellation: "Cancellation",
  claims_completion: "Completion claim",
  possible_result_interpretation: "Possible result interpretation",
  mentions_other_patient: "Other patient mentioned",
};
const queues = {
  urgent_nurse: "Urgent nurse",
  clinician: "Clinician",
  front_desk: "Front desk",
  admin: "Administration",
  nurse: "Nurse",
};
let messages = [],
  selected = null,
  busy = false,
  reviewer = "";
const drafts = new Map();
const date = (iso, options) =>
  new Date(iso).toLocaleString("en-GB", {
    timeZone: "Asia/Kolkata",
    ...options,
  });
const time = (iso) => date(iso, { hour: "2-digit", minute: "2-digit" });
const fullDate = (iso) =>
  date(iso, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }) + " IST";
function avatar(m) {
  const letters = m.patient.name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0])
    .join("");
  const color =
    [...m.patient_id].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % 5;
  return (
    '<span aria-hidden="true" class="avatar a' +
    color +
    '">' +
    text(letters) +
    "</span>"
  );
}
function badge(m) {
  const urgent = m.urgent && m.status === "awaiting_review";
  return (
    '<span class="pill ' +
    (urgent ? "urgent" : text(m.status)) +
    '">' +
    text(urgent ? "Urgent review" : statuses[m.status]) +
    "</span>"
  );
}
function notice(message, error = false) {
  byId("notice").className = message ? "banner" + (error ? " bad" : "") : "";
  byId("notice").textContent = message;
}
async function api(path, body) {
  const options = body
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    : {};
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new Error(
      "Cannot reach the local inbox. Check that the server is running and press Refresh.",
    );
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok)
    throw new Error(data.error || "Unable to load the inbox. Please refresh.");
  return data;
}
function visibleMessages() {
  const query = byId("search").value.trim().toLowerCase(),
    filter = byId("filter").value;
  return messages.filter(
    (m) =>
      (filter === "all" ||
        (filter === "urgent"
          ? m.urgent && m.status === "awaiting_review"
          : m.status === filter)) &&
      [m.patient.name, m.patient_id, m.message_id, m.text]
        .join(" ")
        .toLowerCase()
        .includes(query),
  );
}
function drawQueue() {
  const visible = visibleMessages();
  if (!visible.some((m) => m.message_id === selected))
    selected = visible[0]?.message_id ?? null;
  byId("queueCount").textContent = visible.length;
  byId("pendingCount").textContent = messages.filter(
    (m) => m.status === "awaiting_review",
  ).length;
  byId("urgentCount").textContent = messages.filter(
    (m) => m.urgent && m.status === "awaiting_review",
  ).length;
  byId("errorCount").textContent = messages.filter(
    (m) => m.status === "error",
  ).length;
  document
    .querySelectorAll("[data-filter]")
    .forEach((b) =>
      b.setAttribute(
        "aria-pressed",
        String(b.dataset.filter === byId("filter").value),
      ),
    );
  byId("messages").innerHTML =
    visible
      .map(
        (m) =>
          '<button class="message" data-id="' +
          text(m.message_id) +
          '" aria-current="' +
          (m.message_id === selected) +
          '">' +
          avatar(m) +
          '<span class="rowtext"><span class="rowtitle"><b>' +
          text(m.patient.name) +
          "</b><small>" +
          time(m.sent) +
          '</small></span><span class="excerpt">' +
          text(m.text) +
          "</span>" +
          badge(m) +
          "</span></button>",
      )
      .join("") ||
    '<p class="empty">No matching messages. Change the filter or search text.</p>';
}
function slotInfo(p, key) {
  const s = p[key];
  if (!s) return text(p.payload[key] || "");
  const doctor =
    { PR1: "Dr Iyer", PR2: "Dr Mehta" }[s.practitioner_id] || s.practitioner_id;
  return text(fullDate(s.start) + " · " + doctor);
}
function proposal(m, p) {
  const x = p.payload;
  let title, detail;
  if (p.kind === "route") {
    title = "Staff routing";
    detail = text(queues[x.queue] || x.queue) + " · " + text(x.reason);
  } else if (p.kind === "reply") {
    title = "Draft reply";
    detail = text(x.text);
  } else {
    title =
      {
        book: "Book appointment",
        reschedule: "Move appointment",
        cancel: "Cancel appointment",
      }[x.action] || "Appointment change";
    detail = [
      x.appointment_id ? "Booking " + text(x.appointment_id) : "",
      x.original_slot_id ? "Current: " + slotInfo(p, "original_slot_id") : "",
      x.slot_id ? "Requested: " + slotInfo(p, "slot_id") : "",
    ]
      .filter(Boolean)
      .join("<br>");
  }
  const marks = p.flags
    .map((f) => '<span class="flag">' + text(flags[f] || f) + "</span>")
    .join("");
  let controls = "";
  if (m.status === "awaiting_review") {
    const decisions = drafts.get(m.message_id) || {};
    controls =
      '<div class="options" role="group" aria-label="' +
      text(title) +
      ' decision">' +
      ["approved", "rejected"]
        .map(
          (value) =>
            '<label class="choice"><input type="radio" name="decision-' +
            p.id +
            '" data-proposal="' +
            p.id +
            '" value="' +
            value +
            '" required ' +
            (decisions[p.id] === value ? "checked" : "") +
            ">" +
            (value === "approved" ? "Approve" : "Reject") +
            "</label>",
        )
        .join("") +
      "</div>";
  } else if (p.reviewer) {
    const result =
      { applied: "Applied", failed: "Failed", rejected: "Rejected" }[
        p.status
      ] || p.status;
    controls =
      '<p class="audit">' +
      text(result + " · " + p.reviewer + " · " + fullDate(p.at)) +
      (p.outcome?.reason ? "<br>" + text(p.outcome.reason) : "") +
      "</p>";
  }
  return (
    '<div class="proposal"><div class="prophead"><strong>' +
    text(title) +
    '</strong><span class="flags">' +
    marks +
    '</span></div><p class="bodytext">' +
    detail +
    "</p>" +
    controls +
    "</div>"
  );
}
function drawDetail() {
  const target = byId("detail"),
    m = messages.find((row) => row.message_id === selected);
  if (!m) {
    target.innerHTML =
      '<div class="empty">Select a message from the queue to see its details.</div>';
    return;
  }
  let work = "";
  if (m.status === "new" || m.status === "error") {
    work =
      m.status === "error"
        ? '<div class="errorbox"><h3>Manual follow-up needed</h3><p class="bodytext">The agent could not finish this message. ' +
          (m.retryable
            ? "Check the model connection and retry preparation."
            : "Review the original message and handle it through the clinic’s manual workflow.") +
          '</p><span class="meta">Error · ' +
          text(m.error) +
          "</span></div>"
        : '<div><h3>Prepare this message</h3><p class="bodytext">Run the inbox agent to prepare proposals for staff review.</p></div>';
    if (m.status === "new" || m.retryable)
      work +=
        '<div><button id="prepare" class="primary">' +
        (m.retryable ? "Retry preparation" : "Prepare proposals") +
        "</button></div>";
  } else {
    const pending = m.status === "awaiting_review";
    work =
      '<form id="review"><div class="flex sectiontitle"><h3>' +
      (pending ? "Review proposals" : "Review record") +
      '</h3><span class="number">' +
      m.proposals.length +
      "</span></div>" +
      (pending
        ? '<p class="hint">Choose a decision for each proposal, then save your review.</p>'
        : "") +
      '<div class="proposals">' +
      m.proposals.map((p) => proposal(m, p)).join("") +
      "</div>" +
      (pending
        ? '<div class="save"><label>Reviewer name<input id="reviewer" required maxlength="80" autocomplete="name" placeholder="Your name" value="' +
          text(reviewer) +
          '"></label><button class="primary" type="submit">Save review</button></div>'
        : "") +
      "</form>";
  }
  target.innerHTML =
    '<div class="detailtop"><div class="topmeta"><span class="meta">Message ' +
    text(m.message_id) +
    "</span>" +
    badge(m) +
    '</div><div class="person">' +
    avatar(m) +
    "<div><h2>" +
    text(m.patient.name) +
    '</h2><p class="meta">' +
    text(m.patient_id + " · " + m.patient.doctor + " · " + m.patient.language) +
    "</p></div></div></div>" +
    '<div class="detailbody"><div><div class="flex sectiontitle"><h3>Patient message</h3><span class="meta">' +
    text(fullDate(m.sent)) +
    '</span></div><blockquote class="quote">' +
    text(m.text) +
    "</blockquote></div>" +
    work +
    "</div>";
}
function render() {
  drawQueue();
  drawDetail();
  setBusy(busy);
}
function setBusy(state) {
  busy = state;
  document
    .querySelectorAll("button,select,input")
    .forEach((el) => (el.disabled = state));
  byId("detail").setAttribute("aria-busy", String(state));
}
async function reload() {
  const data = await api("/api/inbox");
  messages = data.messages;
  render();
}
async function refresh() {
  if (busy) return;
  setBusy(true);
  try {
    await reload();
    notice("");
  } catch (err) {
    notice(err.message, true);
  } finally {
    setBusy(false);
  }
}
async function mutate(action, body) {
  if (busy || !selected) return;
  const mid = selected;
  setBusy(true);
  notice(
    action === "review"
      ? "Saving review…"
      : "Preparing proposals. Model processing may take a moment…",
  );
  try {
    await api("/api/messages/" + encodeURIComponent(mid) + "/" + action, body);
    await reload();
    drafts.delete(mid);
    const message = messages.find((m) => m.message_id === mid);
    const failed = message?.proposals.some((p) => p.status === "failed");
    if (message?.status === "error")
      notice(
        mid + " needs manual follow-up. See the preparation error below.",
        true,
      );
    else if (failed)
      notice(
        "Review saved. A calendar change could not be applied. See the review record.",
        true,
      );
    else
      notice(
        action === "review"
          ? "Review saved for " +
              mid +
              ". Decisions are recorded in the audit log."
          : "Proposals are ready for review.",
      );
  } catch (err) {
    notice(err.message, true);
  } finally {
    setBusy(false);
  }
}
byId("refresh").addEventListener("click", refresh);
byId("search").addEventListener("input", render);
byId("filter").addEventListener("change", render);
document.querySelector(".stats").addEventListener("click", (e) => {
  const button = e.target.closest("[data-filter]");
  if (!button) return;
  byId("filter").value =
    byId("filter").value === button.dataset.filter
      ? "all"
      : button.dataset.filter;
  render();
});
byId("messages").addEventListener("click", (e) => {
  const button = e.target.closest("[data-id]");
  if (!button) return;
  selected = button.dataset.id;
  render();
  if (matchMedia("(max-width:660px)").matches)
    byId("detail").scrollIntoView({ block: "start" });
});
byId("detail").addEventListener("change", (e) => {
  if (!e.target.dataset.proposal) return;
  const decisions = drafts.get(selected) || {};
  decisions[e.target.dataset.proposal] = e.target.value;
  drafts.set(selected, decisions);
});
byId("detail").addEventListener("input", (e) => {
  if (e.target.id === "reviewer") reviewer = e.target.value;
});
byId("detail").addEventListener("click", (e) => {
  if (e.target.id === "prepare") mutate("prepare", {});
});
byId("detail").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!reviewer.trim()) {
    notice("Enter your name before saving the review.", true);
    byId("reviewer").focus();
    return;
  }
  mutate("review", {
    reviewer: reviewer.trim(),
    choices: drafts.get(selected) || {},
  });
});
refresh();
