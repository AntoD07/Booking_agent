import { FormEvent, useEffect, useState } from "react";
import { UnauthorizedError, fetchBandProfile, updateBandProfile } from "./api";
import type { BandProfile } from "./types";
import "./VenueSheet.css";
import "./DraftPanel.css";

interface BandProfileSheetProps {
  onClose: () => void;
  onUnauthorized: () => void;
}

const EMPTY: BandProfile = {
  band_name: "",
  signature_name: "",
  phone: "",
  email: "",
  website: "",
  video1_url: "",
  video2_url: "",
  epk_url: "",
};

export default function BandProfileSheet({
  onClose,
  onUnauthorized,
}: BandProfileSheetProps) {
  const [form, setForm] = useState<BandProfile>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function fail(err: unknown) {
    if (err instanceof UnauthorizedError) onUnauthorized();
    else setError(err instanceof Error ? err.message : "Something went wrong");
    setBusy(false);
  }

  useEffect(() => {
    let cancelled = false;
    fetchBandProfile()
      .then((profile) => {
        if (cancelled) return;
        // null → "" so inputs stay controlled.
        setForm({
          band_name: profile.band_name ?? "",
          signature_name: profile.signature_name ?? "",
          phone: profile.phone ?? "",
          email: profile.email ?? "",
          website: profile.website ?? "",
          video1_url: profile.video1_url ?? "",
          video2_url: profile.video2_url ?? "",
          epk_url: profile.epk_url ?? "",
        });
        setLoading(false);
      })
      .catch((err) => {
        if (!cancelled) {
          setLoading(false);
          fail(err);
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function set<K extends keyof BandProfile>(field: K, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setSaved(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const text = (value: string | null) => (value && value.trim()) || null;
    try {
      await updateBandProfile({
        band_name: form.band_name.trim(),
        signature_name: form.signature_name.trim(),
        phone: text(form.phone),
        email: text(form.email),
        website: text(form.website),
        video1_url: text(form.video1_url),
        video2_url: text(form.video2_url),
        epk_url: text(form.epk_url),
      });
      setBusy(false);
      setSaved(true);
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
        aria-label="Band profile"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="sheet-header">
          <div>
            <p className="sheet-overline">Pitch</p>
            <h2 className="sheet-title">Band profile</h2>
          </div>
          <button type="button" className="sheet-close" onClick={onClose}>
            Close
          </button>
        </header>

        {loading ? (
          <p className="sheet-error" style={{ color: "var(--ink-soft)" }}>
            Loading…
          </p>
        ) : (
          <form className="sheet-form" onSubmit={submit}>
            <p
              className="draft-verify"
              style={{ margin: "0 0 0.5rem" }}
            >
              These details fill every pitch. The band’s story and the album
              text are fixed in the template — here you set who signs, the
              contact line, and the video / EPK links.
            </p>
            <fieldset className="sheet-section">
              <legend className="sheet-legend">Signature</legend>
              <div className="sheet-grid">
                <label className="field">
                  <span>Band name</span>
                  <input
                    value={form.band_name}
                    onChange={(e) => set("band_name", e.target.value)}
                    required
                  />
                </label>
                <label className="field">
                  <span>Signed by</span>
                  <input
                    value={form.signature_name}
                    onChange={(e) => set("signature_name", e.target.value)}
                    required
                  />
                </label>
                <label className="field">
                  <span>Phone</span>
                  <input
                    value={form.phone ?? ""}
                    onChange={(e) => set("phone", e.target.value)}
                  />
                </label>
                <label className="field">
                  <span>Email</span>
                  <input
                    value={form.email ?? ""}
                    onChange={(e) => set("email", e.target.value)}
                    inputMode="email"
                  />
                </label>
                <label className="field field-wide">
                  <span>Website</span>
                  <input
                    value={form.website ?? ""}
                    onChange={(e) => set("website", e.target.value)}
                    inputMode="url"
                  />
                </label>
              </div>
            </fieldset>

            <fieldset className="sheet-section">
              <legend className="sheet-legend">Links</legend>
              <div className="sheet-grid">
                <label className="field field-wide">
                  <span>Live video 1</span>
                  <input
                    value={form.video1_url ?? ""}
                    onChange={(e) => set("video1_url", e.target.value)}
                    inputMode="url"
                    placeholder="https://…"
                  />
                </label>
                <label className="field field-wide">
                  <span>Live video 2</span>
                  <input
                    value={form.video2_url ?? ""}
                    onChange={(e) => set("video2_url", e.target.value)}
                    inputMode="url"
                    placeholder="https://…"
                  />
                </label>
                <label className="field field-wide">
                  <span>EPK link</span>
                  <input
                    value={form.epk_url ?? ""}
                    onChange={(e) => set("epk_url", e.target.value)}
                    inputMode="url"
                    placeholder="https://…"
                  />
                </label>
              </div>
            </fieldset>

            {error && <p className="sheet-error">{error}</p>}

            <div className="sheet-actions">
              <button type="submit" className="sheet-save" disabled={busy}>
                {busy ? "Saving…" : saved ? "Saved" : "Save profile"}
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
