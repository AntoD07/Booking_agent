from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models import DraftStatus, VenueStatus, VenueType


class VenueBase(BaseModel):
    name: str
    type: VenueType = VenueType.venue
    country: str | None = None
    city: str | None = None
    status: VenueStatus = VenueStatus.discovered
    fit_score: float | None = None
    booking_contact: str | None = None
    contact_email: str | None = None
    application_method: str | None = None
    application_url: str | None = None
    application_deadline: date | None = None
    event_dates: str | None = None
    website: str | None = None
    research_notes: str | None = None
    last_contact: date | None = None
    next_action: str | None = None
    source: str | None = None


class VenueCreate(VenueBase):
    pass


class VenueUpdate(BaseModel):
    name: str | None = None
    type: VenueType | None = None
    country: str | None = None
    city: str | None = None
    status: VenueStatus | None = None
    fit_score: float | None = None
    booking_contact: str | None = None
    contact_email: str | None = None
    application_method: str | None = None
    application_url: str | None = None
    application_deadline: date | None = None
    event_dates: str | None = None
    website: str | None = None
    research_notes: str | None = None
    last_contact: date | None = None
    next_action: str | None = None
    source: str | None = None


class ArtistSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class VenueOut(VenueBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artists: list[ArtistSummary] = []


class ArtistBase(BaseModel):
    name: str
    styles: str | None = None
    country_base: str | None = None
    similarity: str | None = None
    gig_feed_url: str | None = None
    website: str | None = None
    last_scanned: datetime | None = None
    notes: str | None = None


class ArtistCreate(ArtistBase):
    pass


class ArtistUpdate(BaseModel):
    name: str | None = None
    styles: str | None = None
    country_base: str | None = None
    similarity: str | None = None
    gig_feed_url: str | None = None
    website: str | None = None
    last_scanned: datetime | None = None
    notes: str | None = None


class ArtistOut(ArtistBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class EmailDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int
    subject: str
    body: str
    status: DraftStatus
    created_at: datetime


class LoginRequest(BaseModel):
    password: str
