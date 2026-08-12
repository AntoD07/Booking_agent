from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Artist, Band, Venue, VenueArtist
from app.schemas import AppearanceCreate, VenueCreate, VenueOut, VenueUpdate
from app.security import current_band

router = APIRouter(prefix="/api/venues", tags=["venues"])


def _get_or_404(db: Session, band: Band, venue_id: int) -> Venue:
    venue = db.get(Venue, venue_id)
    if venue is None or venue.band_id != band.id:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@router.get("", response_model=list[VenueOut])
def list_venues(
    db: Session = Depends(get_db), band: Band = Depends(current_band)
) -> list[Venue]:
    return list(
        db.scalars(
            select(Venue).where(Venue.band_id == band.id).order_by(Venue.name)
        )
    )


@router.post("", response_model=VenueOut, status_code=201)
def create_venue(
    payload: VenueCreate,
    db: Session = Depends(get_db),
    band: Band = Depends(current_band),
) -> Venue:
    venue = Venue(**payload.model_dump(), band_id=band.id)
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(
    venue_id: int,
    db: Session = Depends(get_db),
    band: Band = Depends(current_band),
) -> Venue:
    return _get_or_404(db, band, venue_id)


@router.patch("/{venue_id}", response_model=VenueOut)
def update_venue(
    venue_id: int,
    payload: VenueUpdate,
    db: Session = Depends(get_db),
    band: Band = Depends(current_band),
) -> Venue:
    venue = _get_or_404(db, band, venue_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(venue, field, value)
    db.commit()
    db.refresh(venue)
    return venue


@router.delete("/{venue_id}", status_code=204)
def delete_venue(
    venue_id: int,
    db: Session = Depends(get_db),
    band: Band = Depends(current_band),
) -> None:
    venue = _get_or_404(db, band, venue_id)
    db.delete(venue)
    db.commit()


@router.post("/{venue_id}/artists", response_model=VenueOut)
def add_appearance(
    venue_id: int,
    payload: AppearanceCreate,
    db: Session = Depends(get_db),
    band: Band = Depends(current_band),
) -> Venue:
    """Record that a reference artist played this venue (creating the artist
    by name if needed). Posting the same artist again updates the year."""
    venue = _get_or_404(db, band, venue_id)
    artist = db.scalar(
        select(Artist).where(
            Artist.band_id == band.id,
            func.lower(Artist.name) == payload.name.lower(),
        )
    )
    if artist is None:
        artist = Artist(name=payload.name, band_id=band.id)
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
    venue_id: int,
    artist_id: int,
    db: Session = Depends(get_db),
    band: Band = Depends(current_band),
) -> None:
    _get_or_404(db, band, venue_id)  # 404 if the venue isn't this band's
    link = db.get(VenueArtist, (venue_id, artist_id))
    if link is None:
        raise HTTPException(status_code=404, detail="Appearance not found")
    db.delete(link)
    db.commit()
