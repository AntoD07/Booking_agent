from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import DraftStatus, VenueStatus, VenueType


def _require_name(value: str | None) -> str:
    if value is None or not value.strip():
        raise ValueError("name must not be blank")
    return value.strip()


class VenueBase(BaseModel):
    name: str
    type: VenueType = VenueType.venue
    country: str | None = None
    region: str | None = None
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
    added_by: str | None = None
    field_confidence: dict[str, str] | None = None

    _validate_name = field_validator("name")(_require_name)


class VenueCreate(VenueBase):
    pass


class VenueUpdate(BaseModel):
    name: str | None = None
    type: VenueType | None = None
    country: str | None = None
    region: str | None = None
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
    added_by: str | None = None
    field_confidence: dict[str, str] | None = None

    # PATCH omitting name is fine, but an explicit blank/null name would
    # violate the not-null column, so reject it up front.
    _validate_name = field_validator("name")(_require_name)


class VenueArtistOut(BaseModel):
    """A reference-artist appearance at a venue (name + optional year/edition)."""

    model_config = ConfigDict(from_attributes=True)

    artist_id: int
    name: str
    year: str | None = None


class AppearanceCreate(BaseModel):
    name: str
    year: str | None = None

    _validate_name = field_validator("name")(_require_name)


class VenueOut(VenueBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artists: list[VenueArtistOut] = []


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


class DiscoveryRequest(BaseModel):
    """Reference artists to scan, by name (from the table or free text)."""

    artists: list[str]

    @field_validator("artists")
    @classmethod
    def _one_to_five_names(cls, value: list[str]) -> list[str]:
        names = [name.strip() for name in value if name and name.strip()]
        if not 1 <= len(names) <= 5:
            raise ValueError("give one to five reference artist names")
        return names


class GeneralScanRequest(BaseModel):
    """Parameters for a general scan: what to look for, where, and when."""

    region: str
    event_type: VenueType | None = None
    period: str | None = None

    _validate_region = field_validator("region")(_require_name)


class SuggestionOut(BaseModel):
    """A venue Claude found, plus whether it's already in the pipeline."""

    name: str
    type: VenueType
    city: str | None = None
    country: str | None = None
    website: str | None = None
    artist: str | None = None
    event_dates: str | None = None
    source_url: str | None = None
    already_in_pipeline: bool = False
    matched_venue_id: int | None = None
    matched_venue_name: str | None = None


class DiscoveryOut(BaseModel):
    suggestions: list[SuggestionOut]


class ScanStarted(BaseModel):
    """A scan accepted for background processing; poll the job for results."""

    job_id: str


class ScanJobOut(BaseModel):
    job_id: str
    status: str  # running | done | failed
    error: str | None = None
    # Latest progress step, shown live while the scan runs.
    note: str | None = None
    suggestions: list[SuggestionOut] | None = None


class SuggestionAccept(BaseModel):
    """An accepted suggestion, to be turned into a pipeline venue."""

    name: str
    type: VenueType = VenueType.venue
    city: str | None = None
    country: str | None = None
    website: str | None = None
    artist: str | None = None
    event_dates: str | None = None
    source_url: str | None = None
    # Where the lead came from; defaults to the artist hook when absent.
    source: str | None = None

    _validate_name = field_validator("name")(_require_name)


class ResearchFindingOut(BaseModel):
    """A fact Claude found for a venue during a Search & fill run."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int | None
    venue_name: str
    field: str
    old_value: str | None
    new_value: str
    confidence: str
    source: str | None
    applied: bool


class ResearchStarted(BaseModel):
    run_id: int


class StaleDatesReset(BaseModel):
    """Outcome of clearing Claude-filled dates from a past edition."""

    cleared: int
    venues: list[str]


class ResearchRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str  # running | completed | failed
    started_at: datetime
    finished_at: datetime | None
    venues_checked: int
    fields_filled: int
    note: str | None
    summary: str | None
    error: str | None
    findings: list[ResearchFindingOut] = []


class LoginRequest(BaseModel):
    band_name: str
    password: str

    _validate_band = field_validator("band_name")(_require_name)


class SessionOut(BaseModel):
    """Who the current session is signed in as."""

    authenticated: bool = True
    band_name: str
