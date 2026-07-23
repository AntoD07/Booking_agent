from types import SimpleNamespace

import pytest

from app import discovery

CLAUDE_REPLY = """\
I searched the manouche circuit and found these venues.

```json
[
  {
    "name": "Festival Django Reinhardt",
    "type": "festival",
    "city": "Fontainebleau",
    "country": "France",
    "website": "https://www.festivaldjangoreinhardt.com",
    "artist": "Rhythm Future Quartet",
    "source_url": "https://example.com/lineup-2025"
  },
  {
    "name": "Sunset-Sunside",
    "type": "jazz club",
    "city": "Paris",
    "country": "France",
    "website": "https://www.sunset-sunside.com",
    "artist": "Rhythm Future Quartet",
    "source_url": null
  },
  {
    "name": "",
    "type": "venue",
    "city": null,
    "country": null,
    "website": null,
    "artist": null,
    "source_url": null
  }
]
```"""


def _response(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
    )


@pytest.fixture(autouse=True)
def _no_real_api_key(monkeypatch):
    # Accepting a venue schedules real enrichment when a key is present;
    # never let a developer's exported key leak API calls into tests.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture()
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

def _scan(client, path, payload):
    """Start a scan and return its finished job (TestClient runs background
    tasks before the POST returns, so the job is already terminal)."""
    started = client.post(path, json=payload)
    assert started.status_code == 202
    job = client.get(f"/api/discovery/jobs/{started.json()['job_id']}")
    assert job.status_code == 200
    return job.json()



def test_discover_returns_parsed_suggestions(auth_client, api_key, monkeypatch):
    monkeypatch.setattr(
        discovery, "_create_message", lambda client, messages, *a, **kw: _response(CLAUDE_REPLY)
    )
    job = _scan(auth_client, "/api/discovery", {"artists": ["Rhythm Future Quartet"]})
    assert job["status"] == "done"
    suggestions = job["suggestions"]
    # The blank-name entry is dropped
    assert [s["name"] for s in suggestions] == [
        "Festival Django Reinhardt",
        "Sunset-Sunside",
    ]
    festival, club = suggestions
    assert festival["type"] == "festival"
    assert festival["artist"] == "Rhythm Future Quartet"
    assert festival["source_url"] == "https://example.com/lineup-2025"
    assert festival["already_in_pipeline"] is False
    # "jazz club" is coerced to the enum value
    assert club["type"] == "jazz_club"
    assert club["source_url"] is None


def test_discover_marks_venues_already_in_pipeline(auth_client, api_key, monkeypatch):
    created = auth_client.post(
        "/api/venues",
        json={"name": "Django Reinhardt Festival", "type": "festival"},
    )
    assert created.status_code == 201
    venue_id = created.json()["id"]

    monkeypatch.setattr(
        discovery, "_create_message", lambda client, messages, *a, **kw: _response(CLAUDE_REPLY)
    )
    job = _scan(auth_client, "/api/discovery", {"artists": ["Rhythm Future Quartet"]})
    suggestions = {s["name"]: s for s in job["suggestions"]}
    # Same words in a different order still count as a match
    match = suggestions["Festival Django Reinhardt"]
    assert match["already_in_pipeline"] is True
    assert match["matched_venue_id"] == venue_id
    assert match["matched_venue_name"] == "Django Reinhardt Festival"
    assert suggestions["Sunset-Sunside"]["already_in_pipeline"] is False


def test_discover_continues_after_pause_turn(auth_client, api_key, monkeypatch):
    responses = [
        _response("Still searching…", stop_reason="pause_turn"),
        _response(CLAUDE_REPLY),
    ]
    calls = []

    def fake_create(client, messages, *args, **kwargs):
        calls.append(list(messages))
        return responses[len(calls) - 1]

    monkeypatch.setattr(discovery, "_create_message", fake_create)
    job = _scan(auth_client, "/api/discovery", {"artists": ["Rhythm Future Quartet"]})
    assert job["status"] == "done"
    assert len(calls) == 2
    # The paused assistant turn is re-sent so the server can resume
    assert calls[1][-1]["role"] == "assistant"
    assert len(job["suggestions"]) == 2


