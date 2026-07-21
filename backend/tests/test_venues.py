def test_venue_crud(auth_client):
    created = auth_client.post(
        "/api/venues",
        json={
            "name": "Sunside",
            "type": "jazz_club",
            "city": "Paris",
            "country": "France",
        },
    )
    assert created.status_code == 201
    venue = created.json()
    assert venue["status"] == "discovered"

    listed = auth_client.get("/api/venues").json()
    assert [v["name"] for v in listed] == ["Sunside"]

    patched = auth_client.patch(
        f"/api/venues/{venue['id']}",
        json={
            "status": "sent",
            "fit_score": 4.2,
            "region": "Île-de-France",
            "added_by": "Antony",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "sent"
    assert patched.json()["fit_score"] == 4.2
    assert patched.json()["region"] == "Île-de-France"
    assert patched.json()["added_by"] == "Antony"

    assert auth_client.delete(f"/api/venues/{venue['id']}").status_code == 204
    assert auth_client.get(f"/api/venues/{venue['id']}").status_code == 404


def test_invalid_status_rejected(auth_client):
    response = auth_client.post(
        "/api/venues", json={"name": "X", "status": "converted"}
    )
    assert response.status_code == 422


def test_blank_name_rejected_on_create(auth_client):
    assert auth_client.post("/api/venues", json={"name": "   "}).status_code == 422


def test_name_is_stripped(auth_client):
    created = auth_client.post("/api/venues", json={"name": "  Sunside  "})
    assert created.status_code == 201
    assert created.json()["name"] == "Sunside"


def test_blank_or_null_name_rejected_on_patch(auth_client):
    venue = auth_client.post("/api/venues", json={"name": "Sunside"}).json()
    for bad_name in ["", "   ", None]:
        response = auth_client.patch(
            f"/api/venues/{venue['id']}", json={"name": bad_name}
        )
        assert response.status_code == 422
    assert auth_client.get(f"/api/venues/{venue['id']}").json()["name"] == "Sunside"


def test_patch_clears_optional_field_with_null(auth_client):
    venue = auth_client.post(
        "/api/venues", json={"name": "Sunside", "city": "Paris"}
    ).json()
    patched = auth_client.patch(f"/api/venues/{venue['id']}", json={"city": None})
    assert patched.status_code == 200
    assert patched.json()["city"] is None
