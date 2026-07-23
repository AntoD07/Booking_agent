"""Seed the database with a few venues and reference artists.

Usage: cd backend && python -m app.seed
Assumes migrations have been applied (alembic upgrade head).
Idempotent: skips records whose name already exists.
"""

from datetime import date

from sqlalchemy import select

from app.bands import get_or_create_seed_band
from app.db import SessionLocal
from app.models import Artist, Venue, VenueStatus, VenueType

VENUES = [
    Venue(
        name="Jazz à Vienne",
        type=VenueType.festival,
        country="France",
        city="Vienne",
        status=VenueStatus.researched,
        fit_score=4.0,
        application_method="Online form",
        application_url="https://jazzavienne.com",
        application_deadline=date(2026, 11, 30),
        event_dates="Late June – mid July 2027",
        website="https://jazzavienne.com",
        research_notes="Major festival with off-stage programming open to manouche groups.",
        next_action="Confirm 2027 application window",
        source="seed",
    ),
    Venue(
        name="Le Caveau de la Huchette",
        type=VenueType.jazz_club,
        country="France",
        city="Paris",
        status=VenueStatus.discovered,
        fit_score=4.5,
        application_method="Email booker",
        website="https://caveaudelahuchette.fr",
        research_notes="Historic swing cellar; books gypsy jazz regularly.",
        next_action="Find booking contact",
        source="seed",
    ),
    Venue(
        name="Django Reinhardt Festival Samois",
        type=VenueType.festival,
        country="France",
        city="Fontainebleau",
        status=VenueStatus.discovered,
        fit_score=5.0,
        event_dates="Early July 2027",
        website="https://festivaldjangoreinhardt.com",
        research_notes="The reference festival for the manouche scene.",
        next_action="Research programmer and application process",
        source="seed",
    ),
]

ARTISTS = [
    Artist(
        name="Rocky Gresset Trio",
        styles="Gypsy jazz, swing",
        country_base="France",
        similarity="Same manouche guitar tradition, comparable lineup",
        website="https://rockygresset.com",
        notes="Seed reference artist.",
    ),
    Artist(
        name="Antoine Boyer & Samuelito",
        styles="Gypsy jazz, flamenco crossover",
        country_base="France",
        similarity="Young acoustic duo touring the same European circuit",
        website="https://antoineboyer.com",
        notes="Seed reference artist.",
    ),
]


def seed() -> None:
    with SessionLocal() as db:
        band = get_or_create_seed_band(db)
        added = 0
        for venue in VENUES:
            if (
                db.scalar(
                    select(Venue).where(
                        Venue.band_id == band.id, Venue.name == venue.name
                    )
                )
                is None
            ):
                venue.band_id = band.id
                db.add(venue)
                added += 1
        for artist in ARTISTS:
            if (
                db.scalar(
                    select(Artist).where(
                        Artist.band_id == band.id, Artist.name == artist.name
                    )
                )
                is None
            ):
                artist.band_id = band.id
                db.add(artist)
                added += 1
        db.commit()
        print(f"Seed complete: {added} new records.")


if __name__ == "__main__":
    seed()
