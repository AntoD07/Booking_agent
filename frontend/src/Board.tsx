import { useState } from "react";
import { useI18n, useT, type Lang } from "./i18n";
import LangSwitcher from "./LangSwitcher";
import {
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

type SortKey = "deadline" | "name" | "country";

const SORT_KEYS: SortKey[] = ["deadline", "name", "country"];

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

// Deadlines have month granularity, and the whole board is the 2027 season,
// so the year is noise — show just the month, in the active language.
function formatDeadline(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleDateString(lang, { month: "long" });
}

interface VenueCardProps {
  venue: Venue;
  dragging: boolean;
  onOpen: (venue: Venue) => void;
  onStatusChange: (venue: Venue, status: VenueStatus) => void;
  onResearch: (venue: Venue) => void;
  onDragStart: (venue: Venue) => void;
  onDragEnd: () => void;
}

function VenueCard({
  venue,
  dragging,
  onOpen,
  onStatusChange,
  onResearch,
  onDragStart,
  onDragEnd,
}: VenueCardProps) {
  const t = useT();
  const { lang } = useI18n();
  const place = [venue.city, venue.country].filter(Boolean).join(", ");
  const urgent = isUrgent(venue);
  const flag = urgent
    ? " venue-card--urgent"
    : isIncomplete(venue)
      ? " venue-card--incomplete"
      : "";
  return (
    <article
      className={`venue-card${flag}${dragging ? " venue-card--dragging" : ""}`}
      title={
        urgent
          ? t("board.urgentTitle")
          : flag
            ? t("board.incompleteTitle")
            : undefined
      }
      role="button"
      tabIndex={0}
      // Native drag works with a mouse (desktop); touch devices don't fire
      // these events and keep using the status dropdown below.
      draggable
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(venue.id));
        onDragStart(venue);
      }}
      onDragEnd={onDragEnd}
      onClick={() => onOpen(venue)}
      onKeyDown={(event) => {
        if (event.key === "Enter" && event.target === event.currentTarget) {
          onOpen(venue);
        }
      }}
    >
      <h3 className="venue-name">{venue.name}</h3>
      <p className="venue-meta">
        {t(`type.${venue.type}`)}
        {place && ` · ${place}`}
      </p>
      {venue.application_deadline && (
        <p className={`venue-deadline${urgent ? " venue-deadline--urgent" : ""}`}>
          {t("board.applyBy", {
            month: formatDeadline(venue.application_deadline, lang),
          })}
        </p>
      )}
      <div className="venue-card-actions">
        <button
          type="button"
          className="venue-research"
          title={t("board.searchFillTitle")}
          onClick={(event) => {
            event.stopPropagation();
            onResearch(venue);
          }}
        >
          {t("board.searchFill")}
        </button>
        {venue.status === "discovered" && (
          <button
            type="button"
            className="venue-vet"
            title={t("board.vetTitle")}
            onClick={(event) => {
              event.stopPropagation();
              onStatusChange(venue, "researched");
            }}
          >
            {t("board.vet")} →
          </button>
        )}
      </div>
      <select
        className="venue-status"
        value={venue.status}
        aria-label={t("board.statusOf", { name: venue.name })}
        onClick={(event) => event.stopPropagation()}
        onChange={(event) =>
          onStatusChange(venue, event.target.value as VenueStatus)
        }
      >
        {VENUE_STATUSES.map((status) => (
          <option key={status} value={status}>
            {t(`status.${status}`)}
          </option>
        ))}
      </select>
    </article>
  );
}

interface BoardProps {
  venues: Venue[];
  error: string | null;
  bandName: string;
  onSignOut: () => void;
  onAddVenue: () => void;
  onOpenScan: () => void;
  onResearchVenue: (venue: Venue) => void;
  onOpenProfile: () => void;
  onOpenVenue: (venue: Venue) => void;
  onStatusChange: (venue: Venue, status: VenueStatus) => void;
}

