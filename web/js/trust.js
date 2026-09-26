// Model page: evidence that the scoring can be trusted.
// 1) the message-scoring benchmark on hand-labeled enquiries,
// 2) a conversion model trained and tested on a real public lead dataset.

import { insightsApi } from "./api.js";
import { barList, confusionMatrix, pct, statTile, unitLineChart } from "./charts.js";
import { h, replace } from "./dom.js";

const SERIES_COLORS = { logistic_regression: "#3b82c4", gradient_boosting: "#c99400" };

function card(title, sub, ...body) {
  return h("section", { class: "card chart-card" },
    h("header", { class: "chart-head" }, h("h2", { class: "section-title" }, title), sub ? h("p", { class: "muted" }, sub) : null),
    body,
  );
}

function benchmark(b) {
  if (!b) return null;
  return card("Message scoring: hand-labeled test set",
    `The live pipeline (extraction + scoring) run against ${b.total} enquiries with known correct answers.`,
    h("div", { class: "stats-row" },
      statTile("Extraction correct", `${Math.round(b.extraction_accuracy)}%`, "intent, language, budget"),
      statTile("Priority correct", `${Math.round(b.scoring_accuracy)}%`, "score range and priority"),
      statTile("Safety flags correct", `${Math.round(b.safety_accuracy)}%`, "spam, out-of-scope, large deals"),
    ),
    h("p", { class: "fine-print" }, "A small regression suite: it proves known cases stay correct, not accuracy on every possible message."),
  );
}

function headline(report, best) {
  const base = report.dataset.conversion_rate;
  const top20 = report.lift.find((l) => l.top_share === 0.2);
  const baseline = report.models.find((m) => m.key === "baseline");
  return h("div", { class: "stats-row" },
    statTile("Ranking quality (AUC)", best.roc_auc.toFixed(2), "0.5 = coin flip, 1.0 = perfect"),
    statTile("Accuracy", pct(best.accuracy, 1), `vs ${pct(baseline.accuracy, 1)} by always guessing "no"`),
    top20 ? statTile("Top 20% of leads convert", pct(top20.conversion_rate), `vs ${pct(base)} on average`) : null,
    statTile("Tested on", report.dataset.test_rows.toLocaleString(), "real leads the model never saw"),
  );
}

function comparison(report) {
  const cols = ["Model", "AUC", "Accuracy", "Precision", "Recall", "F1"];
  return card("Model comparison", "Same held-out test leads for every model. Higher is better.",
    h("div", { class: "table-wrap" }, h("table", { class: "data-table" },
      h("thead", null, h("tr", null, cols.map((c) => h("th", { scope: "col" }, c)))),
      h("tbody", null, report.models.map((m) => h("tr", { class: m.key === report.best_model ? "is-best" : null },
        h("th", { scope: "row" }, m.label, m.key === report.best_model ? h("span", { class: "tag" }, "best") : null),
        h("td", { class: "num" }, m.roc_auc.toFixed(3)),
        h("td", { class: "num" }, pct(m.accuracy, 1)),
        h("td", { class: "num" }, pct(m.precision, 1)),
        h("td", { class: "num" }, pct(m.recall, 1)),
        h("td", { class: "num" }, pct(m.f1, 1)),
      ))),
    )),
  );
}

function roc(report) {
  const series = Object.entries(report.roc).map(([key, points]) => ({
    name: report.models.find((m) => m.key === key)?.label || key,
    color: SERIES_COLORS[key] || "#7a715d",
    points: points.map((p) => ({ x: p.fpr, y: p.tpr })),
  }));
  return card("ROC curve", "Further above the dashed diagonal = better at ranking buyers above non-buyers.",
    unitLineChart(series, { label: "ROC curve", xLabel: "False alarm rate", yLabel: "Buyers caught" }));
}

