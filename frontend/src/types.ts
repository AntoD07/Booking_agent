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

export type VenueType =
  | "festival"
  | "venue"
  | "jazz_club"
  | "bar"
  | "cultural_center";

export const TYPE_LABELS: Record<VenueType, string> = {
  festival: "Festival",
  venue: "Venue",
  jazz_club: "Jazz club",
  bar: "Bar",
  cultural_center: "Cultural center",
};

export interface ArtistSummary {
  id: number;
  name: string;
}

export interface Venue {
  id: number;
  name: string;
  type: VenueType;
  country: string | null;
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
  artists: ArtistSummary[];
}
