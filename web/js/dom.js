// Tiny DOM helpers. All text goes in through textContent, never innerHTML,
// because lead content is written by the public.

const PROPS = new Set(["value", "checked", "disabled", "selected", "hidden", "open", "indeterminate"]);

export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, val] of Object.entries(props || {})) {
    if (val === null || val === undefined || val === false) continue;
    if (key === "class") el.className = val;
    else if (key === "dataset") Object.assign(el.dataset, val);
    else if (key.startsWith("on") && typeof val === "function") el.addEventListener(key.slice(2), val);
    else if (PROPS.has(key)) el[key] = val;
    else el.setAttribute(key, val === true ? "" : String(val));
  }
  append(el, children);
  return el;
}

export function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return parent;
}

export function replace(parent, ...children) {
  parent.replaceChildren();
  return append(parent, children);
}

const SVG_NS = "http://www.w3.org/2000/svg";
const ICONS = {
  plus: "M8 3v10M3 8h10",
  close: "M4 4l8 8M12 4l-8 8",
  back: "M10 3L5 8l5 5",
  search: "M7 12A5 5 0 1 0 7 2a5 5 0 0 0 0 10zM11 11l3 3",
  refresh: "M13 8a5 5 0 1 1-1.5-3.5M13 2v3h-3",
  download: "M8 2v8M4.5 7L8 10.5 11.5 7M3 13h10",
  trash: "M3 4h10M6 4V2.5h4V4M4.5 4l.7 9.5h5.6l.7-9.5",
};

export function icon(name) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", ICONS[name]);
  svg.append(path);
  return svg;
}

let toastTimer = null;
const TOAST_MS = 3500;

export function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, TOAST_MS);
}

export async function withBusy(button, busyText, fn) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  try {
    return await fn();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}
