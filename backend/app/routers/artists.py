from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Artist
from app.schemas import ArtistCreate, ArtistOut, ArtistUpdate
from app.security import require_session

router = APIRouter(
    prefix="/api/artists", tags=["artists"], dependencies=[Depends(require_session)]
)


def _get_or_404(db: Session, artist_id: int) -> Artist:
    artist = db.get(Artist, artist_id)
    if artist is None:
        raise HTTPException(status_code=404, detail="Artist not found")
    return artist


@router.get("", response_model=list[ArtistOut])
def list_artists(db: Session = Depends(get_db)) -> list[Artist]:
    return list(db.scalars(select(Artist).order_by(Artist.name)))


@router.post("", response_model=ArtistOut, status_code=201)
def create_artist(payload: ArtistCreate, db: Session = Depends(get_db)) -> Artist:
    artist = Artist(**payload.model_dump())
    db.add(artist)
    db.commit()
    db.refresh(artist)
    return artist


@router.get("/{artist_id}", response_model=ArtistOut)
def get_artist(artist_id: int, db: Session = Depends(get_db)) -> Artist:
    return _get_or_404(db, artist_id)


@router.patch("/{artist_id}", response_model=ArtistOut)
def update_artist(
    artist_id: int, payload: ArtistUpdate, db: Session = Depends(get_db)
) -> Artist:
    artist = _get_or_404(db, artist_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(artist, field, value)
    db.commit()
    db.refresh(artist)
    return artist


@router.delete("/{artist_id}", status_code=204)
def delete_artist(artist_id: int, db: Session = Depends(get_db)) -> None:
    artist = _get_or_404(db, artist_id)
    db.delete(artist)
    db.commit()
