import type {
  Artist,
  Suggestion,
  Venue,
  VenueInput,
  VenueType,
} from "./types";

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

export function addAppearance(
  venueId: number,
  name: string,
  year: string | null,
): Promise<Venue> {
  return request(`/api/venues/${venueId}/artists`, {
    method: "POST",
    body: JSON.stringify({ name, year }),
  });
}

export function fetchArtists(): Promise<Artist[]> {
  return request("/api/artists");
}

/** Scans run as background jobs; start one, then poll fetchScanJob. */
export function discoverVenues(
  artists: string[],
): Promise<{ job_id: string }> {
  return request("/api/discovery", {
    method: "POST",
    body: JSON.stringify({ artists }),
  });
}

export interface GeneralScanParams {
  region: string;
  event_type: VenueType | null;
  period: string | null;
}

export function generalScan(
  params: GeneralScanParams,
): Promise<{ job_id: string }> {
  return request("/api/discovery/general", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export interface ScanJob {
  job_id: string;
  status: "running" | "done" | "failed";
  error: string | null;
  suggestions: Suggestion[] | null;
}

export function fetchScanJob(jobId: string): Promise<ScanJob> {
  return request(`/api/discovery/jobs/${jobId}`);
}

export function acceptSuggestion(
  suggestion: Suggestion,
  source: string | null = null,
): Promise<Venue> {
  return request("/api/discovery/accept", {
    method: "POST",
    body: JSON.stringify({
      name: suggestion.name,
      type: suggestion.type,
      city: suggestion.city,
      country: suggestion.country,
      website: suggestion.website,
      artist: suggestion.artist,
      event_dates: suggestion.event_dates,
      source_url: suggestion.source_url,
      source,
    }),
  });
}

export function removeAppearance(
  venueId: number,
  artistId: number,
): Promise<void> {
  return request(`/api/venues/${venueId}/artists/${artistId}`, {
    method: "DELETE",
  });
}
