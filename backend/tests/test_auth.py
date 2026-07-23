from tests.conftest import TEST_BAND, TEST_BAND_PASSWORD


def test_wrong_password_rejected(client, band):
    response = client.post(
        "/api/auth/login", json={"band_name": TEST_BAND, "password": "nope"}
    )
    assert response.status_code == 401


def test_unknown_band_rejected(client, band):
    response = client.post(
        "/api/auth/login",
        json={"band_name": "No Such Band", "password": TEST_BAND_PASSWORD},
    )
    assert response.status_code == 401


def test_missing_band_name_is_invalid(client):
    assert client.post("/api/auth/login", json={"password": "x"}).status_code == 422


def test_api_requires_session(client):
    assert client.get("/api/venues").status_code == 401
    assert client.get("/api/artists").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_login_grants_access(auth_client):
    me = auth_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["band_name"] == TEST_BAND
    assert auth_client.get("/api/venues").status_code == 200


def test_login_is_case_insensitive_on_band_name(client, band):
    response = client.post(
        "/api/auth/login",
        json={"band_name": TEST_BAND.lower(), "password": TEST_BAND_PASSWORD},
    )
    assert response.status_code == 200


def test_logout_clears_session(auth_client):
    auth_client.post("/api/auth/logout")
    assert auth_client.get("/api/auth/me").status_code == 401
