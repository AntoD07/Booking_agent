from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import enrichment
from app.db import SessionLocal
from app.models import ResearchFinding, ResearchRun, Venue, VenueStatus, VenueType


def _make_venue(db, **overrides):
    defaults = {"name": "Testival", "type": VenueType.festival}
    defaults.update(overrides)
    venue = Venue(**defaults)
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def test_start_requires_api_key(auth_client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = auth_client.post("/api/research/runs")
    assert response.status_code == 503


def test_run_applies_findings_under_confidence_rules(auth_client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        empty = _make_venue(db, name="Jazz au Lac")
        protected = _make_venue(
            db,
            name="Hot Club",
            type=VenueType.jazz_club,
            contact_email="human@hotclub.example",  # human-entered: no marker
        )
        refreshable = _make_venue(
            db,
            name="Old Deadline Fest",
            application_deadline=date(2026, 1, 1),  # in the past
            field_confidence={"application_deadline": "medium"},
        )
        ids = {"empty": empty.id, "protected": protected.id, "old": refreshable.id}

    def fake_batch(payload, progress=None):
        assert {item["id"] for item in payload} >= set(ids.values())
        return [
            {
                "venue_id": ids["empty"],
                "field": "contact_email",
                "value": "booking@jazzaulac.example",
                "confidence": "high",
                "source": "https://jazzaulac.example/contact",
            },
            {
                "venue_id": ids["protected"],
                "field": "contact_email",
                "value": "info@hotclub.example",
                "confidence": "high",
                "source": None,
            },
            {
                "venue_id": ids["old"],
                "field": "application_deadline",
                "value": "2027-01",
                "confidence": "medium",
                "source": "https://fest.example",
            },
            {
                "venue_id": ids["empty"],
                "field": "note",
                "value": "New artistic director since 2026.",
                "confidence": "medium",
                "source": None,
            },
            {
                "venue_id": ids["empty"],
                "field": "application_deadline",
                "value": "next spring",  # unusable format: dropped
                "confidence": "medium",
                "source": None,
            },
        ]

    monkeypatch.setattr(enrichment, "research_batch", fake_batch)
    response = auth_client.post("/api/research/runs")
    assert response.status_code == 202
    run_id = response.json()["id"]

    # TestClient runs background tasks before returning, so the run is done.
    run = auth_client.get(f"/api/research/runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["venues_checked"] >= 3
    assert run["fields_filled"] == 2  # email + refreshed deadline
    # Only the protected email counts as kept — not-yet-flushed findings
    # must not be miscounted as unapplied.
    assert "1 finding kept for review" in run["summary"]

    with SessionLocal() as db:
        filled = db.get(Venue, ids["empty"])
        assert filled.contact_email == "booking@jazzaulac.example"
        assert filled.field_confidence["contact_email"] == "high"
        assert "New artistic director" in filled.research_notes
        assert filled.last_researched is not None

        kept = db.get(Venue, ids["protected"])
        assert kept.contact_email == "human@hotclub.example"  # untouched

        refreshed = db.get(Venue, ids["old"])
        assert refreshed.application_deadline == date(2027, 1, 1)

        findings = db.scalars(select(ResearchFinding)).all()
        by_key = {(f.venue_id, f.field): f for f in findings}
        assert by_key[(ids["protected"], "contact_email")].applied is False
        assert by_key[(ids["empty"], "contact_email")].applied is True
        # The unusable deadline value was dropped, not stored.
        assert (ids["empty"], "application_deadline") not in by_key


def test_second_start_returns_active_run(auth_client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        run = ResearchRun(status="running")
        db.add(run)
        db.commit()
        active_id = run.id
    response = auth_client.post("/api/research/runs")
    assert response.status_code == 202
    assert response.json()["id"] == active_id


def test_stale_running_run_is_failed_on_start(auth_client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        stale = ResearchRun(
            status="running",
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(stale)
        db.commit()
        stale_id = stale.id
    monkeypatch.setattr(enrichment, "research_batch", lambda p, progress=None: [])
    response = auth_client.post("/api/research/runs")
    assert response.status_code == 202
    assert response.json()["id"] != stale_id
    assert auth_client.get(f"/api/research/runs/{stale_id}").json()["status"] == "failed"


def test_selection_skips_complete_and_recent_venues(client):
    with SessionLocal() as db:
        complete = _make_venue(
            db,
            name="Complete Club",
            type=VenueType.jazz_club,
            website="https://c.example",
            contact_email="c@c.example",
            application_method="Email",
        )
        recent = _make_venue(db, name="Recently Checked")
        recent.last_researched = datetime.now(timezone.utc)
        needy = _make_venue(db, name="Needy Fest")
        db.commit()
        selected = enrichment.select_venues(db)
        names = [v.name for v in selected]
        assert "Needy Fest" in names
        assert "Complete Club" not in names
        assert "Recently Checked" not in names


def _apply(db, venue, findings):
    run = ResearchRun()
    db.add(run)
    db.commit()
    db.refresh(run)
    enrichment.apply_findings(db, run, [venue], findings)
    db.commit()
    return run


def test_past_edition_deadline_becomes_note_not_field(client):
    with SessionLocal() as db:
        venue = _make_venue(db, name="Django à Liberchies")
        _apply(
            db,
            venue,
            [
                {
                    "venue_id": venue.id,
                    "field": "application_deadline",
                    "value": "2026-03",  # a past edition
                    "confidence": "medium",
                    "source": None,
                }
            ],
        )
        refreshed = db.get(Venue, venue.id)
        # The past deadline must NOT land in the date field...
        assert refreshed.application_deadline is None
        # ...it is preserved as a reference note instead.
        assert "2026-03" in (refreshed.research_notes or "")
        stored = db.scalars(select(ResearchFinding)).all()
        assert [f.field for f in stored] == ["note"]


def test_past_edition_event_dates_become_note(client):
    with SessionLocal() as db:
        venue = _make_venue(db, name="Jazz sous les Pommiers")
        _apply(
            db,
            venue,
            [
                {
                    "venue_id": venue.id,
                    "field": "event_dates",
                    "value": "3-18 July 2026",
                    "confidence": "medium",
                    "source": None,
                }
            ],
        )
        refreshed = db.get(Venue, venue.id)
        assert refreshed.event_dates is None
        assert "3-18 July 2026" in (refreshed.research_notes or "")


def test_future_dates_are_kept(client):
    with SessionLocal() as db:
        venue = _make_venue(db, name="Future Fest")
        _apply(
            db,
            venue,
            [
                {
                    "venue_id": venue.id,
                    "field": "event_dates",
                    "value": "24-27 June 2027",
                    "confidence": "high",
                    "source": None,
                }
            ],
        )
        refreshed = db.get(Venue, venue.id)
        assert refreshed.event_dates == "24-27 June 2027"


def test_clear_stale_dates_targets_only_claude_filled(auth_client):
    from datetime import date

    with SessionLocal() as db:
        stale = _make_venue(
            db,
            name="Stale Fest",
            status=VenueStatus.researched,
            application_deadline=date(2026, 3, 1),
            event_dates="3-18 July 2026",
            field_confidence={
                "application_deadline": "medium",
                "event_dates": "medium",
            },
        )
        manual = _make_venue(
            db,
            name="Manual Fest",
            application_deadline=date(2026, 4, 1),  # no marker → human-entered
        )
        future = _make_venue(
            db,
            name="Future Fest",
            application_deadline=date(2027, 1, 1),
            field_confidence={"application_deadline": "high"},
        )
        ids = {"stale": stale.id, "manual": manual.id, "future": future.id}

    response = auth_client.post("/api/research/clear-stale-dates")
    assert response.status_code == 200
    body = response.json()
    assert body["cleared"] == 1
    assert body["venues"] == ["Stale Fest"]

    with SessionLocal() as db:
        s = db.get(Venue, ids["stale"])
        assert s.application_deadline is None
        assert s.event_dates is None
        assert s.field_confidence is None
        assert s.status == VenueStatus.discovered

        m = db.get(Venue, ids["manual"])
        assert m.application_deadline == date(2026, 4, 1)  # untouched

        f = db.get(Venue, ids["future"])
        assert f.application_deadline == date(2027, 1, 1)  # untouched


def test_runs_list_returns_findings(auth_client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        venue = _make_venue(db, name="Listed Fest")
        vid = venue.id
    monkeypatch.setattr(
        enrichment,
        "research_batch",
        lambda p, progress=None: [
            {
                "venue_id": vid,
                "field": "website",
                "value": "https://listed.example",
                "confidence": "high",
                "source": "https://listed.example",
            }
        ],
    )
    auth_client.post("/api/research/runs")
    runs = auth_client.get("/api/research/runs").json()
    assert runs and runs[0]["status"] == "completed"
    assert runs[0]["findings"][0]["venue_name"] == "Listed Fest"
