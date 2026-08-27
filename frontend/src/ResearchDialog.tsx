import { useEffect, useState } from "react";
import {
  clearStaleDates,
  fetchResearchRuns,
  type StaleDatesReset,
} from "./api";
import type { ResearchFinding, ResearchRun } from "./types";
import { useI18n, type Lang } from "./i18n";
import "./ResearchDialog.css";

const FIELD_KEYS: Record<string, string> = {
  website: "researchDialog.field.website",
  contact_email: "researchDialog.field.contactEmail",
  booking_contact: "researchDialog.field.bookingContact",
  application_method: "researchDialog.field.applicationMethod",
  application_url: "researchDialog.field.applicationUrl",
  application_deadline: "researchDialog.field.applicationDeadline",
  event_dates: "researchDialog.field.eventDates",
  artist: "researchDialog.field.artist",
  note: "researchDialog.field.note",
};

function fieldLabel(field: string, t: (key: string) => string): string {
  const key = FIELD_KEYS[field];
  return key ? t(key) : field;
}

/** Deadlines travel as "YYYY-MM"; show just the month — the season is 2027. */
function formatValue(finding: ResearchFinding, lang: Lang): string {
  if (
    finding.field === "application_deadline" &&
    /^\d{4}-\d{2}$/.test(finding.new_value)
  ) {
    return new Date(`${finding.new_value}-01`).toLocaleDateString(lang, {
      month: "long",
    });
  }
  return finding.new_value;
}

function formatStarted(iso: string, lang: Lang): string {
  return new Date(iso).toLocaleDateString(lang, {
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
  const { t, lang } = useI18n();
  if (findings.length === 0) {
    return <p className="research-empty">{t("researchDialog.empty")}</p>;
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
                      ? t("researchDialog.confHigh")
                      : t("researchDialog.confMedium")
                  }
                />
                {finding.source && (
                  <a
                    className="research-source"
                    href={finding.source}
                    target="_blank"
                    rel="noreferrer"
                    title={t("researchDialog.sourceTitle")}
                  >
                    {t("researchDialog.sourceLink")}
                  </a>
                )}
                <span className="research-field">
                  {fieldLabel(finding.field, t)}
                </span>
                <span className="research-value">
                  {formatValue(finding, lang)}
                  {finding.old_value &&
                    finding.applied &&
                    finding.field !== "note" && (
                      <span className="research-old">
                        {" "}
                        {t("researchDialog.wasValue", {
                          value: finding.old_value,
                        })}
                      </span>
                    )}
                </span>
                {!finding.applied && (
                  <span
                    className="research-kept"
                    title={t("researchDialog.keptTitle")}
                  >
                    {t("researchDialog.keptYours")}
                  </span>
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
  const { t, lang } = useI18n();
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
        err instanceof Error ? err.message : t("researchDialog.genericError"),
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
        aria-label={t("researchDialog.ariaLabel")}
      >
        <header className="research-header">
          <div>
            <p className="research-overline">{t("researchDialog.overline")}</p>
            <h2 className="research-title">{t("researchDialog.title")}</h2>
          </div>
          <button className="research-close" onClick={onClose}>
            {running ? t("researchDialog.closeKeepSearching") : t("common.close")}
          </button>
        </header>

        <div className="research-body">
          {run === null && !error && (
            <p className="research-status">{t("researchDialog.starting")}</p>
          )}

          {running && (
            <p className="research-status">
              {t("researchDialog.running")}
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
              {run.error ?? t("researchDialog.failed")}
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
                  <span className="conf-dot conf-high" />{" "}
                  {t("researchDialog.legendHigh")}
                  <span className="conf-dot conf-medium" />{" "}
                  {t("researchDialog.legendMedium")}
                </p>
              )}
            </>
          )}

          {pastRuns.length > 0 && (
            <section className="research-past">
              <h3 className="research-past-title">
                {t("researchDialog.earlierSearches")}
              </h3>
              {pastRuns.map((past) => (
                <div className="research-past-run" key={past.id}>
                  <button
                    className="research-past-toggle"
                    onClick={() =>
                      setOpenPastId((id) => (id === past.id ? null : past.id))
                    }
                  >
                    <span className="research-past-date">
                      {formatStarted(past.started_at, lang)}
                    </span>
                    <span className="research-past-summary">
                      {past.status === "failed"
                        ? (past.error ?? t("researchDialog.failedShort"))
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
              <h3 className="research-past-title">
                {t("researchDialog.fixPastDates")}
              </h3>
              <p className="research-cleanup-note">
                {t("researchDialog.cleanupNote")}
              </p>
              {cleanup === "confirm" ? (
                <div className="research-cleanup-confirm">
                  <span>{t("researchDialog.cleanupConfirm")}</span>
                  <button className="research-cleanup-go" onClick={runCleanup}>
                    {t("researchDialog.clear")}
                  </button>
                  <button
                    className="research-cleanup-cancel"
                    onClick={() => setCleanup("idle")}
                  >
                    {t("common.cancel")}
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
                    ? t("researchDialog.clearing")
                    : t("researchDialog.clearButton")}
                </button>
              )}
              {cleanupResult && (
                <p className="research-cleanup-result">
                  {cleanupResult.cleared === 0
                    ? t("researchDialog.nothingToClear")
                    : t(
                        cleanupResult.cleared === 1
                          ? "researchDialog.clearedOne"
                          : "researchDialog.clearedMany",
                        {
                          count: cleanupResult.cleared,
                          status: t("status.discovered"),
                          venues: cleanupResult.venues.join(", "),
                        },
                      )}
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
