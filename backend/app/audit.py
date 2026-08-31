"""Recording who changed a venue card, for its history and "Modified by" line."""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.models import Venue, VenueEdit

# Internal research metadata — changing these should not clutter the history.
_UNTRACKED = {"field_confidence", "field_sources"}


def _fmt(value: Any) -> Any:
    """A JSON-friendly, human-readable rendering of a field value."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def record_edit(
    db: Session,
    venue: Venue,
    editor: str | None,
    action: str,
    changes: list | dict | None = None,
) -> None:
    """Append a history entry and stamp the card's last-modified fields.

    Does not commit — the caller's transaction does, so the edit and the
    change it describes are saved together.
    """
    db.add(
        VenueEdit(
            band_id=venue.band_id,
            venue_id=venue.id,
            venue_name=venue.name,
            editor=editor,
            action=action,
            changes=changes,
        )
    )
    venue.last_modified_by = editor
    venue.last_modified_at = datetime.now(timezone.utc)


def apply_update(venue: Venue, updates: dict) -> list[dict]:
    """Apply PATCH fields to the venue, returning the tracked field changes as
    a list of {field, from, to} — empty when nothing meaningful changed."""
    changes: list[dict] = []
    for field, new_value in updates.items():
        old_value = getattr(venue, field)
        if old_value != new_value and field not in _UNTRACKED:
            changes.append(
                {"field": field, "from": _fmt(old_value), "to": _fmt(new_value)}
            )
        setattr(venue, field, new_value)
    return changes
