// New lead sheet: paste an enquiry (or pick a sample), analyze it, and open the result.

import { leadsApi } from "./api.js";
import { h, toast, withBusy } from "./dom.js";

let samples = [];
let samplesLoaded = false;

const $ = (id) => document.getElementById(id);

function showError(message) {
  const el = $("new-lead-error");
  el.textContent = message;
  el.hidden = !message;
}

async function loadSamples() {
  if (samplesLoaded) return;
  try {
    samples = await leadsApi.samples();
    samplesLoaded = true;
    const select = $("sample-select");
    samples.forEach((s, i) => {
      const who = s.company?.name || s.contact?.name || `Sample ${i + 1}`;
      const preview = (s.message || "").slice(0, 48).trim();
      select.append(h("option", { value: String(i) }, `${who}: ${preview}…`));
    });
  } catch {
    // Samples are a convenience; the form works without them.
  }
}

function fillFromSample(index) {
  const s = samples[Number(index)];
  if (!s) return;
  $("lead-message").value = s.message || "";
  $("lead-name").value = s.contact?.name || "";
  $("lead-company").value = s.company?.name || "";
  $("lead-email").value = s.contact?.email || "";
  $("lead-phone").value = s.contact?.phone || "";
  $("lead-source").value = ["website", "line", "facebook", "email"].includes(s.source) ? s.source : "api";
  $("lead-size").value = s.company?.size || "";
}

function payloadFromForm() {
  const value = (id) => $(id).value.trim();
  return {
    lead_id: `lead_manual_${Date.now()}`,
    source: value("lead-source"),
    contact: {
      name: value("lead-name"),
      email: value("lead-email") || null,
      phone: value("lead-phone") || null,
    },
    company: {
      name: value("lead-company") || null,
      website: null,
      size: value("lead-size") || null,
    },
    message: value("lead-message"),
    received_at: new Date().toISOString(),
    metadata: { entered_by: "new-lead-form" },
  };
}

function validate(payload) {
  if (!payload.message) return "Paste the customer's message first.";
  if (!payload.contact.name) return "Add the contact's name.";
  const email = payload.contact.email;
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "That email address doesn't look right.";
  return "";
}

export function openNewLead() {
  const sheet = $("new-lead-sheet");
  showError("");
  sheet.showModal();
  loadSamples();
  $("lead-message").focus();
}

export function initNewLead({ onCreated }) {
  const sheet = $("new-lead-sheet");
  const form = $("new-lead-form");
  const button = $("analyze-btn");

  $("open-new-lead").addEventListener("click", openNewLead);
  sheet.querySelectorAll("[data-close]").forEach((el) => el.addEventListener("click", () => sheet.close()));
  sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.close(); });
  $("sample-select").addEventListener("change", (e) => fillFromSample(e.target.value));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = payloadFromForm();
    const problem = validate(payload);
    showError(problem);
    if (problem) return;

    await withBusy(button, "Analyzing…", async () => {
      try {
        // Sent in canonical shape so channel, size and received time are kept as entered.
        const result = await leadsApi.process(payload);
        form.reset();
        sheet.close();
        const engine = result.meta?.engine === "model" ? result.meta.model : "built-in rules";
        toast(`Scored ${result.score.total_score} with ${engine}.`);
        onCreated(result.id);
      } catch (err) {
        showError(err.message);
      }
    });
  });
}
