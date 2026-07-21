import { FormEvent, useState } from "react";
import {
  UnauthorizedError,
  createVenue,
  deleteVenue,
  updateVenue,
} from "./api";
import {
  STATUS_LABELS,
  TYPE_LABELS,
  VENUE_STATUSES,
  VENUE_TYPES,
  type Venue,
  type VenueInput,
  type VenueStatus,
  type VenueType,
} from "./types";
import "./VenueSheet.css";

interface FormState {
  name: string;
  type: VenueType;
  status: VenueStatus;
  city: string;
  country: string;
  fit_score: string;
  booking_contact: string;
  contact_email: string;
  application_method: string;
  application_url: string;
  application_deadline: string;
  event_dates: string;
  website: string;
  research_notes: string;
  last_contact: string;
  next_action: string;
  source: string;
}

function initForm(venue: Venue | null): FormState {
  return {
    name: venue?.name ?? "",
    type: venue?.type ?? "venue",
    status: venue?.status ?? "discovered",
    city: venue?.city ?? "",
    country: venue?.country ?? "",
    fit_score: venue?.fit_score != null ? String(venue.fit_score) : "",
    booking_contact: venue?.booking_contact ?? "",
    contact_email: venue?.contact_email ?? "",
    application_method: venue?.application_method ?? "",
    application_url: venue?.application_url ?? "",
    application_deadline: venue?.application_deadline ?? "",
    event_dates: venue?.event_dates ?? "",
    website: venue?.website ?? "",
    research_notes: venue?.research_notes ?? "",
    last_contact: venue?.last_contact ?? "",
    next_action: venue?.next_action ?? "",
    source: venue?.source ?? "",
  };
}

function toPayload(form: FormState): VenueInput {
  const text = (value: string) => value.trim() || null;
  const score = form.fit_score.trim();
  return {
    name: form.name.trim(),
    type: form.type,
    status: form.status,
    city: text(form.city),
    country: text(form.country),
    fit_score: score && !Number.isNaN(Number(score)) ? Number(score) : null,
    booking_contact: text(form.booking_contact),
    contact_email: text(form.contact_email),
    application_method: text(form.application_method),
    application_url: text(form.application_url),
    application_deadline: text(form.application_deadline),
    event_dates: text(form.event_dates),
    website: text(form.website),
    research_notes: text(form.research_notes),
    last_contact: text(form.last_contact),
    next_action: text(form.next_action),
    source: text(form.source),
  };
}

interface VenueSheetProps {
  venue: Venue | null; // null → new venue
  onClose: () => void;
  onSaved: () => void;
}

