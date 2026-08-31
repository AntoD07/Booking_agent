"""Edit history, the per-device editor identity, and the band member list."""


def _set_editor(client, name):
    r = client.post("/api/auth/editor", json={"name": name})
    assert r.status_code == 200
    return r.json()


def _new_venue(client, name="Sunside"):
    return client.post("/api/venues", json={"name": name}).json()


def test_editor_is_remembered_in_the_session(auth_client):
    # Not chosen yet.
    assert auth_client.get("/api/auth/me").json()["editor"] is None
    body = _set_editor(auth_client, "Anto")
    assert body["editor"] == "Anto"
    # Persists on the session cookie — no need to pick again.
    assert auth_client.get("/api/auth/me").json()["editor"] == "Anto"


def test_create_records_a_created_edit_and_stamps_the_card(auth_client):
    _set_editor(auth_client, "Bastien")
    venue = _new_venue(auth_client)
    assert venue["last_modified_by"] == "Bastien"
    assert venue["last_modified_at"] is not None

    history = auth_client.get(f"/api/venues/{venue['id']}/history").json()
    assert len(history) == 1
    assert history[0]["action"] == "created"
    assert history[0]["editor"] == "Bastien"


def test_field_and_status_edits_are_recorded_with_diffs(auth_client):
    _set_editor(auth_client, "Cris")
    venue = _new_venue(auth_client)
    vid = venue["id"]

    # A pure status move is its own action.
    auth_client.patch(f"/api/venues/{vid}", json={"status": "sent"})
    # A field edit is "updated" and carries the from/to.
    auth_client.patch(
        f"/api/venues/{vid}", json={"contact_email": "book@sunside.example"}
    )

    history = auth_client.get(f"/api/venues/{vid}/history").json()
    actions = [h["action"] for h in history]  # newest first
    assert actions == ["updated", "status", "created"]

    updated = history[0]
    change = updated["changes"][0]
    assert change["field"] == "contact_email"
    assert change["from"] is None
    assert change["to"] == "book@sunside.example"

    status_edit = history[1]
    assert status_edit["changes"][0] == {
        "field": "status",
        "from": "discovered",
        "to": "sent",
    }


def test_noop_patch_records_nothing(auth_client):
    _set_editor(auth_client, "Sacha")
    venue = _new_venue(auth_client, name="Django Bar")
    auth_client.patch(f"/api/venues/{venue['id']}", json={"name": "Django Bar"})
    history = auth_client.get(f"/api/venues/{venue['id']}/history").json()
    assert [h["action"] for h in history] == ["created"]


def test_artist_appearance_edits_are_recorded(auth_client):
    _set_editor(auth_client, "Anto")
    venue = _new_venue(auth_client)
    vid = venue["id"]
    auth_client.post(
        f"/api/venues/{vid}/artists", json={"name": "Rocky Gresset", "year": "2025"}
    )
    added = auth_client.get(f"/api/venues/{vid}/history").json()[0]
    assert added["action"] == "artist_added"
    assert added["changes"]["artist"] == "Rocky Gresset"

    artist_id = auth_client.get(f"/api/venues/{vid}").json()["artists"][0]["artist_id"]
    auth_client.delete(f"/api/venues/{vid}/artists/{artist_id}")
    removed = auth_client.get(f"/api/venues/{vid}/history").json()[0]
    assert removed["action"] == "artist_removed"
    assert removed["changes"]["artist"] == "Rocky Gresset"


def test_history_is_band_scoped(client):
    from tests.test_bands import _login, _register

    _register("Band A", "pw-a")
    _register("Band B", "pw-b")
    a = _login("Band A", "pw-a")
    b = _login("Band B", "pw-b")
    _set_editor(a, "Alice")
    venue = a.post("/api/venues", json={"name": "A Venue"}).json()
    # Band B can't read Band A's card history.
    assert b.get(f"/api/venues/{venue['id']}/history").status_code == 404


def test_editors_list_uses_band_members_then_seen_names(auth_client):
    # Members set on the profile drive the picker, in order.
    auth_client.put(
        "/api/band-profile", json={"members": ["Anto", "Bastien", "Cris", "Sacha"]}
    )
    # A name used in an edit but not on the member list still shows up after.
    _set_editor(auth_client, "Guest")
    auth_client.post("/api/venues", json={"name": "Some Venue"})

    editors = auth_client.get("/api/auth/editors").json()
    assert editors[:4] == ["Anto", "Bastien", "Cris", "Sacha"]
    assert "Guest" in editors
    assert "Claude" not in editors


def test_members_are_cleaned_on_save(auth_client):
    saved = auth_client.put(
        "/api/band-profile",
        json={"members": [" Anto ", "Bastien", "anto", "", "Cris"]},
    ).json()
    # Trimmed, de-duplicated case-insensitively, blanks dropped.
    assert saved["members"] == ["Anto", "Bastien", "Cris"]
