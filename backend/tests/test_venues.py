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
        f"/api/venues/{venue['id']}", json={"status": "sent", "fit_score": 4.2}
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "sent"
    assert patched.json()["fit_score"] == 4.2

    assert auth_client.delete(f"/api/venues/{venue['id']}").status_code == 204
    assert auth_client.get(f"/api/venues/{venue['id']}").status_code == 404


def test_invalid_status_rejected(auth_client):
    response = auth_client.post(
        "/api/venues", json={"name": "X", "status": "converted"}
    )
    assert response.status_code == 422
