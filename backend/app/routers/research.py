import logging
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import enrichment
from app.config import anthropic_api_key
from app.db import SessionLocal, get_db
from app.models import ResearchRun, Venue, VenueStatus
from app.schemas import ResearchRunOut, StaleDatesReset
from app.security import require_session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/research",
    tags=["research"],
    dependencies=[Depends(require_session)],
)


def _require_api_key() -> None:
    if not anthropic_api_key():
        raise HTTPException(
            status_code=503, detail="ANTHROPIC_API_KEY is not configured"
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail_stale_runs(db: Session) -> None:
    """A run left "running" by a restart must not lock the button forever."""
    cutoff = _now() - enrichment.STALE_RUN_AFTER
    changed = False
    for run in db.scalars(select(ResearchRun).where(ResearchRun.status == "running")):
        started = run.started_at
        if started.tzinfo is None:  # SQLite drops tzinfo
            started = started.replace(tzinfo=timezone.utc)
        if started < cutoff:
            run.status = "failed"
            run.error = "The search was interrupted (server restarted)."
            run.note = None
            run.finished_at = _now()
            changed = True
    if changed:
        db.commit()


def fail_running_runs() -> None:
    """At startup, fail every still-"running" run: a restart killed any job
    that was in flight, so it can never finish and must not stay "running"."""
    with SessionLocal() as db:
        stuck = list(
            db.scalars(select(ResearchRun).where(ResearchRun.status == "running"))
        )
        for run in stuck:
            run.status = "failed"
            run.error = "The search was interrupted (server restarted)."
            run.note = None
            run.finished_at = _now()
        if stuck:
            db.commit()
            logger.info("failed %d orphaned research run(s) at startup", len(stuck))


def _note(run_id: int, message: str) -> None:
    """Progress update in its own short-lived session, so the multi-minute
    Claude call never holds a DB connection open — serverless Postgres drops
    idle ones, and the later completion commit would then fail."""
    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        if run is not None and run.status == "running":
            run.note = message[:300]
            db.commit()


def _mark_failed(run_id: int, error: str) -> None:
    with SessionLocal() as db:
        run = db.get(ResearchRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error = error
            run.note = None
            run.finished_at = _now()
            db.commit()


def _run_research(run_id: int) -> None:
    """Background job: research a batch of venues and record the outcome.

    Every database touch uses its own short-lived session, so no connection is
    held across the long Claude call. Holding one caused the run to strand as
    "running": the connection was dropped mid-run and the completion commit
    then failed on it.
    """
    try:
        # 1. Pick the venues and build the payload (short session).
        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is None:
                return
            venues = enrichment.select_venues(db)
            if not venues:
                run.status = "completed"
                run.summary = (
                    "Every venue is either complete or was researched in the "
                    "last two weeks — nothing to do."
                )
                run.note = None
                run.finished_at = _now()
                db.commit()
                return
            payload = [
                enrichment._venue_payload(v, enrichment.missing_fields(v))
                for v in venues
            ]
            venue_ids = [v.id for v in venues]

        _note(run_id, f"Researching {len(payload)} venues…")

        # 2. The long Claude call — no DB connection held across it.
        findings = enrichment.research_batch(
            payload, progress=lambda message: _note(run_id, message)
        )

        # 3. Apply findings and finish (fresh session, fresh connection).
        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is None:
                return
            venues = list(db.scalars(select(Venue).where(Venue.id.in_(venue_ids))))
            enrichment.apply_findings(db, run, venues, findings)
            kept = sum(1 for f in run.findings if not f.applied)
            updated = sorted({f.venue_name for f in run.findings if f.applied})
            if updated:
                fields = run.fields_filled
                lead = (
                    f"Updated {len(updated)} of {run.venues_checked} venues "
                    f"({fields} field{'s' if fields != 1 else ''} filled): "
                    + ", ".join(updated)
                )
            else:
                lead = f"Checked {run.venues_checked} venues — nothing new to add"
            run.summary = lead + (
                f". {kept} finding{'s' if kept != 1 else ''} kept for review."
                if kept
                else "."
            )
            run.status = "completed"
            run.note = None
            run.finished_at = _now()
            db.commit()
    except enrichment.DiscoveryError as exc:
        _mark_failed(run_id, f"Research failed: {exc}")
    except anthropic.APITimeoutError:
        _mark_failed(run_id, "The search timed out — try again.")
    except anthropic.APIStatusError as exc:
        _mark_failed(run_id, f"Claude API error: {exc.message}")
    except anthropic.APIConnectionError:
        _mark_failed(run_id, "Could not reach the Claude API")
    except Exception as exc:  # noqa: BLE001 — a run must never stay "running"
        logger.exception("research run %s crashed", run_id)
        _mark_failed(run_id, f"Research failed: {exc}")


def _run_out(run: ResearchRun) -> ResearchRunOut:
    return ResearchRunOut.model_validate(run)


@router.post("/runs", response_model=ResearchRunOut, status_code=202)
def start_run(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> ResearchRunOut:
    """Start a Search & fill run, or return the one already running."""
    _require_api_key()
    _fail_stale_runs(db)
    active = db.scalar(
        select(ResearchRun)
        .where(ResearchRun.status == "running")
        .order_by(ResearchRun.started_at.desc())
    )
    if active is not None:
        return _run_out(active)
    run = ResearchRun(note="Starting…")
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(_run_research, run.id)
    return _run_out(run)


@router.get("/runs", response_model=list[ResearchRunOut])
def list_runs(db: Session = Depends(get_db)) -> list[ResearchRunOut]:
    """Recent runs, newest first — past findings stay reviewable."""
    runs = db.scalars(
        select(ResearchRun)
        .options(selectinload(ResearchRun.findings))
        .order_by(ResearchRun.started_at.desc())
        .limit(10)
    )
    return [_run_out(run) for run in runs]


@router.get("/runs/{run_id}", response_model=ResearchRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)) -> ResearchRunOut:
    # The client polls this; healing a stale run here means a stuck search
    # recovers on its own, without waiting for the next start.
    _fail_stale_runs(db)
    run = db.get(ResearchRun, run_id, options=[selectinload(ResearchRun.findings)])
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_out(run)


@router.post("/clear-stale-dates", response_model=StaleDatesReset)
def clear_stale_dates(db: Session = Depends(get_db)) -> StaleDatesReset:
    """Remove Claude-filled dates that belong to a pre-2027 edition.

    Only fields Claude filled (those carrying a confidence marker) are touched;
    values entered by hand are left alone. Each affected venue drops back to
    Discovered so it gets re-researched for the 2027 season.
    """
    target = enrichment.TARGET_SEASON_YEAR
    cleared: list[str] = []
    for venue in db.scalars(select(Venue)):
        marks = dict(venue.field_confidence or {})
        changed = False
        if (
            "application_deadline" in marks
            and venue.application_deadline is not None
            and venue.application_deadline.year < target
        ):
            venue.application_deadline = None
            marks.pop("application_deadline", None)
            changed = True
        if (
            "event_dates" in marks
            and venue.event_dates
            and enrichment.mentions_only_past_years(venue.event_dates)
        ):
            venue.event_dates = None
            marks.pop("event_dates", None)
            changed = True
        if changed:
            venue.field_confidence = marks or None
            venue.status = VenueStatus.discovered
            cleared.append(venue.name)
    db.commit()
    return StaleDatesReset(cleared=len(cleared), venues=sorted(cleared))
