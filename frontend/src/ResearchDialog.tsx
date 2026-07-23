import { useEffect, useRef, useState } from "react";
import {
  UnauthorizedError,
  fetchResearchRun,
  fetchResearchRuns,
  startResearch,
} from "./api";
import type { ResearchFinding, ResearchRun } from "./types";
import "./ResearchDialog.css";

const POLL_INTERVAL_MS = 4000;
// Server-side runs are capped at ten minutes; stop asking well after that.
const MAX_WAIT_MS = 12 * 60 * 1000;

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

/** Deadlines travel as "YYYY-MM"; show "January 2027" like the board does. */
function formatValue(finding: ResearchFinding): string {
  if (
    finding.field === "application_deadline" &&
    /^\d{4}-\d{2}$/.test(finding.new_value)
  ) {
    return new Date(`${finding.new_value}-01`).toLocaleDateString(undefined, {
      month: "long",
      year: "numeric",
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
  onClose: () => void;
  onUnauthorized: () => void;
  /** The run writes venue fields; the board reloads through this. */
  onVenuesChanged: () => void;
}

export default function ResearchDialog({
  onClose,
  onUnauthorized,
  onVenuesChanged,
}: ResearchDialogProps) {
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pastRuns, setPastRuns] = useState<ResearchRun[]>([]);
  const [openPastId, setOpenPastId] = useState<number | null>(null);
  // The board must reload at most once per completed run.
  const notified = useRef(false);

  useEffect(() => {
    let cancelled = false;

    const finish = async (finalRun: ResearchRun) => {
      if (!notified.current && finalRun.fields_filled > 0) {
        notified.current = true;
        onVenuesChanged();
      }
      try {
        const runs = await fetchResearchRuns();
        if (!cancelled) {
          setPastRuns(runs.filter((r) => r.id !== finalRun.id));
        }
      } catch {
        // Past runs are a convenience; the current result already shows.
      }
    };

    const poll = async () => {
      try {
        let current = await startResearch();
        if (cancelled) return;
        setRun(current);
        const startedAt = Date.now();
        while (current.status === "running") {
          await new Promise((resolve) =>
            setTimeout(resolve, POLL_INTERVAL_MS),
          );
          if (cancelled) return;
          current = await fetchResearchRun(current.id);
          if (cancelled) return;
          setRun(current);
          if (Date.now() - startedAt > MAX_WAIT_MS) {
            setError(
              "The search is taking unusually long. Close this box and check back in a few minutes.",
            );
            return;
          }
        }
        await finish(current);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof UnauthorizedError) {
          onUnauthorized();
        } else {
          setError(
            err instanceof Error ? err.message : "Something went wrong",
          );
        }
      }
    };

    poll();
    return () => {
      cancelled = true;
    };
    // Runs once: the dialog exists to drive exactly one research run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const running = run !== null && run.status === "running";

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
        </div>
      </div>
    </div>
  );
}
