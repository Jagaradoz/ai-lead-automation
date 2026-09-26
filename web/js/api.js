// Fetch wrapper for the app's JSON API. Errors carry the server's readable `detail`.

const TOKEN_KEY = "lead-desk-admin-token";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function getAdminToken() {
  try { return sessionStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; }
}

export function setAdminToken(token) {
  try { sessionStorage.setItem(TOKEN_KEY, token); } catch { /* storage unavailable: token lasts for this call only */ }
}

function detailText(data) {
  const detail = data && data.detail;
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).filter((p) => p !== "body").join(".")}: ${d.msg}`).join("; ");
  }
  return String(detail);
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getAdminToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check that it is still running.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailText(data) || `The server returned ${res.status}.`);
  return data;
}

export const leadsApi = {
  list: (params) => api(`/api/leads?${new URLSearchParams(params)}`),
  get: (id) => api(`/api/leads/${id}`),
  process: (payload) => api("/api/leads/process", { method: "POST", body: payload }),
  patch: (id, body) => api(`/api/leads/${id}`, { method: "PATCH", body }),
  remove: (id) => api(`/api/leads/${id}`, { method: "DELETE" }),
  rescore: (id) => api(`/api/leads/${id}/rescore`, { method: "POST" }),
  rescoreAll: () => api("/api/leads/rescore-all", { method: "POST" }),
  reanalyze: (id) => api(`/api/leads/${id}/reanalyze`, { method: "POST" }),
  followup: (id) => api(`/api/leads/${id}/followup`),
  samples: () => api("/api/samples"),
};

export const settingsApi = {
  health: () => api("/health"),
  providers: () => api("/api/providers"),
  model: () => api("/api/settings/model"),
  saveModel: (body) => api("/api/settings/model", { method: "PUT", body }),
  testModel: (body) => api("/api/settings/model/test", { method: "POST", body }),
  listModels: (body) => api("/api/providers/models", { method: "POST", body }),
  profile: () => api("/api/settings/profile"),
  saveProfile: (body) => api("/api/settings/profile", { method: "PUT", body }),
  resetProfile: () => api("/api/settings/profile/reset", { method: "POST" }),
};

export const insightsApi = {
  stats: (days) => api(`/api/stats?${new URLSearchParams({ days })}`),
  modelReport: () => api("/api/model/report"),
};
