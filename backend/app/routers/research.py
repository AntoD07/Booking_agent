import logging
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import enrichment
from app.config import anthropic_api_key
from app.db import SessionLocal, get_db
from app.models import Band, ResearchRun
from app.schemas import ResearchRunOut, ResearchStarted
from app.security import current_band

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


def _api_key_for(band: Band) -> str | None:
    """The band's own key when it has one, otherwise the shared env key."""
    return band.anthropic_api_key or anthropic_api_key()


def _require_api_key(band: Band) -> None:
    if not _api_key_for(band):
        raise HTTPException(
            status_code=503, detail="ANTHROPIC_API_KEY is not configured"
        )


def _fail_stale_runs(db: Session, band_id: int) -> None:
    """A run left "running" by a restart must not lock the button forever."""
    cutoff = datetime.now(timezone.utc) - enrichment.STALE_RUN_AFTER
    for run in db.scalars(
        select(ResearchRun).where(
            ResearchRun.band_id == band_id, ResearchRun.status == "running"
        )
    ):
        started = run.started_at
        if started.tzinfo is None:  # SQLite drops tzinfo
            started = started.replace(tzinfo=timezone.utc)
        if started < cutoff:
            run.status = "failed"
            run.error = "The search was interrupted (server restarted)."
            run.finished_at = datetime.now(timezone.utc)
    db.commit()


def _run_research(run_id: int, band_id: int, api_key: str | None) -> None:
    """Background job: research a batch of the band's venues and record it."""
    db = SessionLocal()
    try:
        run = db.get(ResearchRun, run_id)
        if run is None:
            return

        def note(message: str) -> None:
            run.note = message[:300]
            db.commit()

        try:
            venues = enrichment.select_venues(db, band_id)
            if not venues:
                run.status = "completed"
                run.summary = (
                    "Every venue is either complete or was researched in the "
                    "last two weeks — nothing to do."
                )
                return
            note(f"Researching {len(venues)} venues…")
            payload = [
                enrichment._venue_payload(v, enrichment.missing_fields(v))
                for v in venues
            ]
            findings = enrichment.research_batch(payload, progress=note, api_key=api_key)
            enrichment.apply_findings(db, run, venues, findings)
            kept = sum(1 for f in run.findings if not f.applied)
            run.status = "completed"
            run.summary = (
                f"Checked {run.venues_checked} venues — "
                f"{run.fields_filled} fields filled"
                + (
                    f", {kept} finding{'s' if kept != 1 else ''} kept for review"
                    if kept
                    else ""
                )
                + "."
            )
        except enrichment.DiscoveryError as exc:
            run.status = "failed"
            run.error = f"Research failed: {exc}"
        except anthropic.APITimeoutError:
            run.status = "failed"
            run.error = "The search timed out — try again."
        except anthropic.APIStatusError as exc:
            run.status = "failed"
            run.error = f"Claude API error: {exc.message}"
        except anthropic.APIConnectionError:
            run.status = "failed"
            run.error = "Could not reach the Claude API"
        except Exception as exc:  # noqa: BLE001 — a run must never stay "running"
            logger.exception("research run %s crashed", run_id)
            run.status = "failed"
            run.error = f"Research failed: {exc}"
        finally:
            run.note = None
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def _run_out(run: ResearchRun) -> ResearchRunOut:
    return ResearchRunOut.model_validate(run)


@router.post("/runs", response_model=ResearchRunOut, status_code=202)
def start_run(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    band: Band = Depends(current_band),
) -> ResearchRunOut:
    """Start a Search & fill run, or return the one already running."""
    _require_api_key(band)
    _fail_stale_runs(db, band.id)
    active = db.scalar(
        select(ResearchRun)
        .where(ResearchRun.band_id == band.id, ResearchRun.status == "running")
        .order_by(ResearchRun.started_at.desc())
    )
    if active is not None:
        return _run_out(active)
    run = ResearchRun(note="Starting…", band_id=band.id)
    db.add(run)
    db.commit()
    db.refresh(run)
    background_tasks.add_task(_run_research, run.id, band.id, _api_key_for(band))
    return _run_out(run)


@router.get("/runs", response_model=list[ResearchRunOut])
def list_runs(
    db: Session = Depends(get_db), band: Band = Depends(current_band)
) -> list[ResearchRunOut]:
    """Recent runs, newest first — past findings stay reviewable."""
    runs = db.scalars(
        select(ResearchRun)
        .where(ResearchRun.band_id == band.id)
        .options(selectinload(ResearchRun.findings))
        .order_by(ResearchRun.started_at.desc())
        .limit(10)
    )
    return [_run_out(run) for run in runs]


@router.get("/runs/{run_id}", response_model=ResearchRunOut)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    band: Band = Depends(current_band),
) -> ResearchRunOut:
    run = db.get(ResearchRun, run_id, options=[selectinload(ResearchRun.findings)])
    if run is None or run.band_id != band.id:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_out(run)
