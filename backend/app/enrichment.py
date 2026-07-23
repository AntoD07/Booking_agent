"""Search & fill: research incomplete pipeline venues via the Claude API.

One run selects the venues most in need of information (missing contact,
deadline, or website — or a deadline already in the past), researches the
whole batch in a single Claude call with web search, and applies findings
under the confidence rules: empty fields are filled, Claude-filled values
may be refreshed, human-verified values are never overwritten. Every
finding is stored on the run for later review.
"""

import json
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import anthropic_api_key
from app.discovery import (
    DISCOVERY_MODEL,
    MAX_CONTINUATIONS,
    REQUEST_TIMEOUT_SECONDS,
    DiscoveryError,
    _create_message,
    _extract_json_array,
)
from app.models import ResearchFinding, ResearchRun, Venue, VenueType

logger = logging.getLogger(__name__)

# One run researches this many venues in a single Claude call — enough to
# make visible progress, small enough to finish in a few minutes.
BATCH_SIZE = 5
# Venues researched more recently than this are skipped, so repeated runs
# walk through the whole pipeline instead of re-checking the same cards.
RESEARCH_COOLDOWN = timedelta(days=14)
RUN_MAX_SECONDS = 600.0
# A run stuck in "running" longer than this is treated as failed so the button
# doesn't stay locked. A real run cannot exceed RUN_MAX_SECONDS (10 min), so
# 15 min means genuinely dead — not merely slow.
STALE_RUN_AFTER = timedelta(minutes=15)

# The season we are booking. Dates for earlier editions must never populate a
# venue's deadline/event-date fields — they belong in a reference note. Bump
# this when the booking season rolls over.
TARGET_SEASON_YEAR = 2027

# Venue fields Claude may fill, in the order they should display.
RESEARCHABLE_FIELDS = [
    "website",
    "contact_email",
    "booking_contact",
    "application_method",
    "application_url",
    "application_deadline",
    "event_dates",
    "note",
]

_PROMPT = """\
We are a gypsy jazz (jazz manouche) quartet booking our 2027 season across
Europe. Today is {today}. Below are venues and festivals from our booking
pipeline with incomplete or possibly outdated information:

{venues_json}

For each venue, use web search to:
1. Fill the fields listed in "missing" (official website, booking or
   programming contact email, named programmer, how to apply, application
   link).
2. Find the 2027 edition's dates and application deadline. Report
   "event_dates" and "application_deadline" ONLY when they are for the 2027
   season (or later), with confidence "high".
   If the 2027 edition is not published yet, DO NOT report a past edition's
   dates as "event_dates" or "application_deadline". Instead add a "note"
   describing the most recent edition (e.g. "2026 ran 3-18 July, applications
   closed January 2026") so we know the usual window.
3. Note anything important: festival cancelled or paused, renamed, venue
   closed, named programmer, application window intel.

Rules:
- Only report emails you actually found published — never construct one.
- "application_deadline" and "event_dates" must be for 2027 or later. A past
  edition's dates belong in a "note", never in those fields.
- "application_deadline" values must be "YYYY-MM" (month precision).
- "event_dates" is free text, e.g. "25-28 June 2027".
- Skip fields you found nothing reliable for; do not pad.

End your reply with ONLY a JSON array inside a ```json code fence, one
object per finding, with exactly these keys:
- "venue_id": the venue's id from the list above (integer)
- "field": one of "website", "contact_email", "booking_contact",
  "application_method", "application_url", "application_deadline",
  "event_dates", "note"
- "value": the found value (string)
- "confidence": "high" (published/official) or "medium" (derived/secondary)
- "source": URL of the page documenting it, or null
"""


def select_venues(db: Session, limit: int = BATCH_SIZE) -> list[Venue]:
    """Pick the venues most in need of research, oldest-researched first."""
    cutoff = datetime.now(timezone.utc) - RESEARCH_COOLDOWN
    today = date.today()
    candidates = []
    for venue in db.scalars(select(Venue)):
        researched = venue.last_researched
        if researched is not None:
            if researched.tzinfo is None:  # SQLite drops tzinfo
                researched = researched.replace(tzinfo=timezone.utc)
            if researched > cutoff:
                continue
        missing = missing_fields(venue, today)
        if not missing:
            continue
        candidates.append((venue, missing))
    # Neediest first: never-researched venues, then most missing fields,
    # then nearest deadline so urgent cards refresh sooner.
    candidates.sort(
        key=lambda pair: (
            pair[0].last_researched is not None,
            -len(pair[1]),
            pair[0].application_deadline or date.max,
        )
    )
    return [venue for venue, _ in candidates[:limit]]


def missing_fields(venue: Venue, today: date | None = None) -> list[str]:
    """What research could add to this venue right now."""
    today = today or date.today()
    missing = []
    if not venue.website:
        missing.append("website")
    if not venue.contact_email and not venue.booking_contact:
        missing.append("contact_email")
    if venue.type == VenueType.festival:
        if venue.application_deadline is None:
            missing.append("application_deadline")
        elif venue.application_deadline < today.replace(day=1):
            # The deadline has passed: look up the next edition's.
            missing.append("application_deadline")
        if not venue.event_dates:
            missing.append("event_dates")
    if not venue.application_method and not venue.application_url:
        missing.append("application_method")
    return missing


def _venue_payload(venue: Venue, missing: list[str]) -> dict:
    return {
        "id": venue.id,
        "name": venue.name,
        "type": venue.type.value,
        "city": venue.city,
        "country": venue.country,
        "website": venue.website,
        "contact_email": venue.contact_email,
        "booking_contact": venue.booking_contact,
        "application_deadline": (
            venue.application_deadline.strftime("%Y-%m")
            if venue.application_deadline
            else None
        ),
        "event_dates": venue.event_dates,
        "missing": missing,
    }


