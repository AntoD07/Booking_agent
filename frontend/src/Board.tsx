import {
  STATUS_LABELS,
  TYPE_LABELS,
  VENUE_STATUSES,
  type Venue,
  type VenueStatus,
} from "./types";
import "./Board.css";

function formatDeadline(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
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
  return (
    <article
      className="venue-card"
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
        <p className="venue-deadline">
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
      {error && <p className="board-error">{error}</p>}
      <main className="board" aria-label="Booking pipeline">
        {VENUE_STATUSES.map((status) => {
          const column = venues.filter((venue) => venue.status === status);
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
