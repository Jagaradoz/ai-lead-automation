// Dashboard: how many leads arrive, how good they are, and which channels close.

import { insightsApi } from "./api.js";
import { barList, columnChart, donut, pct, statTile } from "./charts.js";
import { h, icon, replace } from "./dom.js";
import { PRIORITY_COLORS, PRIORITY_LABELS, SOURCE_LABELS, STATUS_LABELS } from "./format.js";

const RANGES = [7, 14, 30];
const PIPELINE = ["new", "contacted", "qualified", "won", "lost", "spam"];
let days = 14;

function shortDate(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function sourceName(key) {
  const name = SOURCE_LABELS[key] || key;
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function latencyText(ms) {
  if (ms === null || ms === undefined) return "–";
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function card(title, sub, ...body) {
  return h("section", { class: "card chart-card" },
    h("header", { class: "chart-head" }, h("h2", { class: "section-title" }, title), sub ? h("p", { class: "muted" }, sub) : null),
    body,
  );
}

function rangePicker(onPick) {
  return h("div", { class: "segmented segmented-inline", role: "group", "aria-label": "Date range" },
    RANGES.map((d) => h("button", { type: "button", "aria-pressed": String(d === days), onclick: () => onPick(d) }, `${d} days`)),
  );
}

function kpis(stats) {
  const hot = stats.by_priority.high || 0;
  return h("div", { class: "stats-row" },
    statTile("Leads", String(stats.total), "all time"),
    statTile("High priority", String(hot), stats.total ? `${pct(hot / stats.total)} of leads` : null),
    statTile("Win rate", pct(stats.win_rate), "won ÷ (won + lost)"),
    statTile("Avg. analysis time", latencyText(stats.median_latency_ms), "median, per lead"),
    statTile("Needs review", String(stats.needs_review), "flagged before reply"),
  );
}

function volume(stats) {
  const inRange = stats.daily.reduce((s, d) => s + d.count, 0);
  const points = stats.daily.map((d) => ({ label: shortDate(d.date), short: shortDate(d.date), value: d.count }));
  return card("Leads per day", `${inRange} in the last ${days} days`,
    columnChart(points, { label: "Leads per day", format: (p) => `${p.label}: ${p.value} ${p.value === 1 ? "lead" : "leads"}` }));
}

function priorityMix(stats) {
  const segments = Object.keys(PRIORITY_LABELS).map((p) => ({
    label: PRIORITY_LABELS[p], value: stats.by_priority[p] || 0, color: PRIORITY_COLORS[p],
  }));
  return card("Priority mix", "How the scoring sorted every lead", donut(segments, { label: "Leads by priority", centerLabel: "leads" }));
}

function channels(stats) {
  const rows = stats.by_source.map((s) => ({
    label: sourceName(s.source),
    value: s.count,
    display: `${s.count} leads`,
    note: `Win rate ${pct(s.win_rate)} · avg. score ${s.avg_score}`,
  }));
  return card("Channels", "Volume per channel, with how often closed deals were won",
    rows.length ? barList(rows) : h("p", { class: "muted" }, "No leads yet."));
}

function pipeline(stats) {
  const rows = PIPELINE.map((s) => ({ label: STATUS_LABELS[s], value: stats.by_status[s] || 0 }));
  return card("Pipeline", "Where leads are in the sales process", barList(rows));
}

async function load(body) {
  replace(body, h("p", { class: "muted" }, "Loading…"));
  try {
    const stats = await insightsApi.stats(days);
    if (!stats.total) {
      replace(body, h("div", { class: "card empty" },
        h("h2", null, "No leads yet"),
        h("p", null, "Add a lead with New lead, or fill the inbox with demo data: python -m scripts.seed_demo_leads"),
      ));
      return;
    }
    replace(body, kpis(stats), h("div", { class: "grid-2" }, volume(stats), priorityMix(stats)),
      h("div", { class: "grid-2" }, channels(stats), pipeline(stats)));
  } catch (err) {
    replace(body, h("div", { class: "card empty" }, h("h2", null, "Couldn't load the dashboard"), h("p", null, err.message)));
  }
}

export function renderDashboard(main) {
  const body = h("div", { class: "page-body" });
  const head = h("header", { class: "page-head" },
    h("div", null, h("h1", null, "Dashboard"), h("p", { class: "muted" }, "Every lead from every channel, analyzed and prioritized.")),
    h("div", { class: "page-tools" },
      h("span", { class: "range-slot" }),
      h("a", { class: "btn btn-small", href: "/api/leads/export.csv", download: "leads.csv" }, icon("download"), "Export CSV"),
    ),
  );
  const renderRange = () => head.querySelector(".range-slot").replaceChildren(rangePicker((d) => { days = d; renderRange(); load(body); }));
  renderRange();
  replace(main, h("div", { class: "page" }, head, body));
  load(body);
}
