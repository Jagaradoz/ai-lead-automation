// Settings / Business profile: what you sell, who you sell to, and how leads are scored.

import { leadsApi, settingsApi } from "./api.js";
import { h, replace, toast, withBusy } from "./dom.js";
import { DIMENSION_LABELS, TIER_LABELS } from "./format.js";
import { cell, checkField, listField, numberField, rowsTable, textField } from "./form-controls.js";
import { adminTokenField, settingsShell } from "./settings-shell.js";

const PCT = { min: 0, max: 100 };

function group(title, intro, ...children) {
  return h("section", { class: "group" }, h("h2", null, title), intro ? h("p", null, intro) : null, children);
}

function grid(...fields) {
  return h("div", { class: "group-grid" }, fields.map((f) => f.el));
}

function weightsEditor(weights) {
  const fields = Object.entries(weights).map(([key, value]) => [key, numberField(DIMENSION_LABELS[key] || key, value, PCT)]);
  const sum = h("p", { class: "sum-line", role: "status" });
  const update = () => {
    const total = fields.reduce((acc, [, f]) => acc + (Number(f.read()) || 0), 0);
    sum.dataset.ok = String(total === 100);
    sum.textContent = total === 100 ? "Adds up to 100 points." : `Adds up to ${total}. It must be exactly 100 to save.`;
  };
  fields.forEach(([, f]) => f.control.addEventListener("input", update));
  update();
  return {
    el: h("div", null, h("div", { class: "weights" }, fields.map(([, f]) => f.el)), sum),
    read: () => Object.fromEntries(fields.map(([k, f]) => [k, f.read()])),
    valid: () => sum.dataset.ok === "true",
  };
}

function sharesEditor(shares, labels) {
  const fields = Object.entries(shares).map(([key, value]) => [key, numberField(labels[key] || key, value, PCT)]);
  return {
    el: h("div", { class: "group-grid" }, fields.map(([, f]) => f.el)),
    read: () => Object.fromEntries(fields.map(([k, f]) => [k, f.read()])),
  };
}

