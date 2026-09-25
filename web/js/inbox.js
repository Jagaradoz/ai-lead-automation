// Inbox: the lead list on the left, the selected lead on the right.

import { leadsApi } from "./api.js";
import { h, icon, replace } from "./dom.js";
import { PRIORITY_LABELS, STATUS_LABELS, timeAgo } from "./format.js";
import { renderDetail, renderDetailEmpty } from "./lead-detail.js";

const PAGE_SIZE = 100;
const SEARCH_DELAY_MS = 250;

let filters = { priority: "", status: "", q: "", sort: "recent" };
let desk = null;
let listEl = null;
let footEl = null;
let detailEl = null;
let selectedId = null;
let searchTimer = null;

function priorityButtons() {
  const options = [["", "All"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]];
  return h(
    "div",
    { class: "segmented", role: "group", "aria-label": "Filter by priority" },
    options.map(([value, label]) =>
      h("button", {
        type: "button",
        "aria-pressed": String(filters.priority === value),
        onclick: () => setFilters({ ...filters, priority: value }),
      }, label),
    ),
  );
}

function renderTools() {
  const statusSelect = h(
    "select",
    { "aria-label": "Filter by status", onchange: (e) => setFilters({ ...filters, status: e.target.value }) },
    h("option", { value: "" }, "Any status"),
    Object.entries(STATUS_LABELS).map(([value, label]) =>
      h("option", { value, selected: filters.status === value }, label),
    ),
  );
  const sortSelect = h(
    "select",
    { "aria-label": "Sort", onchange: (e) => setFilters({ ...filters, sort: e.target.value }) },
    h("option", { value: "recent", selected: filters.sort === "recent" }, "Newest first"),
    h("option", { value: "score", selected: filters.sort === "score" }, "Highest score"),
  );
  const search = h("input", {
    type: "search",
    placeholder: "Search name, company or message",
    "aria-label": "Search leads",
    value: filters.q,
    oninput: (e) => {
      clearTimeout(searchTimer);
      const q = e.target.value;
      searchTimer = setTimeout(() => setFilters({ ...filters, q }), SEARCH_DELAY_MS);
    },
  });
  return h("div", { class: "list-tools" },
    search,
    priorityButtons(),
    h("div", { class: "list-tools-row" }, statusSelect, sortSelect),
  );
}

function leadRow(item) {
  const priority = item.priority || "disqualified";
  const statusText = item.status === "new" ? null : STATUS_LABELS[item.status];
  return h(
    "li",
    null,
    h("button", {
      type: "button",
      class: `lead-row p-${priority}`,
      "aria-current": String(item.id === selectedId),
      "aria-label": `${item.contact_name || "Unnamed lead"}, ${PRIORITY_LABELS[priority]} priority, score ${item.total_score}`,
      onclick: () => { location.hash = `#/lead/${item.id}`; },
    },
      h("span", { class: "lead-row-bar", "aria-hidden": "true" }),
      h("span", { class: "lead-row-name" }, item.contact_name || "Unnamed lead"),
      h("span", { class: "lead-row-score" }, item.total_score),
      h("span", { class: "lead-row-company" },
        item.company_name || "No company given",
        statusText ? h("span", { class: "lead-row-status" }, `, ${statusText.toLowerCase()}`) : null,
      ),
      h("span", { class: "lead-row-time" }, timeAgo(item.created_at)),
      h("span", { class: "lead-row-summary" }, item.summary || ""),
    ),
  );
}

function emptyList() {
  const filtered = filters.priority || filters.status || filters.q;
  if (filtered) {
    return h("div", { class: "empty" },
      h("h2", null, "No leads match these filters"),
      h("button", { type: "button", class: "btn", onclick: () => setFilters({ priority: "", status: "", q: "", sort: filters.sort }) }, "Clear filters"),
    );
  }
  return h("div", { class: "empty" },
    h("h2", null, "No leads yet"),
    h("p", null, "Paste an enquiry with New lead, or send leads from your forms to POST /api/leads/process."),
    h("button", { type: "button", class: "btn btn-primary", onclick: () => document.getElementById("open-new-lead").click() }, icon("plus"), "New lead"),
  );
}

async function loadList() {
  const params = { sort: filters.sort, limit: PAGE_SIZE };
  if (filters.priority) params.priority = filters.priority;
  if (filters.status) params.status = filters.status;
  if (filters.q) params.q = filters.q;

  try {
    const page = await leadsApi.list(params);
    replace(listEl, page.items.length ? h("ul", null, page.items.map(leadRow)) : emptyList());
    replace(footEl,
      h("span", { class: "num" }, page.total === 1 ? "1 lead" : `${page.total} leads`),
      h("a", { class: "btn btn-quiet btn-small", href: "/api/leads/export.csv", download: "leads.csv" }, icon("download"), "Export CSV"),
    );
  } catch (err) {
    replace(listEl, h("div", { class: "empty" }, h("h2", null, "Couldn't load leads"), h("p", null, err.message),
      h("button", { type: "button", class: "btn", onclick: loadList }, "Try again")));
  }
}

function setFilters(next) {
  filters = next;
  const tools = desk.querySelector(".list-tools");
  tools.replaceWith(renderTools());
  loadList();
}

async function loadDetail() {
  if (!selectedId) {
    renderDetailEmpty(detailEl);
    return;
  }
  await renderDetail(detailEl, selectedId, { onChange: loadList });
}

export function renderInbox(main, leadId) {
  selectedId = leadId ? Number(leadId) : null;
  if (!desk || !main.contains(desk)) {
    listEl = h("div", { class: "lead-list", "aria-live": "polite" });
    footEl = h("div", { class: "list-foot" });
    detailEl = h("section", { class: "detail-pane", "aria-label": "Lead detail" });
    desk = h("div", { class: "desk" },
      h("section", { class: "list-pane", "aria-label": "Leads" }, renderTools(), listEl, footEl),
      detailEl,
    );
    replace(main, desk);
  }
  desk.dataset.view = selectedId ? "detail" : "list";
  loadList();
  loadDetail();
}

export function refreshInbox() {
  if (desk && document.contains(desk)) loadList();
}
