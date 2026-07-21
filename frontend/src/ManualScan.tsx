import { useEffect, useState } from "react";
import {
  UnauthorizedError,
  acceptSuggestion,
  discoverVenues,
  fetchArtists,
  fetchScanJob,
  generalScan,
} from "./api";
import {
  TYPE_LABELS,
  VENUE_TYPES,
  type Artist,
  type Suggestion,
  type VenueType,
} from "./types";
import "./ManualScan.css";

const MAX_ARTISTS = 5;
const POLL_INTERVAL_MS = 4000;
// Backend requests are capped server-side; if a job somehow never settles,
// stop asking after this long.
const MAX_WAIT_MS = 12 * 60 * 1000;

type Mode = "artists" | "general";
type ReviewState = "pending" | "accepting" | "accepted" | "dismissed";

function formatScanned(iso: string | null): string {
  if (!iso) {
    return "Never scanned";
  }
  return `Scanned ${new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  })}`;
}

interface ManualScanProps {
  onBack: () => void;
  onUnauthorized: () => void;
}

export default function ManualScan({ onBack, onUnauthorized }: ManualScanProps) {
  const [mode, setMode] = useState<Mode>("artists");

  // By-artist form
  const [artists, setArtists] = useState<Artist[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  // Free-text names not (yet) in the artists table, always part of the scan.
  const [extras, setExtras] = useState<string[]>([]);
  const [extraInput, setExtraInput] = useState("");

  // General form
  const [region, setRegion] = useState("");
  const [eventType, setEventType] = useState<VenueType | "">("");
  const [period, setPeriod] = useState("");

  // Shared scan + review state
  const [scanning, setScanning] = useState(false);
  const [scanned, setScanned] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [review, setReview] = useState<ReviewState[]>([]);
  // Source label written on accepted venues; null lets the artist hook apply.
  const [acceptSource, setAcceptSource] = useState<string | null>(null);

  const loadArtists = () => {
    fetchArtists()
      .then(setArtists)
      .catch(() => {
        // The picker is a convenience; free text still works without it.
      });
  };

  useEffect(loadArtists, []);

  const handleError = (err: unknown) => {
    if (err instanceof UnauthorizedError) {
      onUnauthorized();
    } else {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  const chosen = [...selected, ...extras];
  const full = chosen.length >= MAX_ARTISTS;

  const toggleArtist = (name: string) => {
    setSelected((names) =>
      names.includes(name)
        ? names.filter((n) => n !== name)
        : full
          ? names
          : [...names, name],
    );
  };

  const addExtra = () => {
    const name = extraInput.trim();
    if (!name || full) {
      return;
    }
    const known = artists.find(
      (artist) => artist.name.toLowerCase() === name.toLowerCase(),
    );
    if (known) {
      // Typed a known artist: tick it instead of duplicating it.
      if (!selected.includes(known.name)) {
        setSelected((names) => [...names, known.name]);
      }
    } else if (!extras.some((n) => n.toLowerCase() === name.toLowerCase())) {
      setExtras((names) => [...names, name]);
    }
    setExtraInput("");
  };

  // Scans run as background jobs on the server (they take minutes — too
  // long for one HTTP request to survive proxies and mobile browsers), so
  // we start the job and poll until it settles.
  const runScan = async (start: () => Promise<{ job_id: string }>) => {
    setScanning(true);
    setError(null);
    setSuggestions([]);
    try {
      const { job_id } = await start();
      const startedAt = Date.now();
      for (;;) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
        const job = await fetchScanJob(job_id);
        if (job.status === "done") {
          const found = job.suggestions ?? [];
          setSuggestions(found);
          setReview(found.map(() => "pending"));
          setScanned(true);
          break;
        }
        if (job.status === "failed") {
          setError(job.error ?? "The scan failed — try again.");
          break;
        }
        if (Date.now() - startedAt > MAX_WAIT_MS) {
          setError(
            "The scan is taking unusually long. Leave it and try again in a few minutes.",
          );
          break;
        }
      }
    } catch (err) {
      handleError(err);
    } finally {
      setScanning(false);
    }
  };

  const runArtistScan = async (event: React.FormEvent) => {
    event.preventDefault();
    if (chosen.length === 0 || scanning) {
      return;
    }
    setAcceptSource(null); // let the backend write the artist hook
    await runScan(() => discoverVenues(chosen));
    // The scan stamped last_scanned on the selected artists.
    loadArtists();
  };

  const runGeneralScan = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!region.trim() || scanning) {
      return;
    }
    const what = eventType ? TYPE_LABELS[eventType].toLowerCase() + "s" : "events";
    setAcceptSource(
      `General scan — ${what} in ${region.trim()}${
        period.trim() ? `, ${period.trim()}` : ""
      }`,
    );
    await runScan(() =>
      generalScan({
        region: region.trim(),
        event_type: eventType || null,
        period: period.trim() || null,
      }),
    );
  };

  const accept = async (index: number) => {
    setReview((states) =>
      states.map((s, i) => (i === index ? "accepting" : s)),
    );
    try {
      await acceptSuggestion(suggestions[index], acceptSource);
      setReview((states) =>
        states.map((s, i) => (i === index ? "accepted" : s)),
      );
    } catch (err) {
      setReview((states) =>
        states.map((s, i) => (i === index ? "pending" : s)),
      );
      handleError(err);
    }
  };

  const dismiss = (index: number) => {
    setReview((states) =>
      states.map((s, i) => (i === index ? "dismissed" : s)),
    );
  };

  const visible = suggestions
    .map((suggestion, index) => ({ suggestion, index, state: review[index] }))
    .filter(({ state }) => state !== "dismissed");

  return (
    <div className="scan-page">
      <header className="scan-header">
        <div>
          <p className="scan-overline">Season 2027</p>
          <h1 className="scan-title">Manual scan</h1>
        </div>
        <button className="scan-back" onClick={onBack}>
          Back to venues
        </button>
      </header>

      <main className="scan-main">
        <div className="scan-modes" role="tablist" aria-label="Research method">
          <button
            className={`scan-mode${mode === "artists" ? " is-active" : ""}`}
            role="tab"
            aria-selected={mode === "artists"}
            onClick={() => setMode("artists")}
          >
            By artist
          </button>
          <button
            className={`scan-mode${mode === "general" ? " is-active" : ""}`}
            role="tab"
            aria-selected={mode === "general"}
            onClick={() => setMode("general")}
          >
            By region
          </button>
        </div>

        {mode === "artists" ? (
          <>
            <p className="scan-lede">
              Follow the artists we admire — every stage they have played is
              a lead for us. Choose up to {MAX_ARTISTS} reference artists and
              Claude will search the manouche and swing circuit for the
              venues behind their tour dates.
            </p>

            <form className="scan-form" onSubmit={runArtistScan}>
              <fieldset className="scan-artists">
                <legend className="scan-label">Reference artists</legend>
                {artists.length === 0 && extras.length === 0 && (
                  <p className="scan-empty-list">
                    No artists in the table yet — add a name below.
                  </p>
                )}
                {artists.map((artist) => {
                  const checked = selected.includes(artist.name);
                  return (
                    <label
                      className={`scan-artist${checked ? " is-checked" : ""}`}
                      key={artist.id}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!checked && full}
                        onChange={() => toggleArtist(artist.name)}
                      />
                      <span className="scan-artist-name">{artist.name}</span>
                      <span className="scan-artist-scanned">
                        {formatScanned(artist.last_scanned)}
                      </span>
                    </label>
                  );
                })}
                {extras.map((name) => (
                  <label className="scan-artist is-checked" key={name}>
                    <input
                      type="checkbox"
                      checked
                      onChange={() =>
                        setExtras((names) => names.filter((n) => n !== name))
                      }
                    />
                    <span className="scan-artist-name">{name}</span>
                    <span className="scan-artist-scanned">New name</span>
                  </label>
                ))}
              </fieldset>

              <div className="scan-extra">
                <input
                  className="scan-input"
                  value={extraInput}
                  onChange={(e) => setExtraInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addExtra();
                    }
                  }}
                  placeholder="Another band, not in the list"
                  aria-label="Add an artist by name"
                  disabled={full}
                />
                <button
                  className="scan-extra-add"
                  type="button"
                  onClick={addExtra}
                  disabled={!extraInput.trim() || full}
                >
                  Add
                </button>
              </div>

              <button
                className="scan-submit"
                type="submit"
                disabled={scanning || chosen.length === 0}
              >
                {scanning
                  ? "Scanning…"
                  : chosen.length === 0
                    ? "Scan"
                    : `Scan ${chosen.length} ${
                        chosen.length === 1 ? "artist" : "artists"
                      }`}
              </button>
            </form>
          </>
        ) : (
          <>
            <p className="scan-lede">
              Cast a wider net — search a region for festivals and stages of
              a given kind over a period, whether or not our reference
              artists have played them.
            </p>

            <form className="scan-form" onSubmit={runGeneralScan}>
              <label className="scan-field">
                <span className="scan-label">Region</span>
                <input
                  className="scan-input"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  placeholder="e.g. south of France, Flanders, Bavaria"
                  required
                />
              </label>
              <label className="scan-field">
                <span className="scan-label">
                  Event type <span className="scan-optional">optional</span>
                </span>
                <select
                  className="scan-select"
                  value={eventType}
                  onChange={(e) =>
                    setEventType(e.target.value as VenueType | "")
                  }
                >
                  <option value="">Any kind of stage</option>
                  {VENUE_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {TYPE_LABELS[type]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="scan-field">
                <span className="scan-label">
                  Period <span className="scan-optional">optional</span>
                </span>
                <input
                  className="scan-input"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                  placeholder="e.g. summer 2027, next spring"
                />
              </label>

              <button
                className="scan-submit"
                type="submit"
                disabled={scanning || !region.trim()}
              >
                {scanning ? "Scanning…" : "Scan the region"}
              </button>
            </form>
          </>
        )}

        {scanning && (
          <p className="scan-status">
            Claude is searching — this can take a minute or two.
          </p>
        )}
        {error && <p className="scan-error">{error}</p>}

        {!scanning && scanned && visible.length === 0 && (
          <p className="scan-status">
            Nothing left to review. Run another scan or return to the board.
          </p>
        )}

        {visible.length > 0 && (
          <section className="scan-results" aria-label="Suggested venues">
            <h2 className="scan-results-title">
              For review
              <span className="scan-results-count">{visible.length}</span>
            </h2>
            <p className="scan-results-note">
              Nothing joins the pipeline until you accept it.
            </p>
            {visible.map(({ suggestion, index, state }) => {
              const place = [suggestion.city, suggestion.country]
                .filter(Boolean)
                .join(", ");
              return (
                <article className="suggestion-card" key={index}>
                  <h3 className="suggestion-name">{suggestion.name}</h3>
                  <p className="suggestion-meta">
                    {TYPE_LABELS[suggestion.type]}
                    {place && ` · ${place}`}
                  </p>
                  {suggestion.artist && (
                    <p className="suggestion-artist">
                      {suggestion.artist} played here
                    </p>
                  )}
                  {suggestion.event_dates && (
                    <p className="suggestion-dates">{suggestion.event_dates}</p>
                  )}
                  {(suggestion.website || suggestion.source_url) && (
                    <p className="suggestion-links">
                      {suggestion.website && (
                        <a
                          href={suggestion.website}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Website
                        </a>
                      )}
                      {suggestion.source_url && (
                        <a
                          href={suggestion.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Source
                        </a>
                      )}
                    </p>
                  )}
                  {suggestion.already_in_pipeline ? (
                    <>
                      <p className="suggestion-known">
                        Already in the pipeline
                        {suggestion.matched_venue_name &&
                          ` as “${suggestion.matched_venue_name}”`}
                      </p>
                      <div className="suggestion-actions">
                        <button
                          className="suggestion-dismiss"
                          onClick={() => dismiss(index)}
                        >
                          Dismiss
                        </button>
                      </div>
                    </>
                  ) : state === "accepted" ? (
                    <p className="suggestion-accepted">Added to the pipeline</p>
                  ) : (
                    <div className="suggestion-actions">
                      <button
                        className="suggestion-accept"
                        disabled={state === "accepting"}
                        onClick={() => accept(index)}
                      >
                        {state === "accepting" ? "Adding…" : "Add to pipeline"}
                      </button>
                      <button
                        className="suggestion-dismiss"
                        onClick={() => dismiss(index)}
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                </article>
              );
            })}
          </section>
        )}
      </main>
    </div>
  );
}
