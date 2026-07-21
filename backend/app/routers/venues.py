from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Venue
from app.schemas import VenueCreate, VenueOut, VenueUpdate
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
