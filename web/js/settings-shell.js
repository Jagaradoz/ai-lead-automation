// Shared layout for settings pages, plus the admin token prompt.

import { getAdminToken, setAdminToken, settingsApi } from "./api.js";
import { h, replace, toast } from "./dom.js";

const PAGES = [
  ["model", "#/settings/model", "Model"],
  ["profile", "#/settings/profile", "Business profile"],
];

export function settingsShell(main, active, title, intro) {
  const body = h("div", { class: "settings-body" },
    h("header", null, h("h1", null, title), h("p", null, intro)),
  );
  replace(main, h("div", { class: "settings" },
    h("nav", { class: "settings-nav", "aria-label": "Settings" },
      PAGES.map(([id, href, label]) => h("a", { href, "aria-current": id === active ? "page" : null }, label)),
    ),
    body,
  ));
  return body;
}

/** Shown only when the server has ADMIN_TOKEN set. */
export function adminTokenField() {
  const wrap = h("div", { class: "group", hidden: true });
  settingsApi.health().then((health) => {
    if (!health.settings_locked) return;
    const input = h("input", { type: "password", autocomplete: "off", value: getAdminToken(), "aria-label": "Admin token" });
    const save = h("button", { type: "button", class: "btn btn-small" }, "Use token");
    save.addEventListener("click", () => {
      setAdminToken(input.value.trim());
      toast("Token set for this browser tab.");
    });
    replace(wrap,
      h("h2", null, "Admin token"),
      h("p", null, "This server requires a token to change settings. It is kept only for this browser tab."),
      h("div", { class: "inline-actions" }, input, save),
    );
    wrap.hidden = false;
  }).catch(() => { /* health unavailable: saving will report the problem */ });
  return wrap;
}
