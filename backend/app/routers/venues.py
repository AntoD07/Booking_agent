from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Artist, Venue, VenueArtist
from app.schemas import AppearanceCreate, VenueCreate, VenueOut, VenueUpdate
from app.security import require_session

router = APIRouter(
    prefix="/api/venues", tags=["venues"], dependencies=[Depends(require_session)]
)


def _get_or_404(db: Session, venue_id: int) -> Venue:
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@router.get("", response_model=list[VenueOut])
def list_venues(db: Session = Depends(get_db)) -> list[Venue]:
    return list(db.scalars(select(Venue).order_by(Venue.name)))


@router.post("", response_model=VenueOut, status_code=201)
def create_venue(payload: VenueCreate, db: Session = Depends(get_db)) -> Venue:
    venue = Venue(**payload.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(venue_id: int, db: Session = Depends(get_db)) -> Venue:
    return _get_or_404(db, venue_id)


@router.patch("/{venue_id}", response_model=VenueOut)
def update_venue(
    venue_id: int, payload: VenueUpdate, db: Session = Depends(get_db)
) -> Venue:
    venue = _get_or_404(db, venue_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(venue, field, value)
    db.commit()
    db.refresh(venue)
    return venue


@router.delete("/{venue_id}", status_code=204)
def delete_venue(venue_id: int, db: Session = Depends(get_db)) -> None:
    venue = _get_or_404(db, venue_id)
    db.delete(venue)
    db.commit()


@router.post("/{venue_id}/artists", response_model=VenueOut)
def add_appearance(
    venue_id: int, payload: AppearanceCreate, db: Session = Depends(get_db)
) -> Venue:
    """Record that a reference artist played this venue (creating the artist
    by name if needed). Posting the same artist again updates the year."""
    venue = _get_or_404(db, venue_id)
    artist = db.scalar(select(Artist).where(Artist.name == payload.name))
    if artist is None:
        artist = Artist(name=payload.name)
        db.add(artist)
        db.flush()
    link = db.get(VenueArtist, (venue_id, artist.id))
    if link is None:
        db.add(VenueArtist(venue_id=venue_id, artist_id=artist.id, year=payload.year))
    else:
        link.year = payload.year
    db.commit()
    db.refresh(venue)
    return venue


@router.delete("/{venue_id}/artists/{artist_id}", status_code=204)
def remove_appearance(
    venue_id: int, artist_id: int, db: Session = Depends(get_db)
) -> None:
    link = db.get(VenueArtist, (venue_id, artist_id))
    if link is None:
        raise HTTPException(status_code=404, detail="Appearance not found")
    db.delete(link)
    db.commit()
