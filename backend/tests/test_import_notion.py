from sqlalchemy import select

from app.db import SessionLocal
from app.import_notion import run as run_import
from app.models import Artist, Venue, VenueStatus, VenueType


def _counts():
    with SessionLocal() as db:
        return (
            len(db.scalars(select(Venue)).all()),
            len(db.scalars(select(Artist)).all()),
        )


def test_import_populates_and_removes_placeholders(client):
    with SessionLocal() as db:
        db.add(Venue(name="Placeholder", source="seed"))
        db.add(Artist(name="Placeholder", notes="Seed reference artist."))
        db.commit()

    run_import()

    venues, artists = _counts()
    assert venues == 69
    assert artists == 2

    with SessionLocal() as db:
        assert db.scalar(select(Venue).where(Venue.source == "seed")) is None

        huchette = db.scalar(select(Venue).where(Venue.name == "Caveau de la Huchette"))
        assert huchette.type == VenueType.jazz_club
        assert huchette.status == VenueStatus.discovered
        assert huchette.region == "Île-de-France"
        assert huchette.country == "France"
        assert huchette.added_by == "Antony"

        django = db.scalar(select(Venue).where(Venue.name == "Festival Django Reinhardt"))
        assert django.type == VenueType.festival
        assert django.status == VenueStatus.sent
        assert django.contact_email == "Contact@festivaldjangoreinhardt.com"


def test_import_includes_enrichment(client):
    run_import()
    with SessionLocal() as db:
        # Web-researched email carries a confidence marker.
        huchette = db.scalar(select(Venue).where(Venue.name == "Caveau de la Huchette"))
        assert huchette.contact_email == "artiste@caveaudelahuchette.fr"
        assert huchette.field_confidence["contact_email"] == "high"

        # The two re-identified cards use their corrected names.
        assert db.scalar(select(Venue).where(Venue.name == "Au Grès du Jazz")) is not None
        assert db.scalar(select(Venue).where(Venue.name == "Colmar Jazz Festival")) is not None
        assert db.scalar(select(Venue).where(Venue.name == "Festival Jazz aux Gres")) is None

        # Human-entered data was not overwritten by enrichment.
        juan = db.scalar(select(Venue).where(Venue.name == "Jazz à Juan"))
        assert juan.contact_email == "diane.mazmanian@antibesjuanlespins.com"
        assert "contact_email" not in (juan.field_confidence or {})


def test_import_is_idempotent_and_keeps_edits(client):
    run_import()

    with SessionLocal() as db:
        venue = db.scalar(select(Venue).where(Venue.name == "New Morning"))
        venue.status = VenueStatus.confirmed
        db.commit()

    run_import()

    assert _counts() == (69, 2)
    with SessionLocal() as db:
        venue = db.scalar(select(Venue).where(Venue.name == "New Morning"))
        assert venue.status == VenueStatus.confirmed