function buildEditor(profile, onSaved) {
  const base = profile.business.base_currency;
  const s = profile.scoring;

  const name = textField("Business name", profile.business.name, { maxlength: 120 });
  const description = textField("What you do", profile.business.description, {
    multiline: true, rows: 3, maxlength: 2000, hint: "The model reads this to understand which leads fit.",
  });
  const baseCurrency = textField("Base currency", base, { maxlength: 3, hint: "Budgets are converted to this before scoring." });

  const services = rowsTable([
    { key: "name", label: "Service", width: "32%", make: cell.text("Service name") },
    { key: "tier", label: "Tier", width: "20%", make: cell.select("Tier", [["core", TIER_LABELS.core], ["adjacent", TIER_LABELS.adjacent], ["out_of_scope", TIER_LABELS.out_of_scope]]) },
    { key: "keywords", label: "Words that signal it", make: cell.list("Keywords") },
  ], profile.services, { blank: { name: "", tier: "core", keywords: [] }, addLabel: "Add service", rowLabel: "service" });

  const industries = rowsTable([
    { key: "name", label: "Industry", width: "28%", make: cell.text("Industry") },
    { key: "target", label: "Target", width: "8%", make: cell.check("Target industry") },
    { key: "keywords", label: "Words that signal it", make: cell.list("Keywords") },
  ], profile.industries, { blank: { name: "", target: true, keywords: [] }, addLabel: "Add industry", rowLabel: "industry" });

  const sizes = listField("Target company sizes", profile.target_company_sizes, { rows: 1 });
  const titles = listField("Decision-maker titles", profile.decision_maker_titles, { hint: "A lead gets the decision-maker points when one of these appears." });

  const weights = weightsEditor(s.weights);
  const serviceShares = sharesEditor(s.service_fit, {
    core: "Core service (%)", adjacent: "Adjacent service (%)", uncatalogued: "Not in catalog (%)", out_of_scope: "Out of scope (%)",
  });
  const intentShares = sharesEditor(s.purchase_intent, { high: "High intent (%)", medium: "Medium intent (%)", low: "Low intent (%)" });
  const completeness = sharesEditor(s.data_completeness, { full: "Contact and company (%)", basic: "Contact only (%)" });

  const budgetTiers = rowsTable([
    { key: "min_amount", label: `At least (${base})`, make: cell.number("Minimum amount", { step: 1000 }) },
    { key: "share", label: "Points (%)", make: cell.number("Share of budget points", PCT) },
  ], s.budget_fit.tiers, { blank: { min_amount: 0, share: 50 }, addLabel: "Add tier", rowLabel: "tier" });
  const budgetUnspecified = numberField("No budget stated (%)", s.budget_fit.unspecified, PCT);

  const rates = rowsTable([
    { key: "code", label: "Currency", make: cell.text("Code, e.g. USD") },
    { key: "rate", label: "Worth this many units of the reference", make: cell.number("Rate", { step: 0.01 }) },
  ], Object.entries(profile.currency_rates).map(([code, rate]) => ({ code, rate })),
  { blank: { code: "", rate: 1 }, addLabel: "Add currency", rowLabel: "currency" });

  const buckets = rowsTable([
    { key: "max_days", label: "Within (days)", make: cell.number("Days", { min: 0 }) },
    { key: "share", label: "Points (%)", make: cell.number("Share of timeline points", PCT) },
  ], s.urgency.buckets, { blank: { max_days: 14, share: 100 }, addLabel: "Add bucket", rowLabel: "bucket" });
  const urgencyBeyond = numberField("Later than every bucket (%)", s.urgency.beyond, PCT);
  const urgencyUnspecified = numberField("No timeline stated (%)", s.urgency.unspecified, PCT);

  const t = profile.priority_thresholds;
  const high = numberField("High from", t.high, PCT);
  const medium = numberField("Medium from", t.medium, PCT);
  const low = numberField("Low from", t.low, { ...PCT, hint: "Below this, the lead is disqualified." });

  const r = profile.review;
  const lowConf = numberField("Review when confidence is below", r.low_confidence_below, { min: 0, max: 1, step: 0.05 });
  const largeDeal = numberField(`Review deals of at least (${base})`, r.large_budget_at_least, { min: 0, step: 10000 });
  const flagOut = checkField("Review out-of-scope requests", r.flag_out_of_scope);
  const flagSpam = checkField("Review suspected spam", r.flag_spam);
  const flagAmb = checkField("Review vague messages or leads without contact details", r.flag_ambiguous);
  const spam = listField("Spam phrases", profile.spam_phrases, { rows: 3, hint: "Messages containing any of these are treated as spam." });

  const error = h("p", { class: "form-error", role: "alert", hidden: true });
  const saveBtn = h("button", { type: "submit", class: "btn btn-primary" }, "Save changes");
  const resetBtn = h("button", { type: "button", class: "btn btn-quiet" }, "Restore defaults");

  const collect = () => ({
    version: profile.version,
    business: { name: name.read(), description: description.read(), base_currency: baseCurrency.read().toUpperCase() },
    currency_rates: Object.fromEntries(rates.read().filter((x) => x.code).map((x) => [x.code.toUpperCase(), x.rate])),
    services: services.read().filter((x) => x.name),
    industries: industries.read().filter((x) => x.name),
    target_company_sizes: sizes.read(),
    decision_maker_titles: titles.read(),
    spam_phrases: spam.read(),
    scoring: {
      weights: weights.read(),
      service_fit: serviceShares.read(),
      purchase_intent: intentShares.read(),
      urgency: { buckets: buckets.read(), beyond: urgencyBeyond.read(), unspecified: urgencyUnspecified.read() },
      budget_fit: { tiers: budgetTiers.read(), unspecified: budgetUnspecified.read() },
      data_completeness: completeness.read(),
    },
    priority_thresholds: { high: high.read(), medium: medium.read(), low: low.read() },
    review: {
      low_confidence_below: lowConf.read(),
      large_budget_at_least: largeDeal.read(),
      flag_out_of_scope: flagOut.read(),
      flag_spam: flagSpam.read(),
      flag_ambiguous: flagAmb.read(),
    },
  });

  const showError = (msg) => { error.textContent = msg; error.hidden = !msg; };

  const form = h("form", {
    novalidate: true,
    onsubmit: (e) => {
      e.preventDefault();
      if (!weights.valid()) { showError("Dimension weights must add up to exactly 100."); return; }
      withBusy(saveBtn, "Saving…", async () => {
        try {
          const saved = await settingsApi.saveProfile(collect());
          showError("");
          onSaved(saved, true);
        } catch (err) {
          showError(err.status === 401 ? "Enter the admin token above, then save again." : err.message);
        }
      });
    },
  },
    group("Your business", null, grid(name, baseCurrency), description.el),
    group("What you sell", "Leads are matched to these services. Core services earn full service points, adjacent ones partial, and out-of-scope ones none.", services.el),
    group("Who you sell to", "Leads from a target industry or company size earn the company-fit points.", industries.el, grid(sizes), titles.el),
    group("How much each part is worth", "Each part of the score is worth its weight in points. The percentages further down decide how much of that weight a lead earns.", weights.el),
    group("Service and intent", null, serviceShares.el, intentShares.el, completeness.el),
    group("Budget", `Amounts are compared in ${base}. A lead earns the points of the highest tier its budget reaches.`, budgetTiers.el, grid(budgetUnspecified), h("h3", { class: "field-label" }, `Exchange rates (value of 1 unit in the reference currency; ${base} should be 1)`), rates.el),
    group("Timeline", "A lead earns the points of the first bucket its timeline fits in.", buckets.el, grid(urgencyBeyond, urgencyUnspecified)),
    group("Priority and review", "Total score decides the priority. Review flags ask a person to check before anyone replies.", grid(high, medium, low), grid(lowConf, largeDeal), flagOut.el, flagSpam.el, flagAmb.el, spam.el),
    h("div", { class: "save-bar" }, error, resetBtn, saveBtn),
  );

  resetBtn.addEventListener("click", async () => {
    if (!confirm("Replace your profile with the shipped defaults?")) return;
    try {
      onSaved(await settingsApi.resetProfile(), false);
      toast("Defaults restored.");
    } catch (err) {
      showError(err.message);
    }
  });
  return form;
}

function afterSave(body) {
  return async (saved, offerRescore) => {
    if (!offerRescore) { renderInto(body, saved); return; }
    toast("Profile saved. New leads use these rules.");
    if (confirm("Re-score the leads already in your inbox with the new rules?")) {
      try {
        const res = await leadsApi.rescoreAll();
        toast(`Re-scored ${res.rescored} leads.`);
      } catch (err) {
        toast(err.message);
      }
    }
    renderInto(body, saved);
  };
}

function renderInto(body, profile) {
  const holder = body.querySelector("[data-profile-form]");
  replace(holder, buildEditor(profile, afterSave(body)));
}

export async function renderProfileSettings(main) {
  const body = settingsShell(main, "profile", "Business profile",
    "Describe what you sell and how you judge a lead. The model reads this before extracting facts, and the scoring rules use it to award points.");
  body.append(adminTokenField());
  const holder = h("div", { "data-profile-form": "" }, h("p", { class: "muted" }, "Loading profile…"));
  body.append(holder);
  try {
    renderInto(body, await settingsApi.profile());
  } catch (err) {
    replace(holder, h("p", { class: "form-error" }, err.message));
  }
}
