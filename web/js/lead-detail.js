// Lead detail: why it scored the way it did, what they wrote, what was extracted, and actions.

import { leadsApi } from "./api.js";
import { pointsBar, scoreGauge } from "./charts.js";
import { h, icon, replace, toast, withBusy } from "./dom.js";
import {
  DIMENSION_LABELS, PRIORITY_LABELS, SOURCE_LABELS, STATUS_LABELS, TIER_LABELS,
  humanize, languageName, money, timeAgo,
} from "./format.js";

export function renderDetailEmpty(pane) {
  replace(pane, h("div", { class: "empty" },
    h("h2", null, "Select a lead"),
    h("p", null, "Pick a lead on the left to see why it scored the way it did and what to do next."),
  ));
}

function tally(score) {
  const priority = score.priority || "disqualified";
  const rows = (score.explanations || []).map((e) =>
    h("div", { class: "tally-row", dataset: { zero: String(e.points_awarded === 0) } },
      h("span", { class: "tally-name" }, DIMENSION_LABELS[e.dimension] || humanize(e.dimension)),
      h("span", { class: "tally-pts" }, h("b", null, e.points_awarded), h("span", null, ` / ${e.max_possible}`)),
      h("span", { class: "tally-reason" }, e.reason),
      pointsBar(e.points_awarded, e.max_possible),
    ),
  );
  return h("section", { class: `card p-${priority}`, "aria-labelledby": "tally-title" },
    h("h2", { class: "section-title", id: "tally-title" }, "Why it scored this way"),
    h("div", { class: "score-layout" },
      h("div", { class: "score-summary" },
        scoreGauge(score.total_score, PRIORITY_LABELS[priority]),
        h("span", { class: "priority-pill" }, `${PRIORITY_LABELS[priority]} priority`),
      ),
      h("div", { class: "tally" }, rows),
    ),
  );
}

function reviewNotice(score) {
  if (!score.requires_human_review) return null;
  const danger = score.priority === "disqualified";
  return h("div", { class: `notice${danger ? " notice-danger" : ""}`, role: "note" },
    h("strong", null, "Check before replying"),
    h("ul", null, (score.human_review_reasons || []).map((r) => h("li", null, r))),
  );
}

function respondText(minutes) {
  if (minutes === null || minutes === undefined) return "No reply needed";
  if (minutes < 60 * 24) return `Reply within ${Math.round(minutes / 60)} h`;
  return `Reply within ${Math.round(minutes / (60 * 24))} days`;
}

function followupCard(id) {
  const body = h("div", { class: "followup-body" }, h("p", { class: "muted" }, "Preparing next step…"));
  leadsApi.followup(id).then(({ route, reply }) => {
    const routeRow = h("div", { class: "route" },
      h("div", null, h("span", { class: "route-label" }, "Owner"), h("b", null, route.owner)),
      h("div", null, h("span", { class: "route-label" }, "Next step"), h("b", null, route.action)),
      h("div", null, h("span", { class: "route-label" }, "Target"), h("b", null, respondText(route.respond_within_min))),
    );
    if (!reply) {
      replace(body, routeRow, h("p", { class: "muted" }, "No automatic reply for disqualified leads."));
      return;
    }
    const area = h("textarea", { rows: 9, "aria-label": "Reply draft", lang: reply.language });
    area.value = reply.body;
    const copy = h("button", { type: "button", class: "btn btn-small btn-primary" }, "Copy reply");
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(area.value);
        toast("Reply copied.");
      } catch {
        area.select();
        toast("Press Ctrl+C to copy.");
      }
    });
    replace(body, routeRow,
      h("div", { class: "reply-head" }, h("span", { class: "route-label" }, `Draft reply · ${reply.subject}`), copy),
      area,
    );
  }).catch((err) => replace(body, h("p", { class: "muted" }, `Couldn't prepare a next step: ${err.message}`)));
  return h("section", { class: "card followup" }, h("h2", { class: "section-title" }, "Next step"), body);
}

function engineNote(meta) {
  if (!meta) return null;
  if (meta.engine === "model") {
    const secs = meta.latency_ms ? ` in ${(meta.latency_ms / 1000).toFixed(1)} s` : "";
    return h("p", { class: "engine-note" }, `Analyzed by ${meta.model} (${meta.provider})${secs}.`);
  }
  const why = meta.fallback_reason ? ` ${meta.fallback_reason}` : "";
  return h("p", { class: "engine-note" }, `Analyzed by the built-in rules, not a model.${why} `,
    h("a", { href: "#/settings/model" }, "Model settings"));
}

function contactLine(contact) {
  const parts = [];
  if (contact.email) parts.push(h("a", { href: `mailto:${contact.email}` }, contact.email));
  if (contact.phone) parts.push(h("a", { href: `tel:${String(contact.phone).replace(/[^\d+]/g, "")}` }, contact.phone));
  if (!parts.length) return h("p", { class: "muted" }, "No email or phone number given.");
  return h("p", null, parts.flatMap((p, i) => (i ? [", ", p] : [p])));
}

