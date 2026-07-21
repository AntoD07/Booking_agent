import {
  STATUS_LABELS,
  TYPE_LABELS,
  VENUE_STATUSES,
  type Venue,
} from "./types";
import "./Board.css";

function formatDeadline(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function VenueCard({ venue }: { venue: Venue }) {
  const place = [venue.city, venue.country].filter(Boolean).join(", ");
  return (
    <article className="venue-card">
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
    </article>
  );
}

interface BoardProps {
  venues: Venue[];
  error: string | null;
  onSignOut: () => void;
}

export default function Board({ venues, error, onSignOut }: BoardProps) {
  return (
    <div className="board-page">
      <header className="board-header">
        <div>
          <p className="board-overline">Season 2027</p>
          <h1 className="board-title">Venues</h1>
        </div>
        <button className="board-signout" onClick={onSignOut}>
          Sign out
        </button>
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
                column.map((venue) => <VenueCard key={venue.id} venue={venue} />)
              )}
            </section>
          );
        })}
      </main>
    </div>
  );
}
