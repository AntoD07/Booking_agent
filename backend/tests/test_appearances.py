def _create_venue(auth_client, name="Sunside"):
    return auth_client.post("/api/venues", json={"name": name}).json()


def test_add_list_and_remove_appearance(auth_client):
    venue = _create_venue(auth_client)

    added = auth_client.post(
        f"/api/venues/{venue['id']}/artists",
        json={"name": "Rocky Gresset Trio", "year": "2025"},
    )
    assert added.status_code == 200
    artists = added.json()["artists"]
    assert [(a["name"], a["year"]) for a in artists] == [("Rocky Gresset Trio", "2025")]

    # The artist is created as a proper reference artist.
    artist_names = [a["name"] for a in auth_client.get("/api/artists").json()]
    assert "Rocky Gresset Trio" in artist_names

    fetched = auth_client.get(f"/api/venues/{venue['id']}").json()
    assert fetched["artists"][0]["year"] == "2025"

    artist_id = artists[0]["artist_id"]
    removed = auth_client.delete(f"/api/venues/{venue['id']}/artists/{artist_id}")
    assert removed.status_code == 204
    assert auth_client.get(f"/api/venues/{venue['id']}").json()["artists"] == []
    # Removing the appearance keeps the artist itself.
    artist_names = [a["name"] for a in auth_client.get("/api/artists").json()]
    assert "Rocky Gresset Trio" in artist_names


def test_reposting_same_artist_updates_year_not_duplicates(auth_client):
    venue = _create_venue(auth_client)
    auth_client.post(
        f"/api/venues/{venue['id']}/artists", json={"name": "Duo Manouche"}
    )
    updated = auth_client.post(
        f"/api/venues/{venue['id']}/artists",
        json={"name": "Duo Manouche", "year": "2024 & 2025"},
    )
    artists = updated.json()["artists"]
    assert len(artists) == 1
    assert artists[0]["year"] == "2024 & 2025"


def test_appearance_requires_artist_name(auth_client):
    venue = _create_venue(auth_client)
    response = auth_client.post(
        f"/api/venues/{venue['id']}/artists", json={"name": "  ", "year": "2025"}
    )
    assert response.status_code == 422


def test_deleting_venue_removes_its_appearances(auth_client):
    venue = _create_venue(auth_client)
    auth_client.post(
        f"/api/venues/{venue['id']}/artists", json={"name": "Trio Swing"}
    )
    assert auth_client.delete(f"/api/venues/{venue['id']}").status_code == 204
    artist_names = [a["name"] for a in auth_client.get("/api/artists").json()]
    assert "Trio Swing" in artist_names