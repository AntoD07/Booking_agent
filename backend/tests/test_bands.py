"""Each band sees and touches only its own data."""

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Band
from app.passwords import hash_password


def _register(name: str, password: str) -> None:
    with SessionLocal() as db:
        db.add(Band(name=name, password_hash=hash_password(password)))
        db.commit()


def _login(name: str, password: str) -> TestClient:
    c = TestClient(app)
    response = c.post(
        "/api/auth/login", json={"band_name": name, "password": password}
    )
    assert response.status_code == 200
    return c


def test_bands_are_isolated(client):
    _register("Band A", "pw-a")
    _register("Band B", "pw-b")
    a = _login("Band A", "pw-a")
    b = _login("Band B", "pw-b")

    venue_a = a.post("/api/venues", json={"name": "A Venue"}).json()
    a.post("/api/artists", json={"name": "A Artist"})
    b.post("/api/venues", json={"name": "B Venue"})

    # Listing returns only the caller's own rows.
    assert [v["name"] for v in a.get("/api/venues").json()] == ["A Venue"]
    assert [v["name"] for v in b.get("/api/venues").json()] == ["B Venue"]
    assert [x["name"] for x in a.get("/api/artists").json()] == ["A Artist"]
    assert b.get("/api/artists").json() == []

    # Band B cannot read, edit, or delete Band A's venue even by guessing its id.
    vid = venue_a["id"]
    assert b.get(f"/api/venues/{vid}").status_code == 404
    assert b.patch(f"/api/venues/{vid}", json={"name": "hijacked"}).status_code == 404
    assert b.delete(f"/api/venues/{vid}").status_code == 404

    # Band A's venue is untouched.
    assert a.get(f"/api/venues/{vid}").json()["name"] == "A Venue"


def test_same_venue_name_allowed_across_bands(client):
    _register("Band A", "pw-a")
    _register("Band B", "pw-b")
    a = _login("Band A", "pw-a")
    b = _login("Band B", "pw-b")

    assert a.post("/api/venues", json={"name": "New Morning"}).status_code == 201
    # A different band using the same venue name is fine — they're separate rows.
    assert b.post("/api/venues", json={"name": "New Morning"}).status_code == 201
    assert len(a.get("/api/venues").json()) == 1
    assert len(b.get("/api/venues").json()) == 1


def test_profiles_and_drafts_are_per_band(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # placeholder hook, no call
    _register("Band A", "pw-a")
    _register("Band B", "pw-b")
    a = _login("Band A", "pw-a")
    b = _login("Band B", "pw-b")

    # Each band's profile defaults to its own name and edits independently.
    assert a.get("/api/band-profile").json()["band_name"] == "Band A"
    assert b.get("/api/band-profile").json()["band_name"] == "Band B"
    a.put("/api/band-profile", json={"signature_name": "Alice"})
    assert b.get("/api/band-profile").json()["signature_name"] != "Alice"

    # A draft belongs to the band that made it; the other band can't see it.
    venue_a = a.post("/api/venues", json={"name": "A Venue"}).json()
    draft = a.post(f"/api/venues/{venue_a['id']}/drafts").json()
    assert b.get(f"/api/venues/{venue_a['id']}/drafts").status_code == 404
    assert b.patch(f"/api/drafts/{draft['id']}", json={"body": "x"}).status_code == 404
    assert b.delete(f"/api/drafts/{draft['id']}").status_code == 404
    assert a.get(f"/api/venues/{venue_a['id']}/drafts").json()[0]["id"] == draft["id"]
