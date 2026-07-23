import { useEffect, useState } from "react";
import {
  clearStaleDates,
  fetchResearchRuns,
  type StaleDatesReset,
} from "./api";
import type { ResearchFinding, ResearchRun } from "./types";
import "./ResearchDialog.css";

const FIELD_LABELS: Record<string, string> = {
  website: "Website",
  contact_email: "Contact email",
  booking_contact: "Booking contact",
  application_method: "How to apply",
  application_url: "Application link",
  application_deadline: "Application deadline",
  event_dates: "Event dates",
  note: "Note",
};

/** Deadlines travel as "YYYY-MM"; show just the month — the season is 2027. */
function formatValue(finding: ResearchFinding): string {
  if (
    finding.field === "application_deadline" &&
    /^\d{4}-\d{2}$/.test(finding.new_value)
  ) {
    return new Date(`${finding.new_value}-01`).toLocaleDateString(undefined, {
      month: "long",
    });
  }
  return finding.new_value;
}

function formatStarted(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Findings grouped by venue, in first-seen order. */
function byVenue(findings: ResearchFinding[]): [string, ResearchFinding[]][] {
  const groups = new Map<string, ResearchFinding[]>();
  for (const finding of findings) {
    const list = groups.get(finding.venue_name) ?? [];
    list.push(finding);
    groups.set(finding.venue_name, list);
  }
  return [...groups.entries()];
}

function FindingsList({ findings }: { findings: ResearchFinding[] }) {
  if (findings.length === 0) {
    return (
      <p className="research-empty">
        Nothing new was found for these venues this time.
      </p>
    );
  }
  return (
    <>
      {byVenue(findings).map(([venueName, list]) => (
        <section className="research-venue" key={venueName}>
          <h3 className="research-venue-name">{venueName}</h3>
          <ul className="research-findings">
            {list.map((finding) => (
              <li className="research-finding" key={finding.id}>
                <span
                  className={`conf-dot conf-${finding.confidence}`}
                  title={
                    finding.confidence === "high"
                      ? "High confidence — published or official"
                      : "Medium confidence — derived from past editions"
                  }
                />
                <span className="research-field">
                  {FIELD_LABELS[finding.field] ?? finding.field}
                </span>
                <span className="research-value">
                  {formatValue(finding)}
                  {finding.old_value &&
                    finding.applied &&
                    finding.field !== "note" && (
                      <span className="research-old">
                        {" "}
                        (was {finding.old_value})
                      </span>
                    )}
                </span>
                {!finding.applied && (
                  <span
                    className="research-kept"
                    title="You entered this field yourself, so the found value was not applied — it is only shown here for review."
                  >
                    kept yours
                  </span>
                )}
                {finding.source && (
                  <a
                    className="research-source"
                    href={finding.source}
                    target="_blank"
                    rel="noreferrer"
                  >
                    source
                  </a>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}

interface ResearchDialogProps {
  /** The run being followed (App owns the polling); null while it starts. */
  run: ResearchRun | null;
  error: string | null;
  onClose: () => void;
  /** The run and the cleanup both write venue fields; the board reloads here. */
  onVenuesChanged: () => void;
}

export default function ResearchDialog({
  run,
  error,
  onClose,
  onVenuesChanged,
}: ResearchDialogProps) {
  const [pastRuns, setPastRuns] = useState<ResearchRun[]>([]);
  const [openPastId, setOpenPastId] = useState<number | null>(null);
  const [cleanup, setCleanup] = useState<"idle" | "confirm" | "working">("idle");
  const [cleanupResult, setCleanupResult] = useState<StaleDatesReset | null>(
    null,
  );
  const [cleanupError, setCleanupError] = useState<string | null>(null);

  const running = run !== null && run.status === "running";

  // Refresh the "Earlier searches" list on open and whenever the current run
  // reaches a terminal state (so the just-finished run drops into history).
  useEffect(() => {
    let cancelled = false;
    fetchResearchRuns()
      .then((runs) => {
        if (!cancelled) setPastRuns(runs.filter((r) => r.id !== run?.id));
      })
      .catch(() => {
        // Past runs are a convenience; the current result still shows.
      });
    return () => {
      cancelled = true;
    };
  }, [run?.id, run?.status]);

  const runCleanup = async () => {
    setCleanup("working");
    setCleanupError(null);
    try {
      const result = await clearStaleDates();
      setCleanupResult(result);
      setCleanup("idle");
      if (result.cleared > 0) onVenuesChanged();
    } catch (err) {
      setCleanupError(
        err instanceof Error ? err.message : "Something went wrong",
      );
      setCleanup("idle");
    }
  };

  return (
    <div
      className="research-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget && !running) {
          onClose();
        }
      }}
    >
      <div
        className="research-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Search and fill venue information"
      >
        <header className="research-header">
          <div>
            <p className="research-overline">Season 2027</p>
            <h2 className="research-title">Search &amp; fill</h2>
          </div>
          <button className="research-close" onClick={onClose}>
            {running ? "Close (keeps searching)" : "Close"}
          </button>
        </header>

        <div className="research-body">
          {run === null && !error && (
            <p className="research-status">Starting the search…</p>
          )}

          {running && (
            <p className="research-status">
              Claude is researching the venues most in need of information —
              this can take a few minutes.
              {run.note && (
                <span className="research-note">
                  <br />
                  {run.note}
                </span>
              )}
            </p>
          )}

          {error && <p className="research-error">{error}</p>}

          {run?.status === "failed" && (
            <p className="research-error">
              {run.error ?? "The search failed — try again."}
            </p>
          )}

          {run?.status === "completed" && (
            <>
              {run.summary && (
                <p className="research-summary">{run.summary}</p>
              )}
              {run.venues_checked > 0 && (
                <FindingsList findings={run.findings} />
              )}
              {run.findings.length > 0 && (
                <p className="research-legend">
                  <span className="conf-dot conf-high" /> published or official
                  <span className="conf-dot conf-medium" /> derived from past
                  editions
                </p>
              )}
            </>
          )}

          {pastRuns.length > 0 && (
            <section className="research-past">
              <h3 className="research-past-title">Earlier searches</h3>
              {pastRuns.map((past) => (
                <div className="research-past-run" key={past.id}>
                  <button
                    className="research-past-toggle"
                    onClick={() =>
                      setOpenPastId((id) => (id === past.id ? null : past.id))
                    }
                  >
                    <span className="research-past-date">
                      {formatStarted(past.started_at)}
                    </span>
                    <span className="research-past-summary">
                      {past.status === "failed"
                        ? (past.error ?? "Failed")
                        : (past.summary ?? "…")}
                    </span>
                  </button>
                  {openPastId === past.id && past.status !== "failed" && (
                    <FindingsList findings={past.findings} />
                  )}
                </div>
              ))}
            </section>
          )}

          {!running && (
            <section className="research-cleanup">
              <h3 className="research-past-title">Fix past-edition dates</h3>
              <p className="research-cleanup-note">
                Clear dates Claude filled from a 2026 (or earlier) edition and
                send those cards back to Discovered for the 2027 season.
                Anything you entered by hand is left untouched.
              </p>
              {cleanup === "confirm" ? (
                <div className="research-cleanup-confirm">
                  <span>Clear all past-edition dates Claude filled?</span>
                  <button className="research-cleanup-go" onClick={runCleanup}>
                    Clear
                  </button>
                  <button
                    className="research-cleanup-cancel"
                    onClick={() => setCleanup("idle")}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  className="research-cleanup-button"
                  disabled={cleanup === "working"}
                  onClick={() => {
                    setCleanupResult(null);
                    setCleanup("confirm");
                  }}
                >
                  {cleanup === "working"
                    ? "Clearing…"
                    : "Clear Claude’s past-edition dates"}
                </button>
              )}
              {cleanupResult && (
                <p className="research-cleanup-result">
                  {cleanupResult.cleared === 0
                    ? "No past-edition dates to clear."
                    : `Cleared dates on ${cleanupResult.cleared} venue${
                        cleanupResult.cleared === 1 ? "" : "s"
                      }, moved to Discovered: ${cleanupResult.venues.join(", ")}.`}
                </p>
              )}
              {cleanupError && <p className="research-error">{cleanupError}</p>}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
