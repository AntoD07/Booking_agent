import logging
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import discovery
from app.config import anthropic_api_key
from app.db import SessionLocal, get_db
from app.models import Artist, Venue, VenueArtist, VenueStatus
from app.schemas import (
    DiscoveryOut,
    DiscoveryRequest,
    GeneralScanRequest,
    ScanJobOut,
    ScanStarted,
    SuggestionAccept,
    SuggestionOut,
    VenueOut,
)
from app.security import require_session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/discovery",
    tags=["discovery"],
    dependencies=[Depends(require_session)],
)

# Scans run for minutes — far longer than a browser or proxy will happily
# hold a request open — so they run as background jobs the client polls.
# In-memory is fine: single-user app, single uvicorn worker (render.yaml).
_jobs: dict[str, dict] = {}
_jobs_lock = Lock()
_JOB_TTL = timedelta(hours=2)


def _require_api_key() -> None:
    if not anthropic_api_key():
        raise HTTPException(
            status_code=503, detail="ANTHROPIC_API_KEY is not configured"
        )


def _create_job() -> str:
    cutoff = datetime.now(timezone.utc) - _JOB_TTL
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        for stale in [i for i, j in _jobs.items() if j["created_at"] < cutoff]:
            del _jobs[stale]
        _jobs[job_id] = {
            "status": "running",
            "error": None,
            "result": None,
            "note": None,
            "created_at": datetime.now(timezone.utc),
        }
    return job_id


def _job_note(job_id: str) -> Callable[[str], None]:
    """Progress callback: the scan reports steps, the poller shows them."""

    def note(message: str) -> None:
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is not None:
                job["note"] = message

    return note


def _finish_job(
    job_id: str, *, result: DiscoveryOut | None = None, error: str | None = None
) -> None:
    if error:
        logger.warning("scan job %s failed: %s", job_id, error)
    else:
        count = len(result.suggestions) if result else 0
        logger.info("scan job %s done: %d suggestions", job_id, count)
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None:
            job["status"] = "failed" if error else "done"
            job["error"] = error
            job["result"] = result


def _with_pipeline_matches(found: list[dict], db: Session) -> DiscoveryOut:
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


def _run_scan_job(
    job_id: str,
    scan: Callable[[], list[dict]],
    stamp_artists: list[str] | None = None,
) -> None:
    """Run a scan in the background and record the outcome on the job."""
    try:
        found = scan()
    except discovery.DiscoveryError as exc:
        _finish_job(job_id, error=f"Discovery failed: {exc}")
        return
    except anthropic.APITimeoutError:
        _finish_job(
            job_id,
            error="The scan timed out — try again, with fewer artists or a "
            "narrower search.",
        )
        return
    except anthropic.APIStatusError as exc:
        _finish_job(job_id, error=f"Claude API error: {exc.message}")
        return
    except anthropic.APIConnectionError:
        _finish_job(job_id, error="Could not reach the Claude API")
        return
    except Exception as exc:  # noqa: BLE001 — a job must never stay "running"
        logger.exception("scan job %s crashed", job_id)
        _finish_job(job_id, error=f"Scan failed: {exc}")
        return

    # Background tasks outlive the request, so they get their own session.
    db = SessionLocal()
    try:
        if stamp_artists:
            # Record the scan time on artists we know, so the picker can show
            # when each one was last scouted. Free-text names only get a row
            # on accept.
            scanned = {name.lower() for name in stamp_artists}
            now = datetime.now(timezone.utc)
            for artist in db.scalars(select(Artist)):
                if artist.name.lower() in scanned:
                    artist.last_scanned = now
            db.commit()
        result = _with_pipeline_matches(found, db)
    finally:
        db.close()
    _finish_job(job_id, result=result)


@router.post("", response_model=ScanStarted, status_code=202)
def discover(
    payload: DiscoveryRequest, background_tasks: BackgroundTasks
) -> ScanStarted:
    """Start a scan of 1-5 reference artists' circuits for venues."""
    _require_api_key()
    job_id = _create_job()
    background_tasks.add_task(
        _run_scan_job,
        job_id,
        lambda: discovery.run_discovery(payload.artists, progress=_job_note(job_id)),
        payload.artists,
    )
    return ScanStarted(job_id=job_id)


@router.post("/general", response_model=ScanStarted, status_code=202)
def general_scan(
    payload: GeneralScanRequest, background_tasks: BackgroundTasks
) -> ScanStarted:
    """Start a scan of a region for festivals/venues of a type over a period."""
    _require_api_key()
    job_id = _create_job()
    background_tasks.add_task(
        _run_scan_job,
        job_id,
        lambda: discovery.run_general_discovery(
            payload.region,
            payload.event_type,
            payload.period,
            progress=_job_note(job_id),
        ),
    )
    return ScanStarted(job_id=job_id)


@router.get("/ping")
def ping() -> dict:
    """Cheap end-to-end check of the Claude connection (fractions of a cent)."""
    _require_api_key()
    try:
        return discovery.ping()
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc.message}")
    except anthropic.APIConnectionError as exc:
        raise HTTPException(
            status_code=502, detail=f"Could not reach the Claude API: {exc}"
        )


@router.get("/jobs/{job_id}", response_model=ScanJobOut)
def scan_job(job_id: str) -> ScanJobOut:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    result: DiscoveryOut | None = job["result"]
    return ScanJobOut(
        job_id=job_id,
        status=job["status"],
        error=job["error"],
        note=job["note"],
        suggestions=result.suggestions if result is not None else None,
    )


@router.post("/accept", response_model=VenueOut, status_code=201)
def accept_suggestion(
    payload: SuggestionAccept, db: Session = Depends(get_db)
) -> Venue:
    """Turn a reviewed suggestion into a pipeline venue.

    The venue enters as Discovered. The source is the caller-provided scan
    label when given, otherwise the artist hook; a reference artist, when
    present, is linked (created by name if needed).
    """
    if payload.source:
        source = payload.source.strip()
    elif payload.artist:
        source = f"Scouting — {payload.artist} played here"
    else:
        source = "Scouting"
    notes = f"Source: {payload.source_url}" if payload.source_url else None
    venue = Venue(
        name=payload.name,
        type=payload.type,
        city=payload.city,
        country=payload.country,
        website=payload.website,
        event_dates=payload.event_dates,
        status=VenueStatus.discovered,
        source=source,
        research_notes=notes,
        added_by="Claude",
    )
    db.add(venue)
    db.flush()
    if payload.artist:
        # Case-insensitive match so "die drahtzieher" doesn't duplicate
        # "Die Drahtzieher" in the artists table.
        artist = db.scalar(
            select(Artist).where(
                func.lower(Artist.name) == payload.artist.lower()
            )
        )
        if artist is None:
            artist = Artist(name=payload.artist)
            db.add(artist)
            db.flush()
        db.add(VenueArtist(venue_id=venue.id, artist_id=artist.id))
    db.commit()
    db.refresh(venue)
    return venue
