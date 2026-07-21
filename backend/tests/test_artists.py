def test_artist_crud(auth_client):
    created = auth_client.post(
        "/api/artists",
        json={"name": "Rocky Gresset Trio", "styles": "Gypsy jazz"},
    )
    assert created.status_code == 201
    artist = created.json()

    listed = auth_client.get("/api/artists").json()
    assert [a["name"] for a in listed] == ["Rocky Gresset Trio"]

    patched = auth_client.patch(
        f"/api/artists/{artist['id']}", json={"country_base": "France"}
    )
    assert patched.status_code == 200
    assert patched.json()["country_base"] == "France"

    assert auth_client.delete(f"/api/artists/{artist['id']}").status_code == 204
    assert auth_client.get(f"/api/artists/{artist['id']}").status_code == 404
