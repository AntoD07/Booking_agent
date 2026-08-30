import { useEffect, useState } from "react";
import {
  UnauthorizedError,
  acceptSuggestion,
  deleteArtist,
  discoverVenues,
  fetchArtists,
  fetchScanJob,
  generalScan,
  pingDiscovery,
} from "./api";
import {
  VENUE_TYPES,
  type Artist,
  type Suggestion,
  type VenueType,
} from "./types";
import { useI18n, type Lang } from "./i18n";
import "./ManualScan.css";

const MAX_ARTISTS = 5;
const POLL_INTERVAL_MS = 4000;
// Backend requests are capped server-side; if a job somehow never settles,
// stop asking after this long.
const MAX_WAIT_MS = 12 * 60 * 1000;

type Mode = "artists" | "general";
type ReviewState = "pending" | "accepting" | "accepted" | "dismissed";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

function formatScanned(
  iso: string | null,
  t: Translate,
  lang: Lang,
): string {
  if (!iso) {
    return t("manualScan.neverScanned");
  }
  return t("manualScan.scannedOn", {
    date: new Date(iso).toLocaleDateString(lang, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }),
  });
}

interface ManualScanProps {
  onBack: () => void;
  onUnauthorized: () => void;
}

export default function ManualScan({ onBack, onUnauthorized }: ManualScanProps) {
  const { t, lang } = useI18n();
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
  const [pinging, setPinging] = useState(false);
  const [pingResult, setPingResult] = useState<string | null>(null);
  const [scanNote, setScanNote] = useState<string | null>(null);

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
      setError(err instanceof Error ? err.message : t("manualScan.somethingWentWrong"));
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

  const removeArtist = async (artist: Artist) => {
    if (!window.confirm(t("manualScan.removeArtistConfirm", { name: artist.name }))) {
      return;
    }
    try {
      await deleteArtist(artist.id);
      setSelected((names) => names.filter((n) => n !== artist.name));
      loadArtists();
    } catch (err) {
      handleError(err);
    }
  };

  const testConnection = async () => {
    setPinging(true);
    setPingResult(null);
    try {
      const result = await pingDiscovery();
      setPingResult(t("manualScan.pingSuccess", { seconds: result.seconds }));
    } catch (err) {
      setPingResult(
        err instanceof Error ? err.message : t("manualScan.pingFailed"),
      );
    } finally {
      setPinging(false);
    }
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
    setScanNote(null);
    try {
      const { job_id } = await start();
      const startedAt = Date.now();
      for (;;) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
        let job;
        try {
          job = await fetchScanJob(job_id);
        } catch (err) {
          if (err instanceof Error && err.message === "Scan not found") {
            // The in-memory job vanished mid-scan: the server restarted
            // (free hosting tiers do this). Nothing to recover.
            setError(t("manualScan.serverRestarted"));
            break;
          }
          throw err;
        }
        if (job.note) {
          setScanNote(job.note);
        }
        if (job.status === "done") {
          const found = job.suggestions ?? [];
          setSuggestions(found);
          setReview(found.map(() => "pending"));
          setScanned(true);
          break;
        }
        if (job.status === "failed") {
          setError(job.error ?? t("manualScan.scanFailed"));
          break;
        }
        if (Date.now() - startedAt > MAX_WAIT_MS) {
          setError(t("manualScan.scanTakingLong"));
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
    const what = eventType ? t(`type.${eventType}`) : t("manualScan.eventsGeneric");
    const where = region.trim();
    setAcceptSource(
      period.trim()
        ? t("manualScan.generalScanSourcePeriod", {
            what,
            region: where,
            period: period.trim(),
          })
        : t("manualScan.generalScanSource", { what, region: where }),
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

  type VisibleItem = (typeof visible)[number];

  // Group suggestions by appearance year, most recent first, unknown year
  // last. Artist scans carry a year; the general scan doesn't, so its whole
  // list falls into one unlabelled group and renders flat (see anyYear).
  const anyYear = visible.some(({ suggestion }) => suggestion.year);
  const byYear = new Map<string, VisibleItem[]>();
  for (const item of visible) {
    const key = item.suggestion.year ?? "";
    (byYear.get(key) ?? byYear.set(key, []).get(key)!).push(item);
  }
  const yearGroups = [...byYear.entries()].sort(([a], [b]) => {
    if (a === b) return 0;
    if (a === "") return 1; // unknown year sinks to the bottom
    if (b === "") return -1;
    return b.localeCompare(a); // most recent first
  });

  const renderCard = ({ suggestion, index, state }: VisibleItem) => {
    const place = [suggestion.city, suggestion.country]
      .filter(Boolean)
      .join(", ");
    return (
      <article className="suggestion-card" key={index}>
        <h3 className="suggestion-name">{suggestion.name}</h3>
        <p className="suggestion-meta">
          {t(`type.${suggestion.type}`)}
          {place && ` · ${place}`}
        </p>
        {suggestion.artist && (
          <p className="suggestion-artist">
            {t("manualScan.artistPlayedHere", { artist: suggestion.artist })}
            {suggestion.year && ` (${suggestion.year})`}
          </p>
        )}
        {suggestion.event_dates && (
          <p className="suggestion-dates">{suggestion.event_dates}</p>
        )}
        {(suggestion.website || suggestion.source_url) && (
          <p className="suggestion-links">
            {suggestion.website && (
              <a href={suggestion.website} target="_blank" rel="noreferrer">
                {t("manualScan.website")}
              </a>
            )}
            {suggestion.source_url && (
              <a href={suggestion.source_url} target="_blank" rel="noreferrer">
                {t("manualScan.source")}
              </a>
            )}
          </p>
        )}
        {suggestion.already_in_pipeline ? (
          <>
            <p className="suggestion-known">
              {t("manualScan.alreadyInPipeline")}
              {suggestion.matched_venue_name &&
                t("manualScan.alreadyInPipelineAs", {
                  name: suggestion.matched_venue_name,
                })}
            </p>
            <div className="suggestion-actions">
              <button
                className="suggestion-dismiss"
                onClick={() => dismiss(index)}
              >
                {t("manualScan.dismiss")}
              </button>
            </div>
          </>
        ) : state === "accepted" ? (
          <p className="suggestion-accepted">{t("manualScan.added")}</p>
        ) : (
          <div className="suggestion-actions">
            <button
              className="suggestion-accept"
              disabled={state === "accepting"}
              onClick={() => accept(index)}
            >
              {state === "accepting"
                ? t("manualScan.adding")
                : t("manualScan.addToPipeline")}
            </button>
            <button
              className="suggestion-dismiss"
              onClick={() => dismiss(index)}
            >
              {t("manualScan.dismiss")}
            </button>
          </div>
        )}
      </article>
    );
  };

  return (
    <div className="scan-page">
      <header className="scan-header">
        <div>
          <p className="scan-overline">{t("manualScan.seasonOverline")}</p>
          <h1 className="scan-title">{t("manualScan.title")}</h1>
        </div>
        <button className="scan-back" onClick={onBack}>
          {t("manualScan.backToVenues")}
        </button>
      </header>

      <main className="scan-main">
        <div className="scan-modes" role="tablist" aria-label={t("manualScan.researchMethod")}>
          <button
            className={`scan-mode${mode === "artists" ? " is-active" : ""}`}
            role="tab"
            aria-selected={mode === "artists"}
            onClick={() => setMode("artists")}
          >
            {t("manualScan.byArtist")}
          </button>
          <button
            className={`scan-mode${mode === "general" ? " is-active" : ""}`}
            role="tab"
            aria-selected={mode === "general"}
            onClick={() => setMode("general")}
          >
            {t("manualScan.byRegion")}
          </button>
        </div>

        {mode === "artists" ? (
          <>
            <p className="scan-lede">
              {t("manualScan.artistLede", { count: MAX_ARTISTS })}
            </p>

            <form className="scan-form" onSubmit={runArtistScan}>
              <fieldset className="scan-artists">
                <legend className="scan-label">{t("manualScan.referenceArtists")}</legend>
                {artists.length === 0 && extras.length === 0 && (
                  <p className="scan-empty-list">
                    {t("manualScan.emptyArtistList")}
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
                        {formatScanned(artist.last_scanned, t, lang)}
                      </span>
                      <button
                        className="scan-artist-remove"
                        type="button"
                        aria-label={t("manualScan.removeArtistAria", { name: artist.name })}
                        title={t("manualScan.removeArtistTitle", { name: artist.name })}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          removeArtist(artist);
                        }}
                      >
                        ×
                      </button>
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
                    <span className="scan-artist-scanned">{t("manualScan.newName")}</span>
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
                  placeholder={t("manualScan.extraPlaceholder")}
                  aria-label={t("manualScan.addArtistAria")}
                  disabled={full}
                />
                <button
                  className="scan-extra-add"
                  type="button"
                  onClick={addExtra}
                  disabled={!extraInput.trim() || full}
                >
                  {t("common.add")}
                </button>
              </div>

              <button
                className="scan-submit"
                type="submit"
                disabled={scanning || chosen.length === 0}
              >
                {scanning
                  ? t("manualScan.scanning")
                  : chosen.length === 0
                    ? t("manualScan.scan")
                    : chosen.length === 1
                      ? t("manualScan.scanCountOne", { count: chosen.length })
                      : t("manualScan.scanCountMany", { count: chosen.length })}
              </button>
            </form>
          </>
        ) : (
          <>
            <p className="scan-lede">
              {t("manualScan.generalLede")}
            </p>

            <form className="scan-form" onSubmit={runGeneralScan}>
              <label className="scan-field">
                <span className="scan-label">{t("manualScan.region")}</span>
                <input
                  className="scan-input"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  placeholder={t("manualScan.regionPlaceholder")}
                  required
                />
              </label>
              <label className="scan-field">
                <span className="scan-label">
                  {t("manualScan.eventType")} <span className="scan-optional">{t("manualScan.optional")}</span>
                </span>
                <select
                  className="scan-select"
                  value={eventType}
                  onChange={(e) =>
                    setEventType(e.target.value as VenueType | "")
                  }
                >
                  <option value="">{t("manualScan.anyStage")}</option>
                  {VENUE_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {t(`type.${type}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="scan-field">
                <span className="scan-label">
                  {t("manualScan.period")} <span className="scan-optional">{t("manualScan.optional")}</span>
                </span>
                <input
                  className="scan-input"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                  placeholder={t("manualScan.periodPlaceholder")}
                />
              </label>

              <button
                className="scan-submit"
                type="submit"
                disabled={scanning || !region.trim()}
              >
                {scanning ? t("manualScan.scanning") : t("manualScan.scanRegion")}
              </button>
            </form>
          </>
        )}

        <p className="scan-ping">
          <button
            className="scan-ping-button"
            type="button"
            onClick={testConnection}
            disabled={pinging}
          >
            {pinging ? t("manualScan.testing") : t("manualScan.testConnection")}
          </button>
          {pingResult && <span className="scan-ping-result">{pingResult}</span>}
        </p>

        {scanning && (
          <p className="scan-status">
            {t("manualScan.searchingStatus")}
            {scanNote && (
              <span className="scan-note">
                <br />
                {scanNote}
              </span>
            )}
          </p>
        )}
        {error && <p className="scan-error">{error}</p>}

        {!scanning && scanned && visible.length === 0 && (
          <p className="scan-status">
            {t("manualScan.nothingToReview")}
          </p>
        )}

        {visible.length > 0 && (
          <section className="scan-results" aria-label={t("manualScan.suggestedVenues")}>
            <h2 className="scan-results-title">
              {t("manualScan.forReview")}
              <span className="scan-results-count">{visible.length}</span>
            </h2>
            <p className="scan-results-note">
              {t("manualScan.reviewNote")}
            </p>
            {anyYear
              ? yearGroups.map(([year, items]) => (
                  <div className="scan-year-group" key={year || "unknown"}>
                    <h3 className="scan-year-heading">
                      {year || t("manualScan.yearUnknown")}
                    </h3>
                    {items.map(renderCard)}
                  </div>
                ))
              : visible.map(renderCard)}
          </section>
        )}
      </main>
    </div>
  );
}
