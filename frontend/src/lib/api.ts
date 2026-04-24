const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  return response.json() as Promise<T>;
}

export async function getHealthcheck() {
  return request("/health");
}

export async function getDeadDataSummary() {
  return request("/dead-data/summary");
}

export async function getDeadDataScan() {
  return request("/dead-data/scan");
}

export async function validateDeadDataAsset(fqn: string) {
  return request(`/dead-data/validate/${encodeURIComponent(fqn).replace(/%2F/g, "/")}`, {
    method: "POST",
  });
}

export async function reviewDeadDataAsset(fqn: string) {
  return request(`/dead-data/review/${encodeURIComponent(fqn).replace(/%2F/g, "/")}`, {
    method: "POST",
  });
}

export async function removeDeadDataAsset(fqn: string) {
  return request(`/dead-data/remove/${encodeURIComponent(fqn).replace(/%2F/g, "/")}`, {
    method: "POST",
  });
}

export async function getPassport(fqn: string) {
  return request<any>(`/passport/${encodeURIComponent(fqn).replace(/%2F/g, "/")}`);
}

export async function getBlastRadiusTable(fqn: string) {
  return request(`/blast-radius/table/${encodeURIComponent(fqn).replace(/%2F/g, "/")}`);
}

export async function getStormAlerts() {
  return request("/storm/alerts");
}

export async function getWatchedAssets() {
  return request("/storm/watched");
}

export async function simulateStormAlert(payload: unknown) {
  return request("/storm/simulate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function askChat(payload: unknown) {
  return request("/chat/ask", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function explainRootCause(fqn: string) {
  return request(`/rca/explain/${encodeURIComponent(fqn).replace(/%2F/g, "/")}`);
}