function liftCard(report) {
  const rows = report.lift.map((l) => ({
    label: `Call the top ${pct(l.top_share)} of leads`,
    value: l.conversions_captured,
    display: `${pct(l.conversions_captured)} of buyers`,
    note: `${pct(l.conversion_rate)} of these leads converted`,
  }));
  return card("What it means for a sales team", "Work leads in score order and most buyers come early.", barList(rows, { max: 1 }));
}

function confusion(report, best) {
  return card("Where it's right and wrong", `${best.label} at a ${report.threshold} cut-off, on test leads.`, confusionMatrix(best.confusion));
}

function importance(report) {
  const rows = report.feature_importance.map((f) => ({
    label: f.feature,
    value: Math.max(0, f.importance),
    display: f.importance.toFixed(3),
    title: `${f.feature}: AUC drops by ${f.importance.toFixed(3)} when this signal is scrambled`,
  }));
  return card("What drives conversion", "How much ranking quality drops when each signal is scrambled.", barList(rows));
}

function calibrationCard(report) {
  const points = report.calibration.map((b) => ({
    x: b.predicted, y: b.actual,
    title: `Predicted ${pct(b.predicted)}, actually ${pct(b.actual)} (${b.count} leads)`,
  }));
  return card("Are the probabilities honest?", "Dots near the diagonal: a lead given 70% converts about 70% of the time.",
    unitLineChart([{ name: "Gradient boosting", color: SERIES_COLORS.gradient_boosting, points }],
      { label: "Calibration", xLabel: "Predicted conversion", yLabel: "Actual conversion", markers: true }));
}

function bySource(report) {
  const rows = report.conversion_by_source.map((s) => ({
    label: s.value, value: s.conversion_rate, display: pct(s.conversion_rate), note: `${s.leads.toLocaleString()} leads`,
  }));
  return card("Conversion by lead source", "Real outcomes in the dataset.", barList(rows, { max: 1 }));
}

function caveats(report) {
  return h("section", { class: "card notes-card" },
    h("h2", { class: "section-title" }, "About this evaluation"),
    h("ul", { class: "plain-list" },
      h("li", null, `Dataset: ${report.dataset.name}, ${report.dataset.rows.toLocaleString()} leads with a real converted / not converted outcome (${pct(report.dataset.conversion_rate, 1)} converted).`),
      h("li", null, `Signals used: ${report.dataset.features.join(", ")}. ${report.dataset.train_rows.toLocaleString()} leads for training, ${report.dataset.test_rows.toLocaleString()} held out for testing.`),
      h("li", null, "It proves the approach on real data from one business. For your business, retrain on your own won/lost history; the inbox statuses are that history."),
      h("li", null, `Generated ${new Date(report.generated_at).toLocaleString()}. Re-run with: python -m scripts.train_conversion_model`),
    ),
  );
}

export async function renderTrust(main) {
  const body = h("div", { class: "page-body" }, h("p", { class: "muted" }, "Loading…"));
  replace(main, h("div", { class: "page" },
    h("header", { class: "page-head" }, h("div", null,
      h("h1", null, "Can you trust the scoring?"),
      h("p", { class: "muted" }, "Tested on labeled enquiries and on thousands of real leads with known outcomes."),
    )),
    body,
  ));
  try {
    const report = await insightsApi.modelReport();
    const best = report.models.find((m) => m.key === report.best_model);
    replace(body,
      benchmark(report.message_benchmark),
      h("h2", { class: "page-section-title" }, "Conversion model on real lead data"),
      headline(report, best),
      h("div", { class: "grid-2" }, liftCard(report), confusion(report, best)),
      h("div", { class: "grid-2" }, roc(report), calibrationCard(report)),
      h("div", { class: "grid-2" }, importance(report), bySource(report)),
      comparison(report),
      caveats(report),
    );
  } catch (err) {
    replace(body, h("div", { class: "card empty" }, h("h2", null, "No model report"), h("p", null, err.message)));
  }
}
