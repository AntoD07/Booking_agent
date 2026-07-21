import { useState } from "react";
import {
  STATUS_LABELS,
  TYPE_LABELS,
  VENUE_STATUSES,
  VENUE_TYPES,
  type Venue,
  type VenueStatus,
  type VenueType,
} from "./types";
import "./Board.css";

function distinct(values: (string | null)[]): string[] {
  return [...new Set(values.filter((v): v is string => Boolean(v)))].sort(
    (a, b) => a.localeCompare(b),
  );
}

type SortKey = "deadline" | "name" | "country" | "fit";

const SORT_LABELS: Record<SortKey, string> = {
  deadline: "Deadline",
  name: "Name",
  country: "Country",
  fit: "Fit",
};

function compareVenues(a: Venue, b: Venue, key: SortKey): number {
  switch (key) {
    case "deadline":
      // Soonest deadline first; venues without one sink to the bottom.
      if (a.application_deadline && b.application_deadline) {
        return (
          a.application_deadline.localeCompare(b.application_deadline) ||
          a.name.localeCompare(b.name)
        );
      }
      if (a.application_deadline) return -1;
      if (b.application_deadline) return 1;
      return a.name.localeCompare(b.name);
    case "name":
      return a.name.localeCompare(b.name);
    case "country":
      return (
        (a.country ?? "￿").localeCompare(b.country ?? "￿") ||
        a.name.localeCompare(b.name)
      );
    case "fit":
      // Best fit first; unrated venues last.
      return (
        (b.fit_score ?? -1) - (a.fit_score ?? -1) ||
        a.name.localeCompare(b.name)
      );
  }
}

const TWO_MONTHS_MS = 61 * 24 * 60 * 60 * 1000;

/** Deadline already set and closer than two months (or past). */
function isUrgent(venue: Venue): boolean {
  if (!venue.application_deadline) return false;
  return (
    new Date(venue.application_deadline).getTime() - Date.now() < TWO_MONTHS_MS
  );
}

/** Missing what we need to pitch: a contact, or (for festivals) the
 * submission deadline — year-round venues have no deadline to miss. */
function isIncomplete(venue: Venue): boolean {
  const hasContact = Boolean(venue.contact_email || venue.booking_contact);
  if (venue.type === "festival") {
    return !hasContact || !venue.application_deadline;
  }
  return !hasContact;
}

