export const VENUE_STATUSES = [
  "discovered",
  "researched",
  "draft_ready",
  "sent",
  "follow_up",
  "confirmed",
  "declined",
  "not_a_fit",
] as const;

export type VenueStatus = (typeof VENUE_STATUSES)[number];

export const STATUS_LABELS: Record<VenueStatus, string> = {
  discovered: "Discovered",
  researched: "Researched",
  draft_ready: "Draft ready",
  sent: "Sent",
  follow_up: "Follow-up",
  confirmed: "Confirmed",
  declined: "Declined",
  not_a_fit: "Not a fit",
};

export const VENUE_TYPES = [
  "festival",
  "venue",
  "jazz_club",
  "bar",
  "cultural_center",
] as const;

export type VenueType = (typeof VENUE_TYPES)[number];

export const TYPE_LABELS: Record<VenueType, string> = {
  festival: "Festival",
  venue: "Venue",
  jazz_club: "Jazz club",
  bar: "Bar",
  cultural_center: "Cultural center",
};

export interface VenueArtistAppearance {
  artist_id: number;
  name: string;
  year: string | null;
}

/** Payload for creating or updating a venue — everything but id/artists. */
export interface VenueInput {
  name: string;
  type: VenueType;
  country: string | null;
  region: string | null;
  city: string | null;
  status: VenueStatus;
  fit_score: number | null;
  booking_contact: string | null;
  contact_email: string | null;
  application_method: string | null;
  application_url: string | null;
  application_deadline: string | null;
  event_dates: string | null;
  website: string | null;
  research_notes: string | null;
  last_contact: string | null;
  next_action: string | null;
  source: string | null;
  added_by: string | null;
  /** Per-field research confidence for values filled by Claude. */
  field_confidence: Record<string, string> | null;
}

/** Known team members for the "Added by" picker; extend as the team grows. */
export const ADDED_BY_OPTIONS = ["Antony", "Claude"] as const;

export interface Venue {
  id: number;
  name: string;
  type: VenueType;
  country: string | null;
  region: string | null;
  city: string | null;
  status: VenueStatus;
  fit_score: number | null;
  booking_contact: string | null;
  contact_email: string | null;
  application_method: string | null;
  application_url: string | null;
  application_deadline: string | null;
  event_dates: string | null;
  website: string | null;
  research_notes: string | null;
  last_contact: string | null;
  next_action: string | null;
  source: string | null;
  added_by: string | null;
  field_confidence: Record<string, string> | null;
  artists: VenueArtistAppearance[];
}
