from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import enrichment
from app.db import SessionLocal
from app.models import ResearchFinding, ResearchRun, Venue, VenueStatus, VenueType


def _make_venue(db, band_id, **overrides):
    defaults = {"name": "Testival", "type": VenueType.festival}
    defaults.update(overrides)
    venue = Venue(**defaults, band_id=band_id)
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def test_start_requires_api_key(auth_client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = auth_client.post("/api/research/runs")
    assert response.status_code == 503


def test_run_applies_findings_under_confidence_rules(auth_client, band, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        empty = _make_venue(db, band.id, name="Jazz au Lac")
        protected = _make_venue(
            db,
            band.id,
            name="Hot Club",
            type=VenueType.jazz_club,
            contact_email="human@hotclub.example",  # human-entered: no marker
        )
        refreshable = _make_venue(
            db,
            band.id,
            name="Old Deadline Fest",
            application_deadline=date(2026, 1, 1),  # in the past
            field_confidence={"application_deadline": "medium"},
        )
        ids = {"empty": empty.id, "protected": protected.id, "old": refreshable.id}

    def fake_batch(payload, progress=None, api_key=None, reference_artists=None):
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
    # The protected email differs from the find: it surfaces as a conflict
    # to verify (and not-yet-flushed findings must not be miscounted).
    assert "1 conflict with the card to verify" in run["summary"]

    with SessionLocal() as db:
        filled = db.get(Venue, ids["empty"])
        assert filled.contact_email == "booking@jazzaulac.example"
        assert filled.field_confidence["contact_email"] == "high"
        # The finding's source is stored per field for the sheet's dot link.
        assert filled.field_sources["contact_email"] == (
            "https://jazzaulac.example/contact"
        )
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


def test_second_start_returns_active_run(auth_client, band, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        run = ResearchRun(status="running", band_id=band.id)
        db.add(run)
        db.commit()
        active_id = run.id
    response = auth_client.post("/api/research/runs")
    assert response.status_code == 202
    assert response.json()["id"] == active_id


def test_stale_running_run_is_failed_on_start(auth_client, band, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        stale = ResearchRun(
            status="running",
            band_id=band.id,
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(stale)
        db.commit()
        stale_id = stale.id
    monkeypatch.setattr(
        enrichment, "research_batch", lambda p, progress=None, api_key=None, reference_artists=None: []
    )
    response = auth_client.post("/api/research/runs")
    assert response.status_code == 202
    assert response.json()["id"] != stale_id
    assert auth_client.get(f"/api/research/runs/{stale_id}").json()["status"] == "failed"


def test_selection_skips_complete_and_recent_venues(band):
    with SessionLocal() as db:
        complete = _make_venue(
            db,
            band.id,
            name="Complete Club",
            type=VenueType.jazz_club,
            website="https://c.example",
            contact_email="c@c.example",
            application_method="Email",
        )
        recent = _make_venue(db, band.id, name="Recently Checked")
        recent.last_researched = datetime.now(timezone.utc)
        needy = _make_venue(db, band.id, name="Needy Fest")
        db.commit()
        selected = enrichment.select_venues(db, band.id)
        names = [v.name for v in selected]
        assert "Needy Fest" in names
        assert "Complete Club" not in names
        assert "Recently Checked" not in names


def _apply(db, band_id, venue, findings):
    run = ResearchRun(band_id=band_id)
    db.add(run)
    db.commit()
    db.refresh(run)
    enrichment.apply_findings(db, run, [venue], findings)
    db.commit()
    return run


def test_past_edition_deadline_becomes_note_not_field(band):
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Django à Liberchies")
        _apply(
            db,
            band.id,
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


def test_past_edition_event_dates_become_note(band):
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Jazz sous les Pommiers")
        _apply(
            db,
            band.id,
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


def test_future_dates_are_kept(band):
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Future Fest")
        _apply(
            db,
            band.id,
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


def test_clear_stale_dates_targets_only_claude_filled(auth_client, band):
    from datetime import date

    with SessionLocal() as db:
        stale = _make_venue(
            db,
            band.id,
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
            band.id,
            name="Manual Fest",
            application_deadline=date(2026, 4, 1),  # no marker → human-entered
        )
        future = _make_venue(
            db,
            band.id,
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


def test_overlong_value_is_capped_not_crashed(band):
    long_method = "Curated booking via the resort; " + "detail " * 60  # >200 chars
    assert len(long_method) > 200
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Enghien Jazz")
        _apply(
            db,
            band.id,
            venue,
            [
                {
                    "venue_id": venue.id,
                    "field": "application_method",
                    "value": long_method,
                    "confidence": "medium",
                    "source": None,
                }
            ],
        )
        refreshed = db.get(Venue, venue.id)
        assert refreshed.application_method is not None
        assert len(refreshed.application_method) <= 200
        # The stored finding reflects the capped value, so it fits its column too.
        stored = db.scalars(select(ResearchFinding)).all()
        assert stored and len(stored[0].new_value) <= 200


def test_orphaned_running_run_failed_at_startup(band):
    from app.routers import research

    with SessionLocal() as db:
        run = ResearchRun(status="running", note="mid-search", band_id=band.id)
        db.add(run)
        db.commit()
        run_id = run.id
    research.fail_running_runs()
    with SessionLocal() as db:
        recovered = db.get(ResearchRun, run_id)
        assert recovered.status == "failed"
        assert recovered.note is None
        assert "interrupted" in recovered.error


def test_poll_recovers_a_stale_run(auth_client, band):
    with SessionLocal() as db:
        stale = ResearchRun(
            status="running",
            band_id=band.id,
            started_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(stale)
        db.commit()
        stale_id = stale.id
    # Simply polling the run heals it — no new search needed.
    body = auth_client.get(f"/api/research/runs/{stale_id}").json()
    assert body["status"] == "failed"


def test_runs_list_returns_findings(auth_client, band, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Listed Fest")
        vid = venue.id
    monkeypatch.setattr(
        enrichment,
        "research_batch",
        lambda p, progress=None, api_key=None, reference_artists=None: [
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


def test_artist_finding_lands_in_research_notes(band):
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Le Duc des Lombards")
        _apply(
            db,
            band.id,
            venue,
            [
                {
                    "venue_id": venue.id,
                    "field": "artist",
                    "value": "Mustaka (2023)",
                    "confidence": "high",
                    "source": "https://duc.example/archive",
                }
            ],
        )
        refreshed = db.get(Venue, venue.id)
        # The appearance is recorded in the notes, with its source.
        assert "A joué ici : Mustaka (2023)" in refreshed.research_notes
        assert "https://duc.example/archive" in refreshed.research_notes
        stored = db.scalars(select(ResearchFinding)).all()
        assert [f.field for f in stored] == ["artist"]
        assert stored[0].applied is True


def test_artist_already_in_notes_is_not_duplicated(band):
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Sunset Sunside")
        finding = {
            "venue_id": venue.id,
            "field": "artist",
            "value": "Djangologists",
            "confidence": "medium",
            "source": None,
        }
        _apply(db, band.id, venue, [finding])
        _apply(db, band.id, db.get(Venue, venue.id), [finding])  # found again
        refreshed = db.get(Venue, venue.id)
        assert refreshed.research_notes.lower().count("djangologists") == 1
        artist_findings = [
            f for f in db.scalars(select(ResearchFinding)) if f.field == "artist"
        ]
        # Both findings recorded; the repeat marked not-applied.
        assert sorted(f.applied for f in artist_findings) == [False, True]


def test_reference_artist_names_are_band_scoped(band):
    from app.models import Artist

    with SessionLocal() as db:
        db.add(Artist(name="Mustaka", band_id=band.id))
        db.commit()
        names = enrichment.reference_artist_names(db, band.id)
        assert names == ["Mustaka"]
        assert enrichment.reference_artist_names(db, band.id + 999) == []


def test_run_targets_the_requested_venue_only(auth_client, band, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        target = _make_venue(db, band.id, name="Cible Club")
        other = _make_venue(db, band.id, name="Autre Fest")
        # Even a fully-complete, recently-researched venue is researched when
        # asked for explicitly — the card button must always work.
        target.website = "https://cible.example"
        target.contact_email = "prog@cible.example"
        target.application_method = "Email"
        target.last_researched = datetime.now(timezone.utc)
        db.commit()
        ids = {"target": target.id, "other": other.id}

    seen = {}

    def fake_batch(payload, progress=None, api_key=None, reference_artists=None):
        seen["ids"] = [item["id"] for item in payload]
        return [
            {
                "venue_id": ids["target"],
                "field": "event_dates",
                "value": "24-27 June 2027",
                "confidence": "high",
                "source": "https://cible.example/2027",
            }
        ]

    monkeypatch.setattr(enrichment, "research_batch", fake_batch)
    response = auth_client.post(
        "/api/research/runs", json={"venue_id": ids["target"]}
    )
    assert response.status_code == 202
    run = auth_client.get(f"/api/research/runs/{response.json()['id']}").json()
    assert run["status"] == "completed"
    assert seen["ids"] == [ids["target"]]  # only the requested venue
    with SessionLocal() as db:
        assert db.get(Venue, ids["target"]).event_dates == "24-27 June 2027"


def test_run_rejects_another_bands_venue(auth_client, band, monkeypatch):
    from app.models import Band
    from app.passwords import hash_password

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with SessionLocal() as db:
        rival = Band(name="Rival Band", password_hash=hash_password("x"))
        db.add(rival)
        db.flush()
        foreign = _make_venue(db, rival.id, name="Foreign Venue")
        db.commit()
        foreign_id = foreign.id
    response = auth_client.post(
        "/api/research/runs", json={"venue_id": foreign_id}
    )
    assert response.status_code == 404


def test_program_link_findings_land_in_notes(band):
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Lac Léman Jazz")
        _apply(
            db,
            band.id,
            venue,
            [
                {
                    "venue_id": venue.id,
                    "field": "program_link",
                    "value": "2026: https://llj.example/programme-2026",
                    "confidence": "high",
                    "source": "https://llj.example/programme-2026",
                },
                {
                    "venue_id": venue.id,
                    "field": "program_link",
                    "value": "2025 - https://llj.example/edition/2025",
                    "confidence": "high",
                    "source": None,
                },
                {
                    "venue_id": venue.id,
                    "field": "program_link",
                    "value": "no url here",  # unusable: dropped
                    "confidence": "medium",
                    "source": None,
                },
            ],
        )
        refreshed = db.get(Venue, venue.id)
        notes = refreshed.research_notes or ""
        assert "— Programmation 2026 : https://llj.example/programme-2026" in notes
        assert "— Programmation 2025 : https://llj.example/edition/2025" in notes
        stored = [
            f for f in db.scalars(select(ResearchFinding)) if f.field == "program_link"
        ]
        assert len(stored) == 2  # the unusable one was not stored
        assert all(f.applied for f in stored)

        # A re-run finding the same page again is recorded but not re-applied.
        _apply(
            db,
            band.id,
            db.get(Venue, venue.id),
            [
                {
                    "venue_id": venue.id,
                    "field": "program_link",
                    "value": "2026: https://llj.example/programme-2026",
                    "confidence": "high",
                    "source": None,
                }
            ],
        )
        notes = db.get(Venue, venue.id).research_notes or ""
        assert notes.count("Programmation 2026") == 1
