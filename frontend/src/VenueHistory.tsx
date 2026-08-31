import { useEffect, useState } from "react";
import { UnauthorizedError, fetchVenueHistory } from "./api";
import { useI18n } from "./i18n";
import type { FieldChange, VenueEdit } from "./types";
import "./VenueHistory.css";

// Backend field name → the venueSheet.* label key already translated elsewhere.
const FIELD_KEY: Record<string, string> = {
  name: "name",
  type: "type",
  status: "status",
  city: "city",
  region: "region",
  country: "country",
  fit_score: "fit",
  booking_contact: "programmerContact",
  contact_email: "email",
  application_method: "howToApply",
  application_url: "applicationLink",
  application_deadline: "applicationDeadline",
  event_dates: "eventDates",
  website: "website",
  research_notes: "researchNotes",
  last_contact: "lastContact",
  next_action: "nextAction",
  added_by: "addedBy",
};

type T = (key: string, vars?: Record<string, string | number>) => string;

function fieldLabel(field: string, t: T): string {
  const key = FIELD_KEY[field];
  return key ? t(`venueSheet.${key}`) : field;
}

function describe(edit: VenueEdit, t: T): string {
  switch (edit.action) {
    case "created":
      return t("history.created");
    case "status": {
      const changes = (edit.changes as FieldChange[]) ?? [];
      const to = changes[0]?.to;
      return t("history.movedTo", { status: to ? t(`status.${to}`) : "" });
    }
    case "updated": {
      const changes = (edit.changes as FieldChange[]) ?? [];
      const fields = changes.map((c) => fieldLabel(c.field, t)).join(", ");
      return t("history.edited", { fields });
    }
    case "artist_added": {
      const c = edit.changes as { artist?: string };
      return t("history.artistAdded", { artist: c?.artist ?? "" });
    }
    case "artist_removed": {
      const c = edit.changes as { artist?: string };
      return t("history.artistRemoved", { artist: c?.artist ?? "" });
    }
    default:
      return edit.action;
  }
}

export default function VenueHistory({
  venueId,
  refreshToken = 0,
  onUnauthorized,
}: {
  venueId: number;
  refreshToken?: number;
  onUnauthorized: () => void;
}) {
  const { t, lang } = useI18n();
  const [edits, setEdits] = useState<VenueEdit[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchVenueHistory(venueId)
      .then((rows) => {
        if (!cancelled) setEdits(rows);
      })
      .catch((err) => {
        if (err instanceof UnauthorizedError) onUnauthorized();
        else if (!cancelled) setEdits([]);
      });
    return () => {
      cancelled = true;
    };
  }, [venueId, refreshToken, onUnauthorized]);

  return (
    <section className="history">
      <h3 className="history-title">{t("history.title")}</h3>
      {edits === null ? (
        <p className="history-empty">{t("history.loading")}</p>
      ) : edits.length === 0 ? (
        <p className="history-empty">{t("history.empty")}</p>
      ) : (
        <ul className="history-list">
          {edits.map((edit) => (
            <li key={edit.id} className="history-entry">
              <span className="history-who">{edit.editor ?? t("history.unknown")}</span>
              <span className="history-what">{describe(edit, t)}</span>
              <span className="history-when">
                {new Date(edit.created_at).toLocaleString(lang, {
                  day: "numeric",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