function facts(analysis) {
  const match = analysis.service_match || {};
  const budget = analysis.budget || {};
  const rows = [
    ["Asked for", analysis.service_requested || "Not clear from the message"],
    ["Catalog match", match.offering ? `${match.offering} (${TIER_LABELS[match.tier] || match.tier})` : TIER_LABELS.none],
    ["Industry", analysis.industry ? humanize(analysis.industry) : "Unknown"],
    ["Budget", budget.stated ? money(budget.amount, budget.currency) : "Not stated"],
    ["Timeline", analysis.timeline_days != null ? `Within ${analysis.timeline_days} ${analysis.timeline_days === 1 ? "day" : "days"}` : "Not stated"],
    ["Their role", analysis.contact_role ? humanize(analysis.contact_role) : "Not stated"],
    ["Language", languageName(analysis.language)],
    ["Still missing", (analysis.missing_information || []).map(humanize).join(", ") || "Nothing obvious"],
    ["Confidence", analysis.confidence_score != null ? `${Math.round(analysis.confidence_score * 100)}%` : "Unknown"],
  ];
  return h("dl", { class: "facts" }, rows.flatMap(([k, v]) => [h("dt", null, k), h("dd", null, v)]));
}

function notesForm(record, onSaved) {
  const area = h("textarea", { rows: 3, maxlength: 5000, "aria-label": "Notes", placeholder: "Call notes, next step, who owns it" });
  area.value = record.notes || "";
  const save = h("button", { type: "submit", class: "btn btn-small" }, "Save notes");
  return h("form", {
    class: "card notes-form",
    onsubmit: async (e) => {
      e.preventDefault();
      await withBusy(save, "Saving…", async () => {
        try {
          await leadsApi.patch(record.id, { notes: area.value });
          toast("Notes saved.");
          onSaved();
        } catch (err) {
          toast(err.message);
        }
      });
    },
  }, h("h2", { class: "section-title" }, "Notes"), area, save);
}

function actions(record, rerender, onChange) {
  const status = h("select", {
    id: "status-select",
    onchange: async (e) => {
      try {
        await leadsApi.patch(record.id, { status: e.target.value });
        toast(`Marked as ${STATUS_LABELS[e.target.value].toLowerCase()}.`);
        onChange();
      } catch (err) {
        toast(err.message);
      }
    },
  }, Object.entries(STATUS_LABELS).map(([v, label]) => h("option", { value: v, selected: record.status === v }, label)));

  const run = (label, busy, fn, done) => {
    const btn = h("button", { type: "button", class: "btn btn-small" }, label);
    btn.addEventListener("click", () => withBusy(btn, busy, async () => {
      try {
        await fn();
        toast(done);
        rerender();
        onChange();
      } catch (err) {
        toast(err.message);
      }
    }));
    return btn;
  };

  const del = h("button", { type: "button", class: "btn btn-small btn-quiet btn-danger" }, icon("trash"), "Delete");
  del.addEventListener("click", async () => {
    if (!confirm("Delete this lead? This can't be undone.")) return;
    try {
      await leadsApi.remove(record.id);
      toast("Lead deleted.");
      location.hash = "#/inbox";
      onChange();
    } catch (err) {
      toast(err.message);
    }
  });

  return h("div", { class: "detail-actions" },
    h("label", { class: "visually-hidden", for: "status-select" }, "Status"),
    status,
    run("Re-score", "Scoring…", () => leadsApi.rescore(record.id), "Re-scored with your current rules."),
    run("Analyze again", "Analyzing…", () => leadsApi.reanalyze(record.id), "Analyzed again."),
    del,
  );
}

export async function renderDetail(pane, id, { onChange }) {
  let record;
  try {
    record = await leadsApi.get(id);
  } catch (err) {
    replace(pane, h("div", { class: "empty" }, h("h2", null, "Couldn't open this lead"), h("p", null, err.message),
      h("a", { class: "btn", href: "#/inbox" }, "Back to inbox")));
    return;
  }

  const { lead, analysis, score, meta } = record;
  const contact = lead.contact || {};
  const company = lead.company || {};
  const subParts = [
    company.name,
    `via ${SOURCE_LABELS[lead.source] || lead.source}`,
    timeAgo(record.created_at),
  ].filter(Boolean);
  const rerender = () => renderDetail(pane, id, { onChange });

  replace(pane, h("article", { class: "detail" },
    h("a", { class: "btn btn-quiet btn-small back-link", href: "#/inbox" }, icon("back"), "All leads"),
    h("header", { class: "detail-head" },
      h("h1", { class: "detail-title" }, contact.name || "Unnamed lead",
        meta && meta.demo ? h("span", { class: "tag", title: "Generated demo data" }, "Demo") : null),
      h("p", { class: "detail-sub" }, subParts.join(", ")),
      h("p", { class: "detail-summary" }, analysis.summary || ""),
      actions(record, rerender, onChange),
    ),
    reviewNotice(score),
    followupCard(id),
    tally(score),
    h("section", { class: "card" },
      h("h2", { class: "section-title" }, "What they wrote"),
      h("div", { class: "message", lang: analysis.language || undefined }, lead.message || ""),
      contactLine(contact),
    ),
    h("section", { class: "card" }, h("h2", { class: "section-title" }, "What was extracted"), facts(analysis), engineNote(meta)),
    notesForm(record, onChange),
  ));
  pane.scrollTop = 0;
}
