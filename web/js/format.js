// Labels and formatting shared across views.

export const PRIORITY_LABELS = {
  high: "High",
  medium: "Medium",
  low: "Low",
  disqualified: "Disqualified",
};

// Chart marks per priority (validated for colour-blind separation; always shown with labels).
export const PRIORITY_COLORS = {
  high: "#c2410c",
  medium: "#e0a50a",
  low: "#3b82c4",
  disqualified: "#a39c8c",
};

export const STATUS_LABELS = {
  new: "New",
  contacted: "Contacted",
  qualified: "Qualified",
  won: "Won",
  lost: "Lost",
  spam: "Spam",
};

export const DIMENSION_LABELS = {
  service_fit: "Service fit",
  purchase_intent: "Buying intent",
  urgency: "Timeline",
  budget_fit: "Budget",
  decision_authority: "Decision maker",
  company_fit: "Company fit",
  data_completeness: "Contact details",
};

export const TIER_LABELS = {
  core: "Core service",
  adjacent: "Adjacent service",
  out_of_scope: "Out of scope",
  none: "Not in your catalog",
};

export const SOURCE_LABELS = {
  website: "website form",
  line: "LINE",
  facebook: "Facebook",
  email: "email",
  api: "API",
  test: "test",
};

const LANGUAGES = { en: "English", th: "Thai", zh: "Chinese", ja: "Japanese" };

export function languageName(code) {
  return LANGUAGES[code] || (code ? code.toUpperCase() : "Unknown");
}

export function money(amount, currency) {
  if (amount === null || amount === undefined) return null;
  return `${Number(amount).toLocaleString(undefined, { maximumFractionDigits: 0 })} ${currency || ""}`.trim();
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso);
  const diff = Date.now() - then.getTime();
  if (Number.isNaN(diff)) return "";
  if (diff < MINUTE) return "just now";
  if (diff < HOUR) return `${Math.floor(diff / MINUTE)} min ago`;
  if (diff < DAY) return `${Math.floor(diff / HOUR)} h ago`;
  if (diff < 7 * DAY) return `${Math.floor(diff / DAY)} d ago`;
  return then.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function humanize(snake) {
  const text = String(snake || "").replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function splitList(text) {
  return String(text || "")
    .split(/[\n,]/)
    .map((s) => s.trim())
    .filter(Boolean);
}
