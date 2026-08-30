import { FormEvent, useEffect, useState } from "react";
import { UnauthorizedError, fetchBandProfile, updateBandProfile } from "./api";
import { useT } from "./i18n";
import "./VenueSheet.css";
import "./DraftPanel.css";

interface BandProfileSheetProps {
  onClose: () => void;
  onUnauthorized: () => void;
}

interface FormState {
  band_name: string;
  signature_name: string;
  phone: string;
  email: string;
  website: string;
  instagram: string;
  video1_url: string;
  video2_url: string;
  epk_url: string;
}

const EMPTY_FORM: FormState = {
  band_name: "",
  signature_name: "",
  phone: "",
  email: "",
  website: "",
  instagram: "",
  video1_url: "",
  video2_url: "",
  epk_url: "",
};

export default function BandProfileSheet({
  onClose,
  onUnauthorized,
}: BandProfileSheetProps) {
  const t = useT();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // The two editable bodies, and the current defaults for "reset".
  const [templateFr, setTemplateFr] = useState("");
  const [templateEn, setTemplateEn] = useState("");
  const [defaultFr, setDefaultFr] = useState("");
  const [defaultEn, setDefaultEn] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function fail(err: unknown) {
    if (err instanceof UnauthorizedError) onUnauthorized();
    else setError(err instanceof Error ? err.message : t("bandProfile.errorFallback"));
    setBusy(false);
  }

  useEffect(() => {
    let cancelled = false;
    fetchBandProfile()
      .then((profile) => {
        if (cancelled) return;
        setForm({
          band_name: profile.band_name ?? "",
          signature_name: profile.signature_name ?? "",
          phone: profile.phone ?? "",
          email: profile.email ?? "",
          website: profile.website ?? "",
          instagram: profile.instagram ?? "",
          video1_url: profile.video1_url ?? "",
          video2_url: profile.video2_url ?? "",
          epk_url: profile.epk_url ?? "",
        });
        setDefaultFr(profile.default_template_fr);
        setDefaultEn(profile.default_template_en);
        // Show the band's own body, or the default when it still tracks it.
        setTemplateFr(profile.template_fr ?? profile.default_template_fr);
        setTemplateEn(profile.template_en ?? profile.default_template_en);
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

  function set<K extends keyof FormState>(field: K, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setSaved(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const text = (value: string) => value.trim() || null;
    // Store null (track the default) when the body is unchanged from it.
    const templatePatch = (value: string, base: string) =>
      value.trim() === base.trim() ? null : value;
    try {
      await updateBandProfile({
        band_name: form.band_name.trim(),
        signature_name: form.signature_name.trim(),
        phone: text(form.phone),
        email: text(form.email),
        website: text(form.website),
        instagram: text(form.instagram),
        video1_url: text(form.video1_url),
        video2_url: text(form.video2_url),
        epk_url: text(form.epk_url),
        template_fr: templatePatch(templateFr, defaultFr),
        template_en: templatePatch(templateEn, defaultEn),
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
        aria-label={t("bandProfile.ariaLabel")}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="sheet-header">
          <div>
            <p className="sheet-overline">{t("bandProfile.overline")}</p>
            <h2 className="sheet-title">{t("bandProfile.title")}</h2>
          </div>
          <button type="button" className="sheet-close" onClick={onClose}>
            {t("common.close")}
          </button>
        </header>

        {loading ? (
          <p className="sheet-error" style={{ color: "var(--ink-soft)" }}>
            {t("bandProfile.loading")}
          </p>
        ) : (
          <form className="sheet-form" onSubmit={submit}>
            <p className="draft-verify" style={{ margin: "0 0 0.5rem" }}>
              {t("bandProfile.intro")}
            </p>
            <fieldset className="sheet-section">
              <legend className="sheet-legend">
                {t("bandProfile.signatureLegend")}
              </legend>
              <div className="sheet-grid">
                <label className="field">
                  <span>{t("bandProfile.bandName")}</span>
                  <input
                    value={form.band_name}
                    onChange={(e) => set("band_name", e.target.value)}
                    required
                  />
                </label>
                <label className="field">
                  <span>{t("bandProfile.signedBy")}</span>
                  <input
                    value={form.signature_name}
                    onChange={(e) => set("signature_name", e.target.value)}
                    required
                  />
                </label>
                <label className="field">
                  <span>{t("bandProfile.phone")}</span>
                  <input
                    value={form.phone}
                    onChange={(e) => set("phone", e.target.value)}
                  />
                </label>
                <label className="field">
                  <span>{t("bandProfile.email")}</span>
                  <input
                    value={form.email}
                    onChange={(e) => set("email", e.target.value)}
                    inputMode="email"
                  />
                </label>
                <label className="field">
                  <span>{t("bandProfile.instagram")}</span>
                  <input
                    value={form.instagram}
                    onChange={(e) => set("instagram", e.target.value)}
                    placeholder="@…"
                  />
                </label>
                <label className="field">
                  <span>{t("bandProfile.website")}</span>
                  <input
                    value={form.website}
                    onChange={(e) => set("website", e.target.value)}
                    inputMode="url"
                  />
                </label>
              </div>
            </fieldset>

            <fieldset className="sheet-section">
              <legend className="sheet-legend">
                {t("bandProfile.linksLegend")}
              </legend>
              <div className="sheet-grid">
                <label className="field field-wide">
                  <span>{t("bandProfile.video1")}</span>
                  <input
                    value={form.video1_url}
                    onChange={(e) => set("video1_url", e.target.value)}
                    inputMode="url"
                    placeholder="https://…"
                  />
                </label>
                <label className="field field-wide">
                  <span>{t("bandProfile.video2")}</span>
                  <input
                    value={form.video2_url}
                    onChange={(e) => set("video2_url", e.target.value)}
                    inputMode="url"
                    placeholder="https://…"
                  />
                </label>
                <label className="field field-wide">
                  <span>{t("bandProfile.epkLink")}</span>
                  <input
                    value={form.epk_url}
                    onChange={(e) => set("epk_url", e.target.value)}
                    inputMode="url"
                    placeholder="https://…"
                  />
                </label>
              </div>
            </fieldset>

            <fieldset className="sheet-section">
              <legend className="sheet-legend">
                {t("bandProfile.templateLegend")}
              </legend>
              <p className="draft-source" style={{ margin: "0 0 0.6rem" }}>
                {t("bandProfile.templateHint")}
              </p>
              <label className="field field-wide">
                <span className="band-template-head">
                  {t("bandProfile.templateFr")}
                  <button
                    type="button"
                    className="band-template-reset"
                    onClick={() => {
                      setTemplateFr(defaultFr);
                      setSaved(false);
                    }}
                    disabled={templateFr.trim() === defaultFr.trim()}
                  >
                    {t("bandProfile.resetDefault")}
                  </button>
                </span>
                <textarea
                  className="draft-body"
                  rows={16}
                  value={templateFr}
                  onChange={(e) => {
                    setTemplateFr(e.target.value);
                    setSaved(false);
                  }}
                />
              </label>
              <label className="field field-wide">
                <span className="band-template-head">
                  {t("bandProfile.templateEn")}
                  <button
                    type="button"
                    className="band-template-reset"
                    onClick={() => {
                      setTemplateEn(defaultEn);
                      setSaved(false);
                    }}
                    disabled={templateEn.trim() === defaultEn.trim()}
                  >
                    {t("bandProfile.resetDefault")}
                  </button>
                </span>
                <textarea
                  className="draft-body"
                  rows={16}
                  value={templateEn}
                  onChange={(e) => {
                    setTemplateEn(e.target.value);
                    setSaved(false);
                  }}
                />
              </label>
            </fieldset>

            {error && <p className="sheet-error">{error}</p>}

            <div className="sheet-actions">
              <button type="submit" className="sheet-save" disabled={busy}>
                {busy
                  ? t("common.saving")
                  : saved
                    ? t("bandProfile.saved")
                    : t("bandProfile.saveProfile")}
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
