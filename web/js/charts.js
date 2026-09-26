// Small SVG/HTML charts built with DOM APIs (no innerHTML, no library).
// Every mark carries a <title> so hovering shows its exact value.

const SVG_NS = "http://www.w3.org/2000/svg";
const GAUGE_RADIUS = 52;
const GAUGE_STROKE = 12;
const GAUGE_SIZE = (GAUGE_RADIUS + GAUGE_STROKE) * 2;
const MAX_SCORE = 100;

function svg(tag, attrs, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v !== null && v !== undefined) el.setAttribute(k, String(v));
  }
  el.append(...children);
  return el;
}

function tip(el, text) {
  const title = document.createElementNS(SVG_NS, "title");
  title.textContent = text;
  el.append(title);
  return el;
}

function html(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

export const pct = (v, digits = 0) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(digits)}%`);

/* ---------- Score gauge (lead detail) ---------- */

export function scoreGauge(score, label) {
  const value = Math.max(0, Math.min(MAX_SCORE, Number(score) || 0));
  const circumference = 2 * Math.PI * GAUGE_RADIUS;
  const center = GAUGE_SIZE / 2;
  const root = svg("svg", {
    class: "gauge",
    viewBox: `0 0 ${GAUGE_SIZE} ${GAUGE_SIZE}`,
    role: "img",
    "aria-label": `Score ${value} out of ${MAX_SCORE}, ${label} priority`,
  });
  const ring = { cx: center, cy: center, r: GAUGE_RADIUS, fill: "none", "stroke-width": GAUGE_STROKE };
  const num = svg("text", { x: center, y: center + 4, class: "gauge-num", "text-anchor": "middle" });
  num.textContent = value;
  const sub = svg("text", { x: center, y: center + 24, class: "gauge-sub", "text-anchor": "middle" });
  sub.textContent = `of ${MAX_SCORE}`;
  root.append(
    svg("circle", { ...ring, class: "gauge-track" }),
    svg("circle", {
      ...ring,
      class: "gauge-value",
      "stroke-linecap": "round",
      "stroke-dasharray": `${(value / MAX_SCORE) * circumference} ${circumference}`,
      transform: `rotate(-90 ${center} ${center})`,
    }),
    num,
    sub,
  );
  return root;
}

export function pointsBar(awarded, max) {
  const share = max > 0 ? Math.max(0, Math.min(1, awarded / max)) : 0;
  const track = html("span", "bar");
  track.setAttribute("aria-hidden", "true");
  const fill = html("span", "bar-fill");
  fill.style.width = `${share * 100}%`;
  track.append(fill);
  return track;
}

/* ---------- Column chart (one series over time) ---------- */

const COL = { width: 640, height: 200, pad: { top: 16, right: 8, bottom: 28, left: 32 }, gap: 2 };

function niceMax(value) {
  if (value <= 4) return 4;
  const step = 10 ** Math.floor(Math.log10(value));
  return Math.ceil(value / step) * step;
}

export function columnChart(points, { label, format = (p) => `${p.label}: ${p.value}` } = {}) {
  const { width, height, pad, gap } = COL;
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const max = niceMax(Math.max(0, ...points.map((p) => p.value)));
  const slot = plotW / Math.max(1, points.length);
  const root = svg("svg", { class: "chart", viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": label });

  for (const t of [0, max / 2, max]) {
    const y = pad.top + plotH - (t / max) * plotH;
    root.append(svg("line", { x1: pad.left, x2: width - pad.right, y1: y, y2: y, class: t ? "grid" : "axis" }));
    const text = svg("text", { x: pad.left - 6, y: y + 4, class: "tick", "text-anchor": "end" });
    text.textContent = Math.round(t);
    root.append(text);
  }
  const labelEvery = Math.ceil(points.length / 7);
  points.forEach((p, i) => {
    const h = (p.value / max) * plotH;
    const x = pad.left + i * slot + gap / 2;
    const w = Math.max(2, slot - gap - 6);
    const group = svg("g", { class: "mark-group" });
    group.append(svg("rect", { x: pad.left + i * slot, y: pad.top, width: slot, height: plotH, class: "hit" }));
    if (h > 0) {
      const r = Math.min(4, w / 2, h);
      group.append(svg("path", {
        class: "col",
        d: `M${x + 3},${pad.top + plotH} v${-(h - r)} q0,${-r} ${r},${-r} h${w - 2 * r} q${r},0 ${r},${r} v${h - r} z`,
      }));
    }
    tip(group, format(p));
    root.append(group);
    if (i % labelEvery === 0 || i === points.length - 1) {
      const text = svg("text", { x: x + 3 + w / 2, y: height - 8, class: "tick", "text-anchor": "middle" });
      text.textContent = p.short || p.label;
      root.append(text);
    }
  });
  return root;
}

/* ---------- Donut with legend (share of a whole) ---------- */

export function donut(segments, { label, centerValue, centerLabel } = {}) {
  const size = 180;
  const r = 70;
  const stroke = 22;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  const total = segments.reduce((s, x) => s + x.value, 0);
  const root = svg("svg", { class: "donut", viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": label });
  root.append(svg("circle", { cx: c, cy: c, r, fill: "none", "stroke-width": stroke, class: "gauge-track" }));
  let offset = 0;
  const gapLen = total && segments.filter((s) => s.value).length > 1 ? 2 : 0;
  for (const seg of segments) {
    if (!seg.value) continue;
    const len = (seg.value / total) * circumference;
    root.append(tip(svg("circle", {
      cx: c, cy: c, r, fill: "none", "stroke-width": stroke,
      stroke: seg.color,
      "stroke-dasharray": `${Math.max(0, len - gapLen)} ${circumference}`,
      "stroke-dashoffset": -offset,
      transform: `rotate(-90 ${c} ${c})`,
      class: "donut-seg",
    }), `${seg.label}: ${seg.value} (${pct(seg.value / total)})`));
    offset += len;
  }
  const num = svg("text", { x: c, y: c + 4, class: "gauge-num", "text-anchor": "middle" });
  num.textContent = centerValue ?? total;
  const sub = svg("text", { x: c, y: c + 24, class: "gauge-sub", "text-anchor": "middle" });
  sub.textContent = centerLabel || "total";
  root.append(num, sub);

  const legend = html("ul", "legend");
  for (const seg of segments) {
    const item = html("li");
    const swatch = html("span", "swatch");
    swatch.style.background = seg.color;
    item.append(swatch, html("span", "legend-label", seg.label),
      html("span", "legend-value num", `${seg.value} · ${pct(total ? seg.value / total : 0)}`));
    legend.append(item);
  }
  const wrap = html("div", "donut-wrap");
  wrap.append(root, legend);
  return wrap;
}

/* ---------- Horizontal bar list (ranked magnitudes) ---------- */

export function barList(rows, { max } = {}) {
  const top = max ?? Math.max(0, ...rows.map((r) => r.value));
  const list = html("ul", "bar-list");
  for (const row of rows) {
    const item = html("li");
    item.title = row.title || `${row.label}: ${row.display ?? row.value}`;
    const head = html("div", "bar-list-head");
    head.append(html("span", "bar-list-label", row.label), html("span", "bar-list-value num", row.display ?? String(row.value)));
    const track = html("span", "bar");
    const fill = html("span", "bar-fill");
    fill.style.width = `${top > 0 ? Math.max(0, (row.value / top) * 100) : 0}%`;
    if (row.color) fill.style.background = row.color;
    track.append(fill);
    item.append(head, track);
    if (row.note) item.append(html("span", "bar-list-note", row.note));
    list.append(item);
  }
  return list;
}

/* ---------- Line chart on a 0–1 × 0–1 plane (ROC, calibration) ---------- */

const PLANE = { size: 300, pad: { top: 12, right: 12, bottom: 40, left: 54 } };

export function unitLineChart(series, { label, xLabel, yLabel, markers = false } = {}) {
  const { size, pad } = PLANE;
  const w = size - pad.left - pad.right;
  const h = size - pad.top - pad.bottom;
  const X = (v) => pad.left + v * w;
  const Y = (v) => pad.top + h - v * h;
  const root = svg("svg", { class: "chart chart-square", viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": label });

  for (const t of [0, 0.25, 0.5, 0.75, 1]) {
    root.append(svg("line", { x1: X(0), x2: X(1), y1: Y(t), y2: Y(t), class: t ? "grid" : "axis" }));
    const ty = svg("text", { x: pad.left - 6, y: Y(t) + 4, class: "tick", "text-anchor": "end" });
    ty.textContent = t.toFixed(t % 1 ? 2 : 0);
    const tx = svg("text", { x: X(t), y: Y(0) + 16, class: "tick", "text-anchor": "middle" });
    tx.textContent = t.toFixed(t % 1 ? 2 : 0);
    root.append(ty, tx);
  }
  root.append(svg("line", { x1: X(0), y1: Y(0), x2: X(1), y2: Y(1), class: "reference" }));
  const xl = svg("text", { x: X(0.5), y: size - 4, class: "axis-label", "text-anchor": "middle" });
  xl.textContent = xLabel;
  const yl = svg("text", { x: 12, y: Y(0.5), class: "axis-label", "text-anchor": "middle", transform: `rotate(-90 12 ${Y(0.5)})` });
  yl.textContent = yLabel;
  root.append(xl, yl);

  for (const s of series) {
    const d = s.points.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(" ");
    root.append(svg("path", { d, class: "line", stroke: s.color }));
    if (markers) {
      for (const p of s.points) {
        root.append(tip(svg("circle", { cx: X(p.x), cy: Y(p.y), r: 4.5, class: "marker", fill: s.color }), p.title || `${p.x}, ${p.y}`));
      }
    }
  }

  const wrap = html("figure", "line-figure");
  wrap.append(root);
  if (series.length > 1) {
    const legend = html("ul", "legend legend-row");
    for (const s of series) {
      const item = html("li");
      const swatch = html("span", "swatch swatch-line");
      swatch.style.background = s.color;
      item.append(swatch, html("span", "legend-label", s.name));
      legend.append(item);
    }
    wrap.append(legend);
  }
  return wrap;
}

/* ---------- Confusion matrix (2×2 heat grid) ---------- */

const STRONG_CELL = 0.6;

export function confusionMatrix({ tn, fp, fn, tp }) {
  const max = Math.max(tn, fp, fn, tp, 1);
  const cell = (value, text, good) => {
    const strong = value / max > STRONG_CELL;
    const el = html("div", `cm-cell${good ? " cm-good" : ""}${strong ? " cm-strong" : ""}`);
    el.style.setProperty("--level", String(0.12 + (value / max) * 0.88));
    el.title = `${text}: ${value}`;
    el.append(html("b", "num", String(value)), html("span", null, text));
    return el;
  };
  const grid = html("div", "cm");
  grid.setAttribute("role", "table");
  grid.setAttribute("aria-label", "Confusion matrix");
  grid.append(
    html("span", "cm-corner"), html("span", "cm-head", "Predicted: no"), html("span", "cm-head", "Predicted: yes"),
    html("span", "cm-side", "Actually no"), cell(tn, "Correctly skipped", true), cell(fp, "False alarm", false),
    html("span", "cm-side", "Actually yes"), cell(fn, "Missed", false), cell(tp, "Correctly caught", true),
  );
  return grid;
}

/* ---------- KPI tile ---------- */

export function statTile(label, value, note) {
  const tile = html("div", "stat");
  tile.append(html("span", "stat-label", label), html("b", "stat-value num", value));
  if (note) tile.append(html("span", "stat-note", note));
  return tile;
}
