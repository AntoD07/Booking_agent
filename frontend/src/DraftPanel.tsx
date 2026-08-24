import { useEffect, useMemo, useState } from "react";
import {
  UnauthorizedError,
  deleteDraft,
  fetchDrafts,
  generateDraft,
  updateDraft,
} from "./api";
import { type DraftStatus, type EmailDraft } from "./types";
import { useT } from "./i18n";
import "./DraftPanel.css";

interface DraftPanelProps {
  venueId: number;
  /** Prefilled as the recipient of the "Open in email" link, if known. */
  contactEmail: string | null;
  /** Generating or sending moves the card; let the board reload. */
  onVenueChanged: () => void;
  onUnauthorized: () => void;
}

function formatCreated(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DraftPanel({
  venueId,
  contactEmail,
  onVenueChanged,
  onUnauthorized,
}: DraftPanelProps) {
  const t = useT();
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const active = useMemo(
    () => drafts.find((d) => d.id === activeId) ?? null,
    [drafts, activeId],
  );
  const dirty =
    active !== null && (subject !== active.subject || body !== active.body);

  function fail(err: unknown) {
    if (err instanceof UnauthorizedError) {
      onUnauthorized();
    } else {
      setError(err instanceof Error ? err.message : t("draftPanel.errorGeneric"));
    }
    setBusy(false);
  }

  function select(draft: EmailDraft) {
    setActiveId(draft.id);
    setSubject(draft.subject);
    setBody(draft.body);
    setError(null);
    setCopied(false);
  }

  useEffect(() => {
    let cancelled = false;
    fetchDrafts(venueId)
      .then((list) => {
        if (cancelled) return;
        setDrafts(list);
        if (list.length > 0) select(list[0]);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoading(false);
        fail(err);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [venueId]);

  async function generate() {
    setBusy(true);
    setGenerating(true);
    setError(null);
    try {
      const draft = await generateDraft(venueId);
      setDrafts((current) => [draft, ...current]);
      select(draft);
      setBusy(false);
      setGenerating(false);
      onVenueChanged();
    } catch (err) {
      setGenerating(false);
      fail(err);
    }
  }

  async function save() {
    if (!active || !dirty) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateDraft(active.id, { subject, body });
      setDrafts((current) =>
        current.map((d) => (d.id === updated.id ? updated : d)),
      );
      setBusy(false);
    } catch (err) {
      fail(err);
    }
  }

  async function setStatus(status: DraftStatus) {
    if (!active) return;
    setBusy(true);
    setError(null);
    try {
      // Persist any pending edits along with the status change.
      const updated = await updateDraft(active.id, {
        status,
        ...(dirty ? { subject, body } : {}),
      });
      setDrafts((current) =>
        current.map((d) => (d.id === updated.id ? updated : d)),
      );
      setBusy(false);
      if (status === "sent") onVenueChanged();
    } catch (err) {
      fail(err);
    }
  }

  async function remove() {
    if (!active) return;
    setBusy(true);
    setError(null);
    try {
      await deleteDraft(active.id);
      const remaining = drafts.filter((d) => d.id !== active.id);
      setDrafts(remaining);
      if (remaining.length > 0) select(remaining[0]);
      else {
        setActiveId(null);
        setSubject("");
        setBody("");
      }
      setBusy(false);
    } catch (err) {
      fail(err);
    }
  }

  function openInEmail() {
    // A mailto: link hands the draft to whatever mail app/website the user has
    // set as their handler, recipient/subject/body prefilled. Nothing is sent
    // until they hit send there — they still "Mark sent" here afterwards.
    const params = new URLSearchParams({ subject, body });
    const to = contactEmail ? encodeURIComponent(contactEmail) : "";
    // URLSearchParams uses "+" for spaces; mail clients want %20.
    const query = params.toString().replace(/\+/g, "%20");
    window.location.href = `mailto:${to}?${query}`;
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(`${subject}\n\n${body}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError(t("draftPanel.copyError"));
    }
  }

  return (
    <section className="draft-panel" aria-label={t("draftPanel.ariaLabel")}>
      <h3 className="sheet-legend">{t("draftPanel.heading")}</h3>

      {loading ? (
        <p className="draft-empty">{t("draftPanel.loading")}</p>
      ) : (
        <>
          {drafts.length === 0 && (
            <p className="draft-empty">{t("draftPanel.emptyState")}</p>
          )}

          {drafts.length > 1 && (
            <div className="draft-tabs">
              {drafts.map((draft) => (
                <button
                  type="button"
                  key={draft.id}
                  className={`draft-tab${
                    draft.id === activeId ? " draft-tab--active" : ""
                  }`}
                  onClick={() => select(draft)}
                >
                  {formatCreated(draft.created_at)}
                  <span className={`draft-tab-status draft-status--${draft.status}`}>
                    {t(`draftStatus.${draft.status}`)}
                  </span>
                </button>
              ))}
            </div>
          )}

          {active && (
            <div className="draft-editor">
              <p className="draft-verify">{t("draftPanel.verifyNotice")}</p>
              {active.source && (
                <p className="draft-source">
                  {t("draftPanel.sourcePrefix")}{" "}
                  <a href={active.source} target="_blank" rel="noreferrer">
                    {t("draftPanel.sourceLink")}
                  </a>{" "}
                  {t("draftPanel.sourceSuffix")}
                </p>
              )}
              <label className="field field-wide">
                <span>{t("draftPanel.subjectLabel")}</span>
                <input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </label>
              <label className="field field-wide">
                <span>{t("draftPanel.bodyLabel")}</span>
                <textarea
                  className="draft-body"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={18}
                />
              </label>

              <div className="draft-status-row">
                <span className="draft-status-label">
                  {t("draftPanel.statusLabel")} {t(`draftStatus.${active.status}`)}
                </span>
                {active.status !== "approved" && active.status !== "sent" && (
                  <button
                    type="button"
                    className="draft-btn"
                    disabled={busy}
                    onClick={() => setStatus("approved")}
                  >
                    {t("draftPanel.markApproved")}
                  </button>
                )}
                {active.status !== "sent" && (
                  <button
                    type="button"
                    className="draft-btn"
                    disabled={busy}
                    onClick={() => setStatus("sent")}
                    title={t("draftPanel.markSentTitle")}
                  >
                    {t("draftPanel.markSent")}
                  </button>
                )}
              </div>
            </div>
          )}

          {error && <p className="sheet-error">{error}</p>}

          <div className="draft-actions">
            <button
              type="button"
              className="draft-generate"
              disabled={busy}
              onClick={generate}
            >
              {generating
                ? t("draftPanel.generating")
                : busy
                  ? t("draftPanel.working")
                  : drafts.length === 0
                    ? t("draftPanel.draftEmail")
                    : t("draftPanel.draftAnother")}
            </button>
            {active && (
              <>
                <button
                  type="button"
                  className="draft-btn"
                  disabled={busy || !dirty}
                  onClick={save}
                >
                  {dirty ? t("draftPanel.saveChanges") : t("draftPanel.saved")}
                </button>
                <button
                  type="button"
                  className="draft-open-email"
                  onClick={openInEmail}
                  title={
                    contactEmail
                      ? t("draftPanel.openEmailTitleTo", { email: contactEmail })
                      : t("draftPanel.openEmailTitleNoContact")
                  }
                >
                  {t("draftPanel.openInEmail")}
                </button>
                <button
                  type="button"
                  className="draft-btn"
                  disabled={busy}
                  onClick={copy}
                  title={t("draftPanel.copyTitle")}
                >
                  {copied ? t("draftPanel.copied") : t("draftPanel.copy")}
                </button>
                <button
                  type="button"
                  className="draft-delete"
                  disabled={busy}
                  onClick={remove}
                >
                  {t("common.delete")}
                </button>
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}
