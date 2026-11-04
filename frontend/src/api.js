// Calls to the backend API.

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : `The server returned ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export async function api(path, { method = "GET", token, body } = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data?.detail);
  return data;
}