Progress = Callable[[str], None]


def research_batch(
    venues_payload: list[dict], progress: Progress | None = None
) -> list[dict]:
    """One Claude call researching a batch of venues; returns raw findings."""
    started = time.monotonic()
    deadline = started + RUN_MAX_SECONDS

    def note(message: str) -> None:
        stamped = f"{message} ({time.monotonic() - started:.0f}s elapsed)"
        logger.info("research: %s", stamped)
        if progress is not None:
            progress(stamped)

    prompt = _PROMPT.format(
        today=date.today().isoformat(),
        venues_json=json.dumps(venues_payload, ensure_ascii=False, indent=1),
    )
    client = anthropic.Anthropic(
        api_key=anthropic_api_key(),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=1,
    )
    messages: list = [{"role": "user", "content": prompt}]
    note("Contacting Claude…")
    response = _create_message(client, messages, note, deadline)
    for continuation in range(MAX_CONTINUATIONS):
        if response.stop_reason != "pause_turn":
            break
        messages = messages + [{"role": "assistant", "content": response.content}]
        note(f"Research continues (round {continuation + 2})…")
        response = _create_message(client, messages, note, deadline)

    text = "".join(block.text for block in response.content if block.type == "text")
    items = _extract_json_array(text)
    if items is None:
        if response.stop_reason == "max_tokens":
            raise DiscoveryError(
                "Claude ran out of room before writing its findings — try again"
            )
        raise DiscoveryError(
            f"Claude's reply did not contain findings (starts: {text[:200]!r})"
        )
    findings = [item for item in items if _valid_finding(item)]
    note(f"Parsed {len(findings)} findings from Claude's reply")
    return findings


def _valid_finding(item) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("venue_id"), int)
        and item.get("field") in RESEARCHABLE_FIELDS
        and isinstance(item.get("value"), str)
        and bool(item["value"].strip())
        and item.get("confidence") in ("high", "medium")
    )


def mentions_only_past_years(text: str) -> bool:
    """True when the text names year(s), all earlier than the target season.

    Used to spot event-date strings for an old edition (e.g. "3-18 July 2026")
    so they don't sit in the field as if they were the upcoming edition's.
    """
    years = [int(match) for match in re.findall(r"\b(20\d{2})\b", text)]
    return bool(years) and max(years) < TARGET_SEASON_YEAR


def _parse_month(value: str) -> date | None:
    match = re.match(r"^(\d{4})-(\d{2})(?:-\d{2})?$", value.strip())
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return date(year, month, 1)


def apply_findings(
    db: Session, run: ResearchRun, venues: list[Venue], findings: list[dict]
) -> None:
    """Apply findings under the confidence rules and record every one.

    Empty fields are filled; values previously filled by Claude (tracked in
    field_confidence) may be refreshed; human-verified values are kept and
    the finding stored with applied=False for review.
    """
    by_id = {venue.id: venue for venue in venues}
    now = datetime.now(timezone.utc)
    for item in findings:
        venue = by_id.get(item["venue_id"])
        if venue is None:
            continue
        field = item["field"]
        value = item["value"].strip()
        confidence = item["confidence"]
        source = item.get("source")
        source = source.strip() if isinstance(source, str) and source.strip() else None

        # The pipeline targets the 2027 season. A date for an earlier edition
        # must not populate the deadline/event-date fields — record it as a
        # reference note so the card still reads as "needs the 2027 dates".
        parsed_deadline = None
        if field == "application_deadline":
            parsed_deadline = _parse_month(value)
            if parsed_deadline is None:
                continue  # unusable date format; don't store noise
            if parsed_deadline.year < TARGET_SEASON_YEAR:
                field = "note"
                value = (
                    f"{TARGET_SEASON_YEAR} application deadline not published "
                    f"yet; the most recent edition closed {value}."
                )
                parsed_deadline = None
        elif field == "event_dates" and mentions_only_past_years(value):
            field = "note"
            value = (
                f"{TARGET_SEASON_YEAR} dates not published yet; most recent "
                f"edition: {value}."
            )

        finding = ResearchFinding(
            run=run,
            venue_id=venue.id,
            venue_name=venue.name,
            field=field,
            new_value=value,
            confidence=confidence,
            source=source[:500] if source else None,
            # Explicit: the column default only lands at flush, and the run
            # summary counts kept findings before that.
            applied=True,
        )
        marks = dict(venue.field_confidence or {})

        if field == "note":
            stamp = now.strftime("%b %Y")
            suffix = f" (source : {source})" if source else ""
            addition = f"— Recherche ({stamp}) : {value}{suffix}"
            base = venue.research_notes or ""
            if value not in base:  # re-runs must not duplicate notes
                venue.research_notes = (base + "\n\n" + addition).strip()
            finding.old_value = None
        elif field == "application_deadline":
            finding.old_value = (
                venue.application_deadline.strftime("%Y-%m")
                if venue.application_deadline
                else None
            )
            if venue.application_deadline is not None and field not in marks:
                finding.applied = False  # human-set deadline: keep it
            else:
                venue.application_deadline = parsed_deadline
                marks[field] = confidence
                run.fields_filled += 1
        else:
            current = getattr(venue, field)
            finding.old_value = current
            if current and field not in marks:
                finding.applied = False  # human-entered value: keep it
            elif current == value:
                finding.applied = False  # nothing new
            else:
                setattr(venue, field, value)
                marks[field] = confidence
                run.fields_filled += 1

        venue.field_confidence = marks or None
        db.add(finding)

    for venue in venues:
        venue.last_researched = now
    run.venues_checked = len(venues)
