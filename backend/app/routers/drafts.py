"""Pitch drafts and the band profile they draw on.

Drafting fills the band's approved template for a venue (see app.drafting).
Nothing is ever sent from here — a draft moves draft → approved → sent only
when a human moves it, and "sent" simply records that the band sent it.
"""

import logging
from datetime import date

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import drafting
from app.db import get_db
from app.models import (
    BandProfile,
    DraftStatus,
    EmailDraft,
    Venue,
    VenueArtist,
    VenueStatus,
)
from app.schemas import (
    BandProfileOut,
    BandProfileUpdate,
    EmailDraftOut,
    EmailDraftUpdate,
)
from app.security import require_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["drafts"], dependencies=[Depends(require_session)])

# Once we have a draft the venue is at least "Draft ready"; generating one for
# an earlier card advances it, but never drags a further-along card backwards.
_PRE_DRAFT = {VenueStatus.discovered, VenueStatus.researched}


def _get_profile(db: Session) -> BandProfile:
    """The single band-profile row, created with defaults on first access."""
    profile = db.get(BandProfile, 1)
    if profile is None:
        profile = BandProfile(id=1)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _get_venue(db: Session, venue_id: int) -> Venue:
    venue = db.get(
        Venue,
        venue_id,
        options=[selectinload(Venue.artists).selectinload(VenueArtist.artist)],
    )
    if venue is None:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


def _get_draft(db: Session, draft_id: int) -> EmailDraft:
    draft = db.get(EmailDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("/band-profile", response_model=BandProfileOut)
def get_band_profile(db: Session = Depends(get_db)) -> BandProfile:
    return _get_profile(db)


@router.put("/band-profile", response_model=BandProfileOut)
def update_band_profile(
    payload: BandProfileUpdate, db: Session = Depends(get_db)
) -> BandProfile:
    profile = _get_profile(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/venues/{venue_id}/drafts", response_model=list[EmailDraftOut])
def list_drafts(venue_id: int, db: Session = Depends(get_db)) -> list[EmailDraft]:
    _get_venue(db, venue_id)  # 404 for an unknown venue
    return list(
        db.scalars(
            select(EmailDraft)
            .where(EmailDraft.venue_id == venue_id)
            .order_by(EmailDraft.created_at.desc(), EmailDraft.id.desc())
        )
    )


@router.post(
    "/venues/{venue_id}/drafts", response_model=EmailDraftOut, status_code=201
)
def generate_draft(venue_id: int, db: Session = Depends(get_db)) -> EmailDraft:
    """Draft a pitch email for this venue from the band's template.

    The body is fixed prose; only the personalisation hook and date line vary.
    The hook is written by Claude when a key is set, else left as a bracketed
    placeholder — either way it must be checked before the email is sent.
    """
    venue = _get_venue(db, venue_id)
    profile = _get_profile(db)
    try:
        subject, body, source = drafting.build_draft(venue, profile)
    except anthropic.APITimeoutError:
        raise HTTPException(status_code=504, detail="Drafting timed out — try again.")
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc.message}")
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=502, detail="Could not reach the Claude API")
    draft = EmailDraft(venue_id=venue.id, subject=subject, body=body, source=source)
    db.add(draft)
    if venue.status in _PRE_DRAFT:
        venue.status = VenueStatus.draft_ready
    db.commit()
    db.refresh(draft)
    return draft


@router.patch("/drafts/{draft_id}", response_model=EmailDraftOut)
def update_draft(
    draft_id: int, payload: EmailDraftUpdate, db: Session = Depends(get_db)
) -> EmailDraft:
    draft = _get_draft(db, draft_id)
    fields = payload.model_dump(exclude_unset=True)
    for field, value in fields.items():
        setattr(draft, field, value)
    # Marking a draft "sent" reflects that the band actually sent it: advance
    # the venue and stamp today as the last contact.
    if fields.get("status") == DraftStatus.sent:
        venue = db.get(Venue, draft.venue_id)
        if venue is not None:
            if venue.status in _PRE_DRAFT | {VenueStatus.draft_ready}:
                venue.status = VenueStatus.sent
            venue.last_contact = date.today()
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/drafts/{draft_id}", status_code=204)
def delete_draft(draft_id: int, db: Session = Depends(get_db)) -> None:
    draft = _get_draft(db, draft_id)
    db.delete(draft)
    db.commit()
