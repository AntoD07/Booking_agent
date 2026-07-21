"""Import venues and reference artists exported from the Notion workspace.

Usage: cd backend && python -m app.import_notion
Runs at deploy (see render.yaml), after migrations. Idempotent: venues and
artists whose name already exists are skipped, so records edited in the app
afterwards are never overwritten. The original placeholder rows created by
app.seed (source="seed") are removed the first time this runs.
"""

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Artist, Venue, VenueStatus, VenueType

DATA_FILE = Path(__file__).parent / "data" / "notion_import.json"


def run() -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        removed = 0
        for venue in db.scalars(select(Venue).where(Venue.source == "seed")):
            db.delete(venue)
            removed += 1
        for artist in db.scalars(
            select(Artist).where(Artist.notes == "Seed reference artist.")
        ):
            db.delete(artist)
            removed += 1

        added = backfilled = 0
        for row in payload["venues"]:
            existing = db.scalar(select(Venue).where(Venue.name == row["name"]))
            if existing is None:
                data = dict(row)
                data["type"] = VenueType(data["type"])
                data["status"] = VenueStatus(data["status"])
                if data.get("application_deadline"):
                    data["application_deadline"] = date.fromisoformat(
                        data["application_deadline"]
                    )
                db.add(Venue(**data))
                added += 1
            elif row.get("application_deadline") and existing.application_deadline is None:
                # Deadlines were added to the dataset after the first deploys:
                # backfill them into existing rows, but never touch a deadline
                # a human has already set.
                existing.application_deadline = date.fromisoformat(
                    row["application_deadline"]
                )
                confidence = dict(existing.field_confidence or {})
                confidence["application_deadline"] = (
                    row.get("field_confidence") or {}
                ).get("application_deadline", "medium")
                existing.field_confidence = confidence
                backfilled += 1
        for row in payload["artists"]:
            if db.scalar(select(Artist).where(Artist.name == row["name"])) is None:
                db.add(Artist(**row))
                added += 1

        db.commit()
        print(
            f"Notion import: {added} records added, {backfilled} deadlines "
            f"backfilled, {removed} placeholders removed."
        )


if __name__ == "__main__":
    run()
