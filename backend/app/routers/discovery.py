from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import discovery
from app.config import anthropic_api_key
from app.db import get_db
from app.models import Artist, Venue, VenueArtist, VenueStatus
from app.schemas import (
    DiscoveryOut,
    DiscoveryRequest,
    SuggestionAccept,
    SuggestionOut,
    VenueOut,
)
from app.security import require_session

router = APIRouter(
    prefix="/api/discovery",
    tags=["discovery"],
    dependencies=[Depends(require_session)],
)


@router.post("", response_model=DiscoveryOut)
def discover(payload: DiscoveryRequest, db: Session = Depends(get_db)) -> DiscoveryOut:
    if not anthropic_api_key():
        raise HTTPException(
            status_code=503, detail="ANTHROPIC_API_KEY is not configured"
        )
    try:
        found = discovery.run_discovery(payload.artists)
    except discovery.DiscoveryError as exc:
        raise HTTPException(status_code=502, detail=f"Discovery failed: {exc}")
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc.message}")
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=502, detail="Could not reach the Claude API")

    # Record the scan time on artists we know, so the picker can show when
    # each one was last scouted. Free-text names only get a row on accept.
    scanned = {name.lower() for name in payload.artists}
    now = datetime.now(timezone.utc)
    for artist in db.scalars(select(Artist)):
        if artist.name.lower() in scanned:
            artist.last_scanned = now
    db.commit()

    existing = [(v.id, v.name) for v in db.scalars(select(Venue))]
    suggestions = []
    for item in found:
        match = discovery.find_pipeline_match(item["name"], existing)
        suggestions.append(
            SuggestionOut(
                **item,
                already_in_pipeline=match is not None,
                matched_venue_id=match[0] if match else None,
                matched_venue_name=match[1] if match else None,
            )
        )
    return DiscoveryOut(suggestions=suggestions)


@router.post("/accept", response_model=VenueOut, status_code=201)
def accept_suggestion(
    payload: SuggestionAccept, db: Session = Depends(get_db)
) -> Venue:
    """Turn a reviewed suggestion into a pipeline venue.

    The venue enters as Discovered with the artist hook as its source, and
    the reference artist is linked (created by name if needed).
    """
    source = (
        f"Scouting — {payload.artist} played here" if payload.artist else "Scouting"
    )
    notes = f"Found via reference-artist scouting.\nSource: {payload.source_url}" \
        if payload.source_url else None
    venue = Venue(
        name=payload.name,
        type=payload.type,
        city=payload.city,
        country=payload.country,
        website=payload.website,
        status=VenueStatus.discovered,
        source=source,
        research_notes=notes,
        added_by="Claude",
    )
    db.add(venue)
    db.flush()
    if payload.artist:
        artist = db.scalar(select(Artist).where(Artist.name == payload.artist))
        if artist is None:
            artist = Artist(name=payload.artist)
            db.add(artist)
            db.flush()
        db.add(VenueArtist(venue_id=venue.id, artist_id=artist.id))
    db.commit()
    db.refresh(venue)
    return venue
