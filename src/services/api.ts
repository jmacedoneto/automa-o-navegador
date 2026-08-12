/**
 * Base API client — all requests go to the FastAPI backend at /api
 */

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}

export const api = {
  get:    <T>(path: string)                          => request<T>(path),
  post:   <T>(path: string, body?: unknown)          => request<T>(path, { method: "POST",   body: body !== undefined ? JSON.stringify(body) : undefined }),
  put:    <T>(path: string, body?: unknown)          => request<T>(path, { method: "PUT",    body: JSON.stringify(body) }),
  patch:  <T>(path: string, body?: unknown)          => request<T>(path, { method: "PATCH",  body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string)                          => request<T>(path, { method: "DELETE" }),
};
