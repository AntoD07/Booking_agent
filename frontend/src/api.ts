import type { Venue, VenueInput } from "./types";

export class UnauthorizedError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}

export function login(password: string): Promise<{ ok: boolean }> {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return request("/api/auth/logout", { method: "POST" });
}

export function checkSession(): Promise<{ authenticated: boolean }> {
  return request("/api/auth/me");
}

export function fetchVenues(): Promise<Venue[]> {
  return request("/api/venues");
}

export function createVenue(input: VenueInput): Promise<Venue> {
  return request("/api/venues", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateVenue(
  id: number,
  patch: Partial<VenueInput>,
): Promise<Venue> {
  return request(`/api/venues/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteVenue(id: number): Promise<void> {
  return request(`/api/venues/${id}`, { method: "DELETE" });
}
