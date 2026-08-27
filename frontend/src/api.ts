import type {
  Artist,
  BandProfile,
  DraftStatus,
  EmailDraft,
  ResearchRun,
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

export function login(
  bandName: string,
  password: string,
): Promise<{ ok: boolean }> {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ band_name: bandName, password }),
  });
}

export function registerBand(
  adminPassword: string,
  bandName: string,
  password: string,
): Promise<{ ok: boolean; band_name: string; created: boolean }> {
  return request("/api/auth/register-band", {
    method: "POST",
    body: JSON.stringify({
      admin_password: adminPassword,
      band_name: bandName,
      password,
    }),
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return request("/api/auth/logout", { method: "POST" });
}

export function checkSession(): Promise<{
  authenticated: boolean;
  band_name: string;
}> {
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

export function deleteArtist(id: number): Promise<void> {
  return request(`/api/artists/${id}`, { method: "DELETE" });
}

/** Cheap end-to-end Claude connectivity check (fractions of a cent). */
export function pingDiscovery(): Promise<{
  ok: boolean;
  model: string;
  seconds: number;
}> {
  return request("/api/discovery/ping");
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
  /** Latest progress step while the scan runs. */
  note: string | null;
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

/** Start a Search & fill run (or get the one already running); poll after. */
/** Research one venue (each card carries its own Search & fill). */
export function startResearch(venueId: number): Promise<ResearchRun> {
  return request("/api/research/runs", {
    method: "POST",
    body: JSON.stringify({ venue_id: venueId }),
  });
}

export function fetchResearchRun(id: number): Promise<ResearchRun> {
  return request(`/api/research/runs/${id}`);
}

/** Recent Search & fill runs, newest first — past findings stay reviewable. */
export function fetchResearchRuns(): Promise<ResearchRun[]> {
  return request("/api/research/runs");
}

export interface StaleDatesReset {
  cleared: number;
  venues: string[];
}

/** Clear Claude-filled dates from a past edition; affected cards go to Discovered. */
export function clearStaleDates(): Promise<StaleDatesReset> {
  return request("/api/research/clear-stale-dates", { method: "POST" });
}

export function removeAppearance(
  venueId: number,
  artistId: number,
): Promise<void> {
  return request(`/api/venues/${venueId}/artists/${artistId}`, {
    method: "DELETE",
  });
}

// --- Email drafting -------------------------------------------------------

export function fetchBandProfile(): Promise<BandProfile> {
  return request("/api/band-profile");
}

export function updateBandProfile(
  patch: Partial<BandProfile>,
): Promise<BandProfile> {
  return request("/api/band-profile", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

export function fetchDrafts(venueId: number): Promise<EmailDraft[]> {
  return request(`/api/venues/${venueId}/drafts`);
}

/** Draft a pitch email from the band template (may take a few seconds). */
export function generateDraft(venueId: number): Promise<EmailDraft> {
  return request(`/api/venues/${venueId}/drafts`, { method: "POST" });
}

export function updateDraft(
  draftId: number,
  patch: { subject?: string; body?: string; status?: DraftStatus },
): Promise<EmailDraft> {
  return request(`/api/drafts/${draftId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteDraft(draftId: number): Promise<void> {
  return request(`/api/drafts/${draftId}`, { method: "DELETE" });
}
