const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function apiGet(path, params = {}) {
  const url = new URL(`${API_URL}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  const resp = await fetch(url.toString());
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || resp.statusText);
  }
  return resp.json();
}

export async function apiPost(path, payload) {
  const resp = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : null,
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || resp.statusText);
  }
  return resp.json();
}