export default function Board({
  venues,
  error,
  bandName,
  onSignOut,
  onAddVenue,
  onOpenScan,
  onResearchVenue,
  onOpenProfile,
  onOpenVenue,
  onStatusChange,
}: BoardProps) {
  const t = useT();
  const [typeFilter, setTypeFilter] = useState<VenueType | "">("");
  const [countryFilter, setCountryFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("deadline");
  // Drag-and-drop between columns (desktop): the card being dragged and the
  // column currently under the cursor.
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<VenueStatus | null>(null);
  const draggingVenue =
    draggingId === null
      ? null
      : (venues.find((venue) => venue.id === draggingId) ?? null);

  const endDrag = () => {
    setDraggingId(null);
    setDragOverStatus(null);
  };

  // The dragged venue id comes from the drop event's dataTransfer, not React
  // state, so a drop always resolves the right card regardless of render timing.
  const dropOn = (status: VenueStatus, draggedId: string) => {
    endDrag();
    const id = Number(draggedId);
    const venue = Number.isNaN(id)
      ? null
      : (venues.find((candidate) => candidate.id === id) ?? null);
    if (venue && venue.status !== status) {
      onStatusChange(venue, status);
    }
  };

  const countries = distinct(venues.map((venue) => venue.country));
  const filtered = venues
    .filter(
      (venue) =>
        (!typeFilter || venue.type === typeFilter) &&
        (!countryFilter || venue.country === countryFilter),
    )
    .sort((a, b) => compareVenues(a, b, sortKey));
  const filtering = Boolean(typeFilter || countryFilter);

  return (
    <div className="board-page">
      <header className="board-header">
        <div>
          <p className="board-overline">
            {bandName
              ? t("board.seasonWithBand", { band: bandName })
              : t("board.season")}
          </p>
          <h1 className="board-title">{t("board.title")}</h1>
        </div>
        <div className="board-actions">
          <LangSwitcher />
          <button className="board-add" onClick={onAddVenue}>
            {t("board.addVenue")}
          </button>
          <button className="board-scan" onClick={onOpenScan}>
            {t("board.manualScan")}
          </button>
          <button className="board-scan" onClick={onOpenProfile}>
            {t("board.bandProfile")}
          </button>
          <button className="board-signout" onClick={onSignOut}>
            {t("board.signOut")}
          </button>
        </div>
      </header>
      <div className="board-filters">
        <select
          className="board-filter"
          value={typeFilter}
          aria-label={t("board.filterByType")}
          onChange={(e) => setTypeFilter(e.target.value as VenueType | "")}
        >
          <option value="">{t("board.allTypes")}</option>
          {VENUE_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(`type.${type}`)}
            </option>
          ))}
        </select>
        <select
          className="board-filter"
          value={countryFilter}
          aria-label={t("board.filterByCountry")}
          onChange={(e) => setCountryFilter(e.target.value)}
        >
          <option value="">{t("board.allCountries")}</option>
          {countries.map((country) => (
            <option key={country} value={country}>
              {country}
            </option>
          ))}
        </select>
        <select
          className="board-filter"
          value={sortKey}
          aria-label={t("board.sortBy")}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
        >
          {SORT_KEYS.map((key) => (
            <option key={key} value={key}>
              {t("board.sortPrefix", { label: t(`board.sort.${key}`) })}
            </option>
          ))}
        </select>
        {filtering && (
          <button
            className="board-filter-clear"
            onClick={() => {
              setTypeFilter("");
              setCountryFilter("");
            }}
          >
            {t("board.clearFilters", {
              shown: filtered.length,
              total: venues.length,
            })}
          </button>
        )}
      </div>
      <p className="board-legend">
        <span className="legend-swatch legend-urgent" /> {t("board.legendUrgent")}
        <span className="legend-swatch legend-incomplete" />{" "}
        {t("board.legendIncomplete")}
      </p>
      {error && <p className="board-error">{error}</p>}
      <main className="board" aria-label={t("board.pipeline")}>
        {VENUE_STATUSES.map((status) => {
          const column = filtered.filter((venue) => venue.status === status);
          // Highlight a column as a drop target, but not the card's own column.
          const isTarget =
            dragOverStatus === status &&
            draggingVenue !== null &&
            draggingVenue.status !== status;
          return (
            <section
              className={`board-column${isTarget ? " board-column--drag-over" : ""}`}
              key={status}
              onDragOver={(event) => {
                // Always allow the drop. Gating preventDefault on React state
                // is unreliable: if the state isn't current when the native
                // dragover fires, the browser rejects the drop and the card
                // never moves. The dragged id lives in dataTransfer instead.
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                if (dragOverStatus !== status) {
                  setDragOverStatus(status);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                dropOn(status, event.dataTransfer.getData("text/plain"));
              }}
            >
              <h2 className="column-title">
                {t(`status.${status}`)}
                <span className="column-count">{column.length}</span>
              </h2>
              {column.length === 0 ? (
                <p className="column-empty">{t("common.none")}</p>
              ) : (
                column.map((venue) => (
                  <VenueCard
                    key={venue.id}
                    venue={venue}
                    dragging={venue.id === draggingId}
                    onOpen={onOpenVenue}
                    onStatusChange={onStatusChange}
                    onResearch={onResearchVenue}
                    onDragStart={(v) => setDraggingId(v.id)}
                    onDragEnd={endDrag}
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
