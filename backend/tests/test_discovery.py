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


@pytest.fixture()
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def test_discover_returns_parsed_suggestions(auth_client, api_key, monkeypatch):
    monkeypatch.setattr(
        discovery, "_create_message", lambda client, messages: _response(CLAUDE_REPLY)
    )
    response = auth_client.post(
        "/api/discovery", json={"artists": ["Rhythm Future Quartet"]}
    )
    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
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
        discovery, "_create_message", lambda client, messages: _response(CLAUDE_REPLY)
    )
    response = auth_client.post(
        "/api/discovery", json={"artists": ["Rhythm Future Quartet"]}
    )
    assert response.status_code == 200
    suggestions = {s["name"]: s for s in response.json()["suggestions"]}
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

    def fake_create(client, messages):
        calls.append(list(messages))
        return responses[len(calls) - 1]

    monkeypatch.setattr(discovery, "_create_message", fake_create)
    response = auth_client.post(
        "/api/discovery", json={"artists": ["Rhythm Future Quartet"]}
    )
    assert response.status_code == 200
    assert len(calls) == 2
    # The paused assistant turn is re-sent so the server can resume
    assert calls[1][-1]["role"] == "assistant"
    assert len(response.json()["suggestions"]) == 2


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
        discovery, "_create_message", lambda client, messages: _response(CLAUDE_REPLY)
    )
    response = auth_client.post(
        # Case-insensitive name match; free-text names without a row are fine
        "/api/discovery",
        json={"artists": ["rhythm future quartet", "Someone Unknown"]},
    )
    assert response.status_code == 200

    artists = {a["name"]: a for a in auth_client.get("/api/artists").json()}
    assert artists["Rhythm Future Quartet"]["last_scanned"] is not None
    assert artists["Opal Ocean"]["last_scanned"] is None
    assert "Someone Unknown" not in artists


def test_discover_unusable_reply_is_502(auth_client, api_key, monkeypatch):
    monkeypatch.setattr(
        discovery,
        "_create_message",
        lambda client, messages: _response("Sorry, I found nothing."),
    )
    response = auth_client.post("/api/discovery", json={"artists": ["Someone"]})
    assert response.status_code == 502


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

    def fake_create(client, messages):
        prompts.append(messages[0]["content"])
        return _response(GENERAL_REPLY)

    monkeypatch.setattr(discovery, "_create_message", fake_create)
    response = auth_client.post(
        "/api/discovery/general",
        json={
            "region": "south of France",
            "event_type": "festival",
            "period": "summer 2027",
        },
    )
    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
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
        discovery, "_create_message", lambda client, messages: _response(GENERAL_REPLY)
    )
    response = auth_client.post(
        "/api/discovery/general", json={"region": "Occitanie"}
    )
    assert response.status_code == 200
    suggestions = {s["name"]: s for s in response.json()["suggestions"]}
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


def test_accept_without_artist(auth_client):
    response = auth_client.post(
        "/api/discovery/accept", json={"name": "Le Petit Duc"}
    )
    assert response.status_code == 201
    venue = response.json()
    assert venue["source"] == "Scouting"
    assert venue["artists"] == []