// Deadlines have month granularity: show "January 2027".
function formatDeadline(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

interface VenueCardProps {
  venue: Venue;
  onOpen: (venue: Venue) => void;
  onStatusChange: (venue: Venue, status: VenueStatus) => void;
}

function VenueCard({ venue, onOpen, onStatusChange }: VenueCardProps) {
  const place = [venue.city, venue.country].filter(Boolean).join(", ");
  const urgent = isUrgent(venue);
  const flag = urgent
    ? " venue-card--urgent"
    : isIncomplete(venue)
      ? " venue-card--incomplete"
      : "";
  return (
    <article
      className={`venue-card${flag}`}
      title={
        urgent
          ? "Application deadline in less than two months"
          : flag
            ? "Missing contact or submission deadline"
            : undefined
      }
      role="button"
      tabIndex={0}
      onClick={() => onOpen(venue)}
      onKeyDown={(event) => {
        if (event.key === "Enter" && event.target === event.currentTarget) {
          onOpen(venue);
        }
      }}
    >
      <h3 className="venue-name">{venue.name}</h3>
      <p className="venue-meta">
        {TYPE_LABELS[venue.type]}
        {place && ` · ${place}`}
      </p>
      {venue.application_deadline && (
        <p className={`venue-deadline${urgent ? " venue-deadline--urgent" : ""}`}>
          Apply by {formatDeadline(venue.application_deadline)}
        </p>
      )}
      {venue.next_action && <p className="venue-action">{venue.next_action}</p>}
      <select
        className="venue-status"
        value={venue.status}
        aria-label={`Status of ${venue.name}`}
        onClick={(event) => event.stopPropagation()}
        onChange={(event) =>
          onStatusChange(venue, event.target.value as VenueStatus)
        }
      >
        {VENUE_STATUSES.map((status) => (
          <option key={status} value={status}>
            {STATUS_LABELS[status]}
          </option>
        ))}
      </select>
    </article>
  );
}

interface BoardProps {
  venues: Venue[];
  error: string | null;
  onSignOut: () => void;
  onAddVenue: () => void;
  onOpenVenue: (venue: Venue) => void;
  onStatusChange: (venue: Venue, status: VenueStatus) => void;
}

export default function Board({
  venues,
  error,
  onSignOut,
  onAddVenue,
  onOpenVenue,
  onStatusChange,
}: BoardProps) {
  const [typeFilter, setTypeFilter] = useState<VenueType | "">("");
  const [countryFilter, setCountryFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("deadline");

  const countries = distinct(venues.map((venue) => venue.country));
  const regions = distinct(venues.map((venue) => venue.region));
  const filtered = venues
    .filter(
      (venue) =>
        (!typeFilter || venue.type === typeFilter) &&
        (!countryFilter || venue.country === countryFilter) &&
        (!regionFilter || venue.region === regionFilter),
    )
    .sort((a, b) => compareVenues(a, b, sortKey));
  const filtering = Boolean(typeFilter || countryFilter || regionFilter);

  return (
    <div className="board-page">
      <header className="board-header">
        <div>
          <p className="board-overline">Season 2027</p>
          <h1 className="board-title">Venues</h1>
        </div>
        <div className="board-actions">
          <button className="board-add" onClick={onAddVenue}>
            Add venue
          </button>
          <button className="board-signout" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </header>
      <div className="board-filters">
        <select
          className="board-filter"
          value={typeFilter}
          aria-label="Filter by type"
          onChange={(e) => setTypeFilter(e.target.value as VenueType | "")}
        >
          <option value="">All types</option>
          {VENUE_TYPES.map((type) => (
            <option key={type} value={type}>
              {TYPE_LABELS[type]}
            </option>
          ))}
        </select>
        <select
          className="board-filter"
          value={countryFilter}
          aria-label="Filter by country"
          onChange={(e) => setCountryFilter(e.target.value)}
        >
          <option value="">All countries</option>
          {countries.map((country) => (
            <option key={country} value={country}>
              {country}
            </option>
          ))}
        </select>
        <select
          className="board-filter"
          value={regionFilter}
          aria-label="Filter by region"
          onChange={(e) => setRegionFilter(e.target.value)}
        >
          <option value="">All regions</option>
          {regions.map((region) => (
            <option key={region} value={region}>
              {region}
            </option>
          ))}
        </select>
        <select
          className="board-filter"
          value={sortKey}
          aria-label="Sort venues by"
          onChange={(e) => setSortKey(e.target.value as SortKey)}
        >
          {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
            <option key={key} value={key}>
              Sort: {SORT_LABELS[key]}
            </option>
          ))}
        </select>
        {filtering && (
          <button
            className="board-filter-clear"
            onClick={() => {
              setTypeFilter("");
              setCountryFilter("");
              setRegionFilter("");
            }}
          >
            Clear · {filtered.length} of {venues.length}
          </button>
        )}
      </div>
      <p className="board-legend">
        <span className="legend-swatch legend-urgent" /> deadline under two
        months
        <span className="legend-swatch legend-incomplete" /> contact or
        deadline missing
      </p>
      {error && <p className="board-error">{error}</p>}
      <main className="board" aria-label="Booking pipeline">
        {VENUE_STATUSES.map((status) => {
          const column = filtered.filter((venue) => venue.status === status);
          return (
            <section className="board-column" key={status}>
              <h2 className="column-title">
                {STATUS_LABELS[status]}
                <span className="column-count">{column.length}</span>
              </h2>
              {column.length === 0 ? (
                <p className="column-empty">—</p>
              ) : (
                column.map((venue) => (
                  <VenueCard
                    key={venue.id}
                    venue={venue}
                    onOpen={onOpenVenue}
                    onStatusChange={onStatusChange}
                  />
                ))
              )}
            </section>
          );
        })}
      </main>
    </div>
  );
}
