// Entry point: hash router, engine status chip, and the New lead sheet.

import { settingsApi } from "./api.js";
import { refreshInbox, renderInbox } from "./inbox.js";
import { initNewLead } from "./new-lead.js";
import { renderModelSettings } from "./settings-model.js";
import { renderProfileSettings } from "./settings-profile.js";

const main = document.getElementById("main");

async function refreshEngine() {
  const chip = document.getElementById("engine-chip");
  const label = document.getElementById("engine-label");
  try {
    const health = await settingsApi.health();
    const usingModel = health.ai_engine_mode === "model";
    chip.dataset.state = usingModel ? "model" : "rules";
    label.textContent = usingModel ? health.engine : "Rules only. Set up a model";
  } catch {
    chip.dataset.state = "";
    label.textContent = "Server unreachable";
  }
}

function setActiveNav(section) {
  document.querySelectorAll("[data-nav]").forEach((a) => {
    if (a.dataset.nav === section) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
}

function route() {
  const hash = location.hash || "#/inbox";
  const leadMatch = hash.match(/^#\/lead\/(\d+)$/);

  if (hash === "#/settings/model") {
    setActiveNav("settings");
    renderModelSettings(main);
  } else if (hash === "#/settings/profile") {
    setActiveNav("settings");
    renderProfileSettings(main);
  } else {
    setActiveNav("inbox");
    renderInbox(main, leadMatch ? leadMatch[1] : null);
  }
}

initNewLead({
  onCreated: (id) => {
    if (id) location.hash = `#/lead/${id}`;
    refreshInbox();
  },
});

window.addEventListener("hashchange", route);
document.addEventListener("engine-changed", refreshEngine);
route();
refreshEngine();
