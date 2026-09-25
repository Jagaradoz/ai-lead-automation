// Form controls that know how to read their own value back.
// Each returns { el, read } so a page can rebuild its data from the DOM on save.

import { h, icon } from "./dom.js";
import { splitList } from "./format.js";

let uid = 0;
const nextId = () => `f${++uid}`;

function labelled(label, control, hint) {
  const id = control.id || (control.id = nextId());
  return h("div", { class: "field" },
    h("label", { class: "field-label", for: id }, label),
    control,
    hint ? h("span", { class: "field-hint" }, hint) : null,
  );
}

export function textField(label, value, { hint, maxlength, multiline, rows = 3 } = {}) {
  const control = multiline
    ? h("textarea", { rows, maxlength })
    : h("input", { value: value ?? "", maxlength });
  if (multiline) control.value = value ?? "";
  return { el: labelled(label, control, hint), read: () => control.value.trim(), control };
}

export function numberField(label, value, { hint, min, max, step = 1 } = {}) {
  const control = h("input", { type: "number", value: value ?? 0, min, max, step, inputmode: "decimal" });
  return { el: labelled(label, control, hint), read: () => Number(control.value), control };
}

export function listField(label, items, { hint, rows = 3 } = {}) {
  const control = h("textarea", { rows });
  control.value = (items || []).join(", ");
  return { el: labelled(label, control, hint || "Separate with commas or new lines."), read: () => splitList(control.value) };
}

export function checkField(label, checked) {
  const control = h("input", { type: "checkbox", checked: Boolean(checked) });
  return { el: h("label", { class: "inline-actions" }, control, label), read: () => control.checked };
}

/**
 * Editable table. `columns` is [{ label, make(value) -> { el, read } }].
 * Rows are objects; `blank` is used for "Add row".
 */
export function rowsTable(columns, rows, { blank, addLabel, rowLabel = "row" }) {
  const tbody = h("tbody");
  const readers = new Map();

  const addRow = (row) => {
    const cells = columns.map((col) => ({ key: col.key, ...col.make(row[col.key]) }));
    const remove = h("button", { type: "button", class: "btn btn-quiet btn-icon", "aria-label": `Remove ${rowLabel}` }, icon("close"));
    const tr = h("tr", null, cells.map((c) => h("td", null, c.el)), h("td", null, remove));
    remove.addEventListener("click", () => { readers.delete(tr); tr.remove(); });
    readers.set(tr, () => Object.fromEntries(cells.map((c) => [c.key, c.read()])));
    tbody.append(tr);
  };
  rows.forEach(addRow);

  const add = h("button", { type: "button", class: "btn btn-small" }, icon("plus"), addLabel);
  add.addEventListener("click", () => addRow({ ...blank }));

  const el = h("div", { class: "field" },
    h("table", { class: "edit-table" },
      h("thead", null, h("tr", null, columns.map((c) => {
        const th = h("th", { scope: "col" }, c.label);
        if (c.width) th.style.width = c.width;
        return th;
      }), h("th", null, h("span", { class: "visually-hidden" }, "Actions")))),
      tbody,
    ),
    h("div", { class: "inline-actions" }, add),
  );
  return { el, read: () => [...tbody.children].map((tr) => readers.get(tr)()).filter(Boolean) };
}

// Cell editors for rowsTable columns.
export const cell = {
  text: (placeholder, ariaLabel) => (value) => {
    const input = h("input", { value: value ?? "", placeholder, "aria-label": ariaLabel || placeholder });
    return { el: input, read: () => input.value.trim() };
  },
  number: (ariaLabel, { min = 0, max, step = 1 } = {}) => (value) => {
    const input = h("input", { type: "number", value: value ?? 0, min, max, step, "aria-label": ariaLabel });
    return { el: input, read: () => Number(input.value) };
  },
  list: (ariaLabel) => (value) => {
    const input = h("input", { value: (value || []).join(", "), "aria-label": ariaLabel, placeholder: "comma, separated" });
    return { el: input, read: () => splitList(input.value) };
  },
  select: (ariaLabel, options) => (value) => {
    const select = h("select", { "aria-label": ariaLabel },
      options.map(([v, label]) => h("option", { value: v, selected: v === value }, label)));
    return { el: select, read: () => select.value };
  },
  check: (ariaLabel) => (value) => {
    const input = h("input", { type: "checkbox", checked: Boolean(value), "aria-label": ariaLabel });
    return { el: input, read: () => input.checked };
  },
};