def test_discover_requires_api_key(auth_client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = auth_client.post("/api/discovery", json={"artists": ["Someone"]})
    assert response.status_code == 503


def test_discover_validates_artist_count(auth_client, api_key):
    assert (
        auth_client.post("/api/discovery", json={"artists": []}).status_code == 422
    )
    assert (
        auth_client.post("/api/discovery", json={"artists": ["  "]}).status_code == 422
    )
    assert (
        auth_client.post(
            "/api/discovery", json={"artists": ["A", "B", "C", "D", "E", "F"]}
        ).status_code
        == 422
    )


def test_discover_stamps_last_scanned_on_known_artists(
    auth_client, api_key, monkeypatch
):
    scanned = auth_client.post(
        "/api/artists", json={"name": "Rhythm Future Quartet"}
    )
    other = auth_client.post("/api/artists", json={"name": "Opal Ocean"})
    assert scanned.status_code == 201 and other.status_code == 201

    monkeypatch.setattr(
        discovery, "_create_message", lambda client, messages, *a, **kw: _response(CLAUDE_REPLY)
    )
    # Case-insensitive name match; free-text names without a row are fine
    job = _scan(
        auth_client,
        "/api/discovery",
        {"artists": ["rhythm future quartet", "Someone Unknown"]},
    )
    assert job["status"] == "done"

    artists = {a["name"]: a for a in auth_client.get("/api/artists").json()}
    assert artists["Rhythm Future Quartet"]["last_scanned"] is not None
    assert artists["Opal Ocean"]["last_scanned"] is None
    assert "Someone Unknown" not in artists


def test_discover_unusable_reply_fails_the_job(auth_client, api_key, monkeypatch):
    monkeypatch.setattr(
        discovery,
        "_create_message",
        lambda client, messages, *a, **kw: _response("Sorry, I found nothing."),
    )
    job = _scan(auth_client, "/api/discovery", {"artists": ["Someone"]})
    assert job["status"] == "failed"
    assert "Discovery failed" in job["error"]
    assert job["suggestions"] is None


def test_unknown_scan_job_is_404(auth_client):
    assert auth_client.get("/api/discovery/jobs/nope").status_code == 404


def test_discover_requires_auth(client):
    response = client.post("/api/discovery", json={"artists": ["Someone"]})
    assert response.status_code == 401


def test_accept_creates_discovered_venue_with_artist_link(auth_client):
    response = auth_client.post(
        "/api/discovery/accept",
        json={
            "name": "Sunset-Sunside",
            "type": "jazz_club",
            "city": "Paris",
            "country": "France",
            "website": "https://www.sunset-sunside.com",
            "artist": "Rhythm Future Quartet",
            "source_url": "https://example.com/lineup-2025",
        },
    )
    assert response.status_code == 201
    venue = response.json()
    assert venue["status"] == "discovered"
    assert venue["source"] == "Scouting — Rhythm Future Quartet played here"
    assert "https://example.com/lineup-2025" in venue["research_notes"]
    assert venue["added_by"] == "Claude"
    assert [a["name"] for a in venue["artists"]] == ["Rhythm Future Quartet"]

    artists = auth_client.get("/api/artists").json()
    assert [a["name"] for a in artists] == ["Rhythm Future Quartet"]


def test_accept_reuses_existing_artist(auth_client):
    created = auth_client.post(
        "/api/artists", json={"name": "Rhythm Future Quartet"}
    )
    assert created.status_code == 201
    artist_id = created.json()["id"]

    response = auth_client.post(
        "/api/discovery/accept",
        json={"name": "La Chope des Puces", "artist": "Rhythm Future Quartet"},
    )
    assert response.status_code == 201
    assert response.json()["artists"][0]["artist_id"] == artist_id
    assert len(auth_client.get("/api/artists").json()) == 1


GENERAL_REPLY = """\
Here is what is programmed in that region.

```json
[
  {
    "name": "Jazz in Marciac",
    "type": "festival",
    "city": "Marciac",
    "country": "France",
    "website": "https://www.jazzinmarciac.com",
    "event_dates": "Late July to mid-August 2027",
    "source_url": "https://example.com/marciac-2027"
  },
  {
    "name": "Le Petit Duc",
    "type": "venue",
    "city": "Aix-en-Provence",
    "country": "France",
    "website": null,
    "event_dates": null,
    "source_url": null
  }
]
```"""


def test_general_scan_returns_suggestions(auth_client, api_key, monkeypatch):
    prompts = []

    def fake_create(client, messages, *args, **kwargs):
        prompts.append(messages[0]["content"])
        return _response(GENERAL_REPLY)

    monkeypatch.setattr(discovery, "_create_message", fake_create)
    job = _scan(
        auth_client,
        "/api/discovery/general",
        {
            "region": "south of France",
            "event_type": "festival",
            "period": "summer 2027",
        },
    )
    assert job["status"] == "done"
    suggestions = job["suggestions"]
    assert [s["name"] for s in suggestions] == ["Jazz in Marciac", "Le Petit Duc"]
    assert suggestions[0]["event_dates"] == "Late July to mid-August 2027"
    assert suggestions[0]["artist"] is None
    # The form parameters shape the prompt
    assert "festivals" in prompts[0]
    assert "south of France" in prompts[0]
    assert "during summer 2027" in prompts[0]


def test_general_scan_marks_venues_already_in_pipeline(
    auth_client, api_key, monkeypatch
):
    created = auth_client.post("/api/venues", json={"name": "Jazz in Marciac"})
    assert created.status_code == 201

    monkeypatch.setattr(
        discovery, "_create_message", lambda client, messages, *a, **kw: _response(GENERAL_REPLY)
    )
    job = _scan(auth_client, "/api/discovery/general", {"region": "Occitanie"})
    suggestions = {s["name"]: s for s in job["suggestions"]}
    assert suggestions["Jazz in Marciac"]["already_in_pipeline"] is True
    assert suggestions["Le Petit Duc"]["already_in_pipeline"] is False


def test_general_scan_requires_region(auth_client, api_key):
    assert (
        auth_client.post("/api/discovery/general", json={"region": "  "}).status_code
        == 422
    )


def test_general_scan_requires_api_key(auth_client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = auth_client.post(
        "/api/discovery/general", json={"region": "Belgium"}
    )
    assert response.status_code == 503


def test_accept_with_scan_source_and_event_dates(auth_client):
    response = auth_client.post(
        "/api/discovery/accept",
        json={
            "name": "Jazz in Marciac",
            "type": "festival",
            "city": "Marciac",
            "country": "France",
            "event_dates": "Late July to mid-August 2027",
            "source": "General scan — festivals in the south of France",
            "source_url": "https://example.com/marciac-2027",
        },
    )
    assert response.status_code == 201
    venue = response.json()
    assert venue["status"] == "discovered"
    assert venue["source"] == "General scan — festivals in the south of France"
    assert venue["event_dates"] == "Late July to mid-August 2027"
    assert venue["artists"] == []


def test_ping_reports_connection(auth_client, api_key, monkeypatch):
    monkeypatch.setattr(
        discovery, "ping", lambda: {"ok": True, "model": "claude-opus-4-8", "seconds": 1.2}
    )
    response = auth_client.get("/api/discovery/ping")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_ping_requires_api_key(auth_client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert auth_client.get("/api/discovery/ping").status_code == 503


def test_accept_matches_artist_case_insensitively(auth_client):
    created = auth_client.post("/api/artists", json={"name": "Die Drahtzieher"})
    assert created.status_code == 201
    artist_id = created.json()["id"]

    response = auth_client.post(
        "/api/discovery/accept",
        json={"name": "Porgy & Bess", "artist": "die drahtzieher"},
    )
    assert response.status_code == 201
    assert response.json()["artists"][0]["artist_id"] == artist_id
    # No duplicate row was created
    assert len(auth_client.get("/api/artists").json()) == 1


ENRICH_REPLY = """\
I researched the venue. Here is the card.

```json
{
  "region": {"value": "Occitanie", "confidence": "high"},
  "website": {"value": "https://www.jazzinmarciac.com", "confidence": "high"},
  "booking_contact": {"value": "Programming director", "confidence": "medium"},
  "contact_email": {"value": "prog@jazzinmarciac.com", "confidence": "medium"},
  "application_method": null,
  "application_url": {"value": "https://www.jazzinmarciac.com/contact", "confidence": "wild-guess"},
  "application_deadline": {"value": "2027-01-15", "confidence": "medium"},
  "event_dates": {"value": "Late July 2027", "confidence": "high"},
  "research_notes": {"value": "Major jazz festival with a swing stage.", "confidence": "high"}
}
```"""


def test_parse_enrichment():
    found = discovery._parse_enrichment(ENRICH_REPLY)
    assert found["region"] == ("Occitanie", "high")
    # Unknown confidence levels are coerced to low, null fields dropped
    assert found["application_url"][1] == "low"
    assert "application_method" not in found
    # The deadline is parsed into a real date
    from datetime import date

    assert found["application_deadline"] == (date(2027, 1, 15), "medium")


def test_accept_enriches_empty_fields_only(auth_client, api_key, monkeypatch):
    from datetime import date

    monkeypatch.setattr(
        discovery,
        "run_enrichment",
        lambda *a, **kw: {
            "region": ("Occitanie", "high"),
            "website": ("https://wrong.example", "high"),
            "contact_email": ("prog@jazzinmarciac.com", "medium"),
            "application_deadline": (date(2027, 1, 15), "medium"),
            "research_notes": ("Major jazz festival with a swing stage.", "high"),
        },
    )
    created = auth_client.post(
        "/api/discovery/accept",
        json={
            "name": "Jazz in Marciac",
            "type": "festival",
            "city": "Marciac",
            "country": "France",
            "website": "https://www.jazzinmarciac.com",
            "source_url": "https://example.com/lineup",
        },
    )
    assert created.status_code == 201

    venue = auth_client.get(f"/api/venues/{created.json()['id']}").json()
    # Empty fields were filled with confidence stamps
    assert venue["region"] == "Occitanie"
    assert venue["contact_email"] == "prog@jazzinmarciac.com"
    assert venue["application_deadline"] == "2027-01-15"
    assert venue["field_confidence"]["region"] == "high"
    assert venue["field_confidence"]["contact_email"] == "medium"
    # The suggestion's website was NOT overwritten
    assert venue["website"] == "https://www.jazzinmarciac.com"
    assert "website" not in venue["field_confidence"]
    # Research notes are appended to the source note
    assert "Source: https://example.com/lineup" in venue["research_notes"]
    assert "Major jazz festival" in venue["research_notes"]


def test_accept_survives_enrichment_failure(auth_client, api_key, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("Claude had a bad day")

    monkeypatch.setattr(discovery, "run_enrichment", boom)
    created = auth_client.post(
        "/api/discovery/accept", json={"name": "Le Petit Duc"}
    )
    assert created.status_code == 201
    venue = auth_client.get(f"/api/venues/{created.json()['id']}").json()
    assert venue["name"] == "Le Petit Duc"
    assert venue["field_confidence"] in (None, {})


def test_accept_without_artist(auth_client):
    response = auth_client.post(
        "/api/discovery/accept", json={"name": "Le Petit Duc"}
    )
    assert response.status_code == 201
    venue = response.json()
    assert venue["source"] == "Scouting"
    assert venue["artists"] == []
