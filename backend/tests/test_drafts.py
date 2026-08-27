from datetime import date

from app import drafting
from app.db import SessionLocal
from app.models import Venue, VenueArtist, VenueStatus, VenueType


def _make_venue(db, band_id, **overrides):
    defaults = {"name": "Jazz au Lac", "type": VenueType.festival, "country": "France"}
    defaults.update(overrides)
    venue = Venue(**defaults, band_id=band_id)
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def _no_key(monkeypatch):
    """Force the placeholder personalisation path (no Claude call)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# --- Band profile ---------------------------------------------------------


def test_profile_created_with_band_defaults(auth_client):
    body = auth_client.get("/api/band-profile").json()
    assert body["band_name"] == "Gipsy Tonic"
    assert body["signature_name"] == "Antony"
    assert body["epk_url"] is None


def test_profile_update_persists(auth_client):
    auth_client.get("/api/band-profile")  # create it
    response = auth_client.put(
        "/api/band-profile",
        json={"epk_url": "https://gipsytonic.com/epk", "phone": "+41 78 679 42 35"},
    )
    assert response.status_code == 200
    assert response.json()["epk_url"] == "https://gipsytonic.com/epk"
    # Band name kept its default (partial update).
    assert response.json()["band_name"] == "Gipsy Tonic"


def test_profile_blank_name_rejected(auth_client):
    auth_client.get("/api/band-profile")
    assert auth_client.put("/api/band-profile", json={"band_name": "  "}).status_code == 422


# --- Generating a draft ---------------------------------------------------


def test_generate_french_draft_moves_card_to_draft_ready(
    auth_client, band, monkeypatch
):
    _no_key(monkeypatch)
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Jazz à Vienne", country="France")
        vid = venue.id

    response = auth_client.post(f"/api/venues/{vid}/drafts")
    assert response.status_code == 201
    draft = response.json()
    assert draft["subject"].startswith("Gipsy Tonic : Candidature Jazz à Vienne 2027")
    # French, fixed prose, and the bracketed hook to fill in by hand.
    assert "On s'appelle Gipsy Tonic" in draft["body"]
    assert "À COMPLÉTER" in draft["body"]
    assert "lors de votre édition 2027" in draft["body"]
    assert draft["status"] == "draft"
    # No key → no web search → no source.
    assert draft["source"] is None

    with SessionLocal() as db:
        assert db.get(Venue, vid).status == VenueStatus.draft_ready


def test_generate_english_for_non_francophone(auth_client, band, monkeypatch):
    _no_key(monkeypatch)
    with SessionLocal() as db:
        venue = _make_venue(
            db, band.id, name="Fasching", country="Sweden", type=VenueType.jazz_club
        )
        vid = venue.id
    body = auth_client.post(f"/api/venues/{vid}/drafts").json()["body"]
    assert "We're Gipsy Tonic" in body
    assert "in 2027" in body  # a club, not a festival edition


def test_generate_uses_profile_links_and_greeting(auth_client, band, monkeypatch):
    _no_key(monkeypatch)
    auth_client.put(
        "/api/band-profile",
        json={
            "video1_url": "https://youtu.be/one",
            "epk_url": "https://gipsytonic.com/epk",
            "website": "gipsytonic.com",
            "email": "booking@gipsytonic.com",
        },
    )
    with SessionLocal() as db:
        venue = _make_venue(
            db, band.id, booking_contact="Marie Dupont, programmation"
        )
        vid = venue.id
    body = auth_client.post(f"/api/venues/{vid}/drafts").json()["body"]
    assert "Bonjour Marie," in body
    assert "https://youtu.be/one" in body
    assert "https://gipsytonic.com/epk" in body
    assert "[lien vidéo 2]" in body  # video2 still unset → placeholder
    assert "booking@gipsytonic.com · gipsytonic.com" in body


def test_generate_personalisation_and_source_from_claude(
    auth_client, band, monkeypatch
):
    monkeypatch.setattr(
        drafting,
        "_research_personalisation",
        lambda venue, language, api_key=None: (
            "J'ai vu que vous aviez programmé le Rosenberg Trio.",
            "https://django-fest.example/2026-lineup",
        ),
    )
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, name="Django Fest")
        vid = venue.id
    draft = auth_client.post(f"/api/venues/{vid}/drafts").json()
    assert "Rosenberg Trio" in draft["body"]
    assert "À COMPLÉTER" not in draft["body"]
    # The page Claude grounded the opening line in is stored on the draft.
    assert draft["source"] == "https://django-fest.example/2026-lineup"


def test_generate_unknown_venue_404(auth_client, monkeypatch):
    _no_key(monkeypatch)
    assert auth_client.post("/api/venues/9999/drafts").status_code == 404


# --- Editing / sending ----------------------------------------------------


def test_patch_body_and_mark_sent_advances_venue(auth_client, band, monkeypatch):
    _no_key(monkeypatch)
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, status=VenueStatus.draft_ready)
        vid = venue.id
    draft_id = auth_client.post(f"/api/venues/{vid}/drafts").json()["id"]

    edited = auth_client.patch(
        f"/api/drafts/{draft_id}", json={"body": "My own final wording."}
    )
    assert edited.status_code == 200
    assert edited.json()["body"] == "My own final wording."

    sent = auth_client.patch(f"/api/drafts/{draft_id}", json={"status": "sent"})
    assert sent.json()["status"] == "sent"
    with SessionLocal() as db:
        venue = db.get(Venue, vid)
        assert venue.status == VenueStatus.sent
        assert venue.last_contact == date.today()


def test_mark_sent_does_not_drag_back_a_confirmed_venue(
    auth_client, band, monkeypatch
):
    _no_key(monkeypatch)
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, status=VenueStatus.confirmed)
        vid = venue.id
    draft_id = auth_client.post(f"/api/venues/{vid}/drafts").json()["id"]
    auth_client.patch(f"/api/drafts/{draft_id}", json={"status": "sent"})
    with SessionLocal() as db:
        # Still confirmed — a sent pitch must not reset a further-along card.
        assert db.get(Venue, vid).status == VenueStatus.confirmed


def test_patch_blank_body_rejected(auth_client, band, monkeypatch):
    _no_key(monkeypatch)
    with SessionLocal() as db:
        vid = _make_venue(db, band.id).id
    draft_id = auth_client.post(f"/api/venues/{vid}/drafts").json()["id"]
    assert auth_client.patch(f"/api/drafts/{draft_id}", json={"body": "  "}).status_code == 422


def test_list_and_delete_drafts(auth_client, band, monkeypatch):
    _no_key(monkeypatch)
    with SessionLocal() as db:
        vid = _make_venue(db, band.id).id
    first = auth_client.post(f"/api/venues/{vid}/drafts").json()["id"]
    auth_client.post(f"/api/venues/{vid}/drafts")
    listed = auth_client.get(f"/api/venues/{vid}/drafts").json()
    assert len(listed) == 2

    assert auth_client.delete(f"/api/drafts/{first}").status_code == 204
    assert len(auth_client.get(f"/api/venues/{vid}/drafts").json()) == 1


# --- Drafting unit logic --------------------------------------------------


def test_appearances_feed_the_hook_prompt(band):
    with SessionLocal() as db:
        venue = _make_venue(db, band.id)
        artist_link = VenueArtist(venue_id=venue.id, year="2019")
        from app.models import Artist

        artist = Artist(name="Rosenberg Trio", band_id=band.id)
        db.add(artist)
        db.flush()
        artist_link.artist_id = artist.id
        db.add(artist_link)
        db.commit()
        db.refresh(venue)
        assert drafting._appearances_text(venue, "fr") == "Rosenberg Trio (2019)"


def test_edition_year_prefers_future_event_year(band):
    with SessionLocal() as db:
        venue = _make_venue(db, band.id, event_dates="24-27 June 2028")
        assert drafting._edition_year(venue) == 2028
        past = _make_venue(db, band.id, name="Old", event_dates="3-18 July 2026")
        assert drafting._edition_year(past) == 2027  # past year ignored → season


def test_first_name_ignores_role_words():
    assert drafting._first_name("Programmation générale") is None
    assert drafting._first_name("Jean-Marc Lefèvre") == "Jean-Marc"
    assert drafting._first_name(None) is None
