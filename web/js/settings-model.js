// Settings / Model: choose the upstream model that reads leads.

import { settingsApi } from "./api.js";
import { h, replace, toast, withBusy } from "./dom.js";
import { adminTokenField, settingsShell } from "./settings-shell.js";

let providers = [];

function field(label, control, hint) {
  return h("label", { class: "field" },
    h("span", { class: "field-label" }, label),
    control,
    hint ? h("span", { class: "field-hint" }, hint) : null,
  );
}

function keyPlaceholder(current) {
  if (!current.has_api_key) return "Paste your API key";
  const hint = current.api_key_hint || "";
  return hint.startsWith("…") ? `Saved key ending in ${hint.slice(1)}. Leave blank to keep it.` : "A key is saved. Leave blank to keep it.";
}

function formValues(form) {
  const v = (name) => form.elements[name].value.trim();
  const body = {
    provider: v("provider"),
    base_url: v("base_url"),
    model: v("model"),
    timeout_s: Number(v("timeout_s")),
    on_failure: form.elements.on_failure.value,
    extra_instructions: form.elements.extra_instructions.value,
  };
  if (form.dataset.removeKey === "true") body.api_key = "";
  else if (v("api_key")) body.api_key = v("api_key");
  return body;
}

function buildForm(current) {
  const providerSelect = h("select", { name: "provider" },
    providers.map((p) => h("option", { value: p.id, selected: p.id === current.provider }, p.label)));
  const baseUrl = h("input", { name: "base_url", value: current.base_url, placeholder: "https://…/v1", inputmode: "url" });
  const modelList = h("datalist", { id: "model-options" });
  const model = h("input", { name: "model", value: current.model, list: "model-options", autocomplete: "off" });
  const apiKey = h("input", { name: "api_key", type: "password", autocomplete: "off", placeholder: keyPlaceholder(current) });
  const keyHint = h("span", { class: "field-hint" });
  const timeout = h("input", { name: "timeout_s", type: "number", min: 5, max: 300, step: 5, value: current.timeout_s });
  const extra = h("textarea", { name: "extra_instructions", rows: 3, maxlength: 4000, placeholder: "Optional. For example: Leads from Singapore quote prices in SGD." });
  extra.value = current.extra_instructions || "";
  const onFailure = h("div", { class: "inline-actions", role: "radiogroup", "aria-label": "When the model fails" },
    ["fallback", "error"].map((value) => h("label", { class: "inline-actions" },
      h("input", { type: "radio", name: "on_failure", value, checked: current.on_failure === value }),
      value === "fallback" ? "Use the built-in rules instead" : "Show an error and don't save the lead",
    )));

  const result = h("p", { class: "result-line", role: "status" });
  const loadModels = h("button", { type: "button", class: "btn btn-small" }, "Load models");
  const removeKey = h("button", { type: "button", class: "btn btn-small btn-quiet", hidden: !current.has_api_key }, "Remove saved key");
  const testBtn = h("button", { type: "button", class: "btn" }, "Test connection");
  const saveBtn = h("button", { type: "submit", class: "btn btn-primary" }, "Save");

  const modelGroup = h("div", { class: "group" });
  const form = h("form", { class: "settings-form", novalidate: true }, modelGroup);

  const syncVisibility = () => {
    const preset = providers.find((p) => p.id === providerSelect.value) || providers[0];
    const none = preset.kind === "none";
    modelGroup.querySelectorAll("[data-needs-model]").forEach((el) => { el.hidden = none; });
    keyHint.textContent = preset.key_required ? "Required for this provider." : "Not needed for local servers unless you set one.";
  };

  providerSelect.addEventListener("change", () => {
    const preset = providers.find((p) => p.id === providerSelect.value);
    baseUrl.value = preset?.base_url || "";
    model.value = preset?.model_hint || "";
    apiKey.value = "";
    replace(modelList);
    syncVisibility();
  });

  removeKey.addEventListener("click", () => {
    form.dataset.removeKey = "true";
    apiKey.placeholder = "Key will be removed when you save";
    removeKey.hidden = true;
  });

  loadModels.addEventListener("click", () => withBusy(loadModels, "Loading…", async () => {
    try {
      const res = await settingsApi.listModels(formValues(form));
      if (res.error) { result.className = "result-line bad"; result.textContent = res.error; return; }
      replace(modelList, res.models.map((m) => h("option", { value: m })));
      result.className = "result-line ok";
      result.textContent = `${res.models.length} models available. Start typing in Model to pick one.`;
    } catch (err) {
      result.className = "result-line bad";
      result.textContent = err.message;
    }
  }));

  testBtn.addEventListener("click", () => withBusy(testBtn, "Testing…", async () => {
    result.className = "result-line";
    result.textContent = "Sending a sample lead to the model…";
    try {
      const res = await settingsApi.testModel(formValues(form));
      if (res.ok) {
        result.className = "result-line ok";
        result.textContent = `Works. ${res.model} answered in ${(res.latency_ms / 1000).toFixed(1)} s and read the sample as ${res.sample.intent} intent, ${res.sample.industry || "unknown"} industry.`;
      } else {
        result.className = "result-line bad";
        result.textContent = res.error;
      }
    } catch (err) {
      result.className = "result-line bad";
      result.textContent = err.message;
    }
  }));

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    withBusy(saveBtn, "Saving…", async () => {
      try {
        const saved = await settingsApi.saveModel(formValues(form));
        toast(saved.is_configured ? `Saved. New leads use ${saved.model}.` : "Saved. New leads use the built-in rules.");
        document.dispatchEvent(new CustomEvent("engine-changed"));
        renderModelSettings(document.getElementById("main"));
      } catch (err) {
        result.className = "result-line bad";
        result.textContent = err.status === 401 ? "Enter the admin token above, then save again." : err.message;
      }
    });
  });

  replace(modelGroup,
    h("h2", null, "Provider"),
    h("p", null, "Any server that speaks the OpenAI chat completions API works, including local ones like Ollama and LM Studio. Anthropic is supported directly."),
    field("Provider", providerSelect),
    h("div", { class: "group-grid", "data-needs-model": "" },
      field("Base URL", baseUrl),
      h("div", { class: "field" },
        h("label", { class: "field-label", for: "model-input" }, "Model"),
        Object.assign(model, { id: "model-input" }),
        h("div", { class: "inline-actions" }, loadModels),
        modelList,
      ),
    ),
    h("div", { class: "field", "data-needs-model": "" },
      h("label", { class: "field-label", for: "api-key-input" }, "API key"),
      Object.assign(apiKey, { id: "api-key-input" }),
      keyHint,
      h("span", { class: "field-hint" }, "Stored on this server in data/settings.json. It is never sent back to the browser."),
      h("div", { class: "inline-actions" }, removeKey),
    ),
    h("div", { class: "group-grid", "data-needs-model": "" }, field("Timeout (seconds)", timeout)),
    h("fieldset", { class: "field", "data-needs-model": "" },
      h("legend", { class: "field-label" }, "When the model fails"),
      onFailure,
    ),
    h("div", { "data-needs-model": "" }, field("Extra instructions for the model", extra,
      "Added to the prompt after your business profile.")),
    result,
    h("div", { class: "inline-actions" }, testBtn, saveBtn),
  );
  syncVisibility();
  return form;
}

export async function renderModelSettings(main) {
  const body = settingsShell(main, "model",
    "Model",
    "Pick the model that reads each lead and extracts the facts. Scoring always uses your own rules, so the same facts give the same score.");
  try {
    const [list, current] = await Promise.all([settingsApi.providers(), settingsApi.model()]);
    providers = list;
    body.append(adminTokenField(), buildForm(current));
  } catch (err) {
    body.append(h("p", { class: "form-error" }, err.message));
  }
}
