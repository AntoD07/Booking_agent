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
            "/api/discovery", json={"artists": ["A", "B", "C"]}
        ).status_code
        == 422
    )


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


def test_accept_without_artist(auth_client):
    response = auth_client.post(
        "/api/discovery/accept", json={"name": "Le Petit Duc"}
    )
    assert response.status_code == 201
    venue = response.json()
    assert venue["source"] == "Scouting"
    assert venue["artists"] == []
