import { useEffect, useMemo, useState } from "react";
import {
  UnauthorizedError,
  deleteDraft,
  fetchDrafts,
  generateDraft,
  updateDraft,
} from "./api";
import { DRAFT_STATUS_LABELS, type DraftStatus, type EmailDraft } from "./types";
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
      setError(err instanceof Error ? err.message : "Something went wrong");
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
      setError("Couldn’t copy — select the text and copy it by hand.");
    }
  }

  return (
    <section className="draft-panel" aria-label="Pitch draft">
      <h3 className="sheet-legend">Pitch draft</h3>

      {loading ? (
        <p className="draft-empty">Loading drafts…</p>
      ) : (
        <>
          {drafts.length === 0 && (
            <p className="draft-empty">
              No draft yet. Generate one from the band’s template — you’ll edit
              and check it before anything is sent.
            </p>
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
                    {DRAFT_STATUS_LABELS[draft.status]}
                  </span>
                </button>
              ))}
            </div>
          )}

          {active && (
            <div className="draft-editor">
              <p className="draft-verify">
                Check the opening line — it must name a real artist from this
                venue’s programme — then edit freely. The app never sends;
                copy the text into your mail client to send it yourself.
              </p>
              {active.source && (
                <p className="draft-source">
                  Opening line grounded in{" "}
                  <a href={active.source} target="_blank" rel="noreferrer">
                    this source
                  </a>{" "}
                  — confirm it before sending.
                </p>
              )}
              <label className="field field-wide">
                <span>Subject</span>
                <input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </label>
              <label className="field field-wide">
                <span>Body</span>
                <textarea
                  className="draft-body"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={18}
                />
              </label>

              <div className="draft-status-row">
                <span className="draft-status-label">
                  Status: {DRAFT_STATUS_LABELS[active.status]}
                </span>
                {active.status !== "approved" && active.status !== "sent" && (
                  <button
                    type="button"
                    className="draft-btn"
                    disabled={busy}
                    onClick={() => setStatus("approved")}
                  >
                    Mark approved
                  </button>
                )}
                {active.status !== "sent" && (
                  <button
                    type="button"
                    className="draft-btn"
                    disabled={busy}
                    onClick={() => setStatus("sent")}
                    title="Records that you sent this pitch and moves the card to Sent"
                  >
                    Mark sent
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
                ? "Searching their line-up…"
                : busy
                  ? "Working…"
                  : drafts.length === 0
                    ? "Draft email"
                    : "Draft another"}
            </button>
            {active && (
              <>
                <button
                  type="button"
                  className="draft-btn"
                  disabled={busy || !dirty}
                  onClick={save}
                >
                  {dirty ? "Save changes" : "Saved"}
                </button>
                <button
                  type="button"
                  className="draft-open-email"
                  onClick={openInEmail}
                  title={
                    contactEmail
                      ? `Open a new email to ${contactEmail}, prefilled`
                      : "Open a new prefilled email (add the recipient yourself)"
                  }
                >
                  Open in email
                </button>
                <button
                  type="button"
                  className="draft-btn"
                  disabled={busy}
                  onClick={copy}
                  title="Copy the subject and body to paste elsewhere"
                >
                  {copied ? "Copied" : "Copy"}
                </button>
                <button
                  type="button"
                  className="draft-delete"
                  disabled={busy}
                  onClick={remove}
                >
                  Delete
                </button>
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}
