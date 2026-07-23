import enum
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class VenueStatus(str, enum.Enum):
    discovered = "discovered"
    researched = "researched"
    draft_ready = "draft_ready"
    sent = "sent"
    follow_up = "follow_up"
    confirmed = "confirmed"
    declined = "declined"
    not_a_fit = "not_a_fit"


class VenueType(str, enum.Enum):
    festival = "festival"
    venue = "venue"
    jazz_club = "jazz_club"
    bar = "bar"
    cultural_center = "cultural_center"


class DraftStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    sent = "sent"


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[VenueType] = mapped_column(
        Enum(VenueType, native_enum=False, length=30), default=VenueType.venue
    )
    country: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[VenueStatus] = mapped_column(
        Enum(VenueStatus, native_enum=False, length=30), default=VenueStatus.discovered
    )
    fit_score: Mapped[float | None] = mapped_column(Float)
    booking_contact: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    application_method: Mapped[str | None] = mapped_column(String(200))
    application_url: Mapped[str | None] = mapped_column(String(500))
    application_deadline: Mapped[date | None] = mapped_column(Date)
    event_dates: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(500))
    research_notes: Mapped[str | None] = mapped_column(Text)
    last_contact: Mapped[date | None] = mapped_column(Date)
    next_action: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str | None] = mapped_column(String(200))
    added_by: Mapped[str | None] = mapped_column(String(100))
    # Per-field research confidence for values filled by Claude,
    # e.g. {"contact_email": "high"}. Cleared per field when a human edits it.
    field_confidence: Mapped[dict | None] = mapped_column(JSON)
    # When "Search & fill" last researched this venue; recently researched
    # venues are skipped so repeated runs move through the whole pipeline.
    last_researched: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    artists: Mapped[list["VenueArtist"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    drafts: Mapped[list["EmailDraft"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    styles: Mapped[str | None] = mapped_column(String(300))
    country_base: Mapped[str | None] = mapped_column(String(100))
    similarity: Mapped[str | None] = mapped_column(String(300))
    gig_feed_url: Mapped[str | None] = mapped_column(String(500))
    website: Mapped[str | None] = mapped_column(String(500))
    last_scanned: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    appearances: Mapped[list["VenueArtist"]] = relationship(
        back_populates="artist", cascade="all, delete-orphan"
    )


class VenueArtist(Base):
    """An appearance of a reference artist at a venue, optionally dated."""

    __tablename__ = "venue_artists"

    venue_id: Mapped[int] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )
    year: Mapped[str | None] = mapped_column(String(50))

    venue: Mapped[Venue] = relationship(back_populates="artists")
    artist: Mapped[Artist] = relationship(back_populates="appearances")

    @property
    def name(self) -> str:
        return self.artist.name


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, native_enum=False, length=20), default=DraftStatus.draft
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    venue: Mapped[Venue] = relationship(back_populates="drafts")


class ResearchRun(Base):
    """One click of "Search & fill": a batch of venues researched by Claude."""

    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    venues_checked: Mapped[int] = mapped_column(default=0)
    fields_filled: Mapped[int] = mapped_column(default=0)
    # Latest progress step while running; a human-readable recap when done.
    note: Mapped[str | None] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    findings: Mapped[list["ResearchFinding"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ResearchFinding(Base):
    """A single fact Claude found for a venue, and whether it was applied."""

    __tablename__ = "research_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    venue_id: Mapped[int | None] = mapped_column(
        ForeignKey("venues.id", ondelete="SET NULL")
    )
    # Kept denormalized so findings stay readable after a venue is deleted.
    venue_name: Mapped[str] = mapped_column(String(200))
    field: Mapped[str] = mapped_column(String(50))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(10))
    source: Mapped[str | None] = mapped_column(String(500))
    # False when the venue already had a human-verified value we kept.
    applied: Mapped[bool] = mapped_column(default=True)

    run: Mapped[ResearchRun] = relationship(back_populates="findings")
