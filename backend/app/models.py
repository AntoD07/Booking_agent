import enum
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text
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

    artists: Mapped[list["Artist"]] = relationship(
        secondary="venue_artists", back_populates="venues"
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

    venues: Mapped[list[Venue]] = relationship(
        secondary="venue_artists", back_populates="artists"
    )


class VenueArtist(Base):
    __tablename__ = "venue_artists"

    venue_id: Mapped[int] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True
    )


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