export default function VenueSheet({ venue, onClose, onSaved }: VenueSheetProps) {
  const [form, setForm] = useState<FormState>(() => initForm(venue));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  function set<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function fail(err: unknown) {
    if (err instanceof UnauthorizedError) {
      setError("Your session expired — reload the page and sign in again.");
    } else {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
    setBusy(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload = toPayload(form);
      if (venue) {
        await updateVenue(venue.id, payload);
      } else {
        await createVenue(payload);
      }
      onSaved();
    } catch (err) {
      fail(err);
    }
  }

  async function removeVenue() {
    if (!venue) return;
    setBusy(true);
    setError(null);
    try {
      await deleteVenue(venue.id);
      onSaved();
    } catch (err) {
      fail(err);
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <section
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={venue ? venue.name : "New venue"}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="sheet-header">
          <div>
            <p className="sheet-overline">{venue ? "Venue" : "New venue"}</p>
            <h2 className="sheet-title">{venue ? venue.name : "Add a venue"}</h2>
          </div>
          <button type="button" className="sheet-close" onClick={onClose}>
            Close
          </button>
        </header>

        <form className="sheet-form" onSubmit={submit}>
          <fieldset className="sheet-section">
            <legend className="sheet-legend">Essentials</legend>
            <div className="sheet-grid">
              <label className="field field-wide">
                <span>Name</span>
                <input
                  value={form.name}
                  onChange={(e) => set("name", e.target.value)}
                  required
                  autoFocus={!venue}
                />
              </label>
              <label className="field">
                <span>Type</span>
                <select
                  value={form.type}
                  onChange={(e) => set("type", e.target.value as VenueType)}
                >
                  {VENUE_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {TYPE_LABELS[type]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Status</span>
                <select
                  value={form.status}
                  onChange={(e) => set("status", e.target.value as VenueStatus)}
                >
                  {VENUE_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {STATUS_LABELS[status]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>City</span>
                <input
                  value={form.city}
                  onChange={(e) => set("city", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Country</span>
                <input
                  value={form.country}
                  onChange={(e) => set("country", e.target.value)}
                />
              </label>
            </div>
          </fieldset>

          <fieldset className="sheet-section">
            <legend className="sheet-legend">Application</legend>
            <div className="sheet-grid">
              <label className="field">
                <span>Application deadline</span>
                <input
                  type="date"
                  value={form.application_deadline}
                  onChange={(e) => set("application_deadline", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Event dates</span>
                <input
                  value={form.event_dates}
                  onChange={(e) => set("event_dates", e.target.value)}
                  placeholder="e.g. 12–14 July"
                />
              </label>
              <label className="field">
                <span>How to apply</span>
                <input
                  value={form.application_method}
                  onChange={(e) => set("application_method", e.target.value)}
                  placeholder="email, form…"
                />
              </label>
              <label className="field">
                <span>Application link</span>
                <input
                  value={form.application_url}
                  onChange={(e) => set("application_url", e.target.value)}
                  inputMode="url"
                />
              </label>
            </div>
          </fieldset>

          <fieldset className="sheet-section">
            <legend className="sheet-legend">Contact</legend>
            <div className="sheet-grid">
              <label className="field">
                <span>Programmer / contact</span>
                <input
                  value={form.booking_contact}
                  onChange={(e) => set("booking_contact", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Email</span>
                <input
                  value={form.contact_email}
                  onChange={(e) => set("contact_email", e.target.value)}
                  inputMode="email"
                />
              </label>
              <label className="field field-wide">
                <span>Website</span>
                <input
                  value={form.website}
                  onChange={(e) => set("website", e.target.value)}
                  inputMode="url"
                />
              </label>
            </div>
          </fieldset>

          <fieldset className="sheet-section">
            <legend className="sheet-legend">Notes</legend>
            <div className="sheet-grid">
              <label className="field field-wide">
                <span>Research notes</span>
                <textarea
                  value={form.research_notes}
                  onChange={(e) => set("research_notes", e.target.value)}
                  rows={4}
                />
              </label>
              <label className="field field-wide">
                <span>Next action</span>
                <input
                  value={form.next_action}
                  onChange={(e) => set("next_action", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Last contact</span>
                <input
                  type="date"
                  value={form.last_contact}
                  onChange={(e) => set("last_contact", e.target.value)}
                />
              </label>
              <label className="field">
                <span>Fit (0–5)</span>
                <input
                  type="number"
                  min={0}
                  max={5}
                  step={0.5}
                  value={form.fit_score}
                  onChange={(e) => set("fit_score", e.target.value)}
                />
              </label>
              <label className="field field-wide">
                <span>Source</span>
                <input
                  value={form.source}
                  onChange={(e) => set("source", e.target.value)}
                  placeholder="how you found this venue"
                />
              </label>
            </div>
          </fieldset>

          {error && <p className="sheet-error">{error}</p>}

          <div className="sheet-actions">
            <button type="submit" className="sheet-save" disabled={busy}>
              {busy ? "Saving…" : venue ? "Save changes" : "Add venue"}
            </button>
            {venue && !confirmingDelete && (
              <button
                type="button"
                className="sheet-delete"
                onClick={() => setConfirmingDelete(true)}
              >
                Delete venue
              </button>
            )}
            {venue && confirmingDelete && (
              <div className="sheet-confirm">
                <span>Delete this venue for good?</span>
                <button
                  type="button"
                  className="sheet-delete sheet-delete-confirm"
                  onClick={removeVenue}
                  disabled={busy}
                >
                  Delete
                </button>
                <button
                  type="button"
                  className="sheet-keep"
                  onClick={() => setConfirmingDelete(false)}
                >
                  Keep
                </button>
              </div>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}
