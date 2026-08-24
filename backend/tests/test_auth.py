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


# --- Band registration (owner-gated, no shell needed) ---------------------

# conftest sets APP_PASSWORD (the owner secret) to this.
ADMIN_PW = "test-password"


def test_register_band_creates_and_can_log_in(client):
    response = client.post(
        "/api/auth/register-band",
        json={
            "admin_password": ADMIN_PW,
            "band_name": "Les Amis",
            "password": "amispw",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "band_name": "Les Amis", "created": True}
    # The new band can immediately log in.
    login = client.post(
        "/api/auth/login", json={"band_name": "Les Amis", "password": "amispw"}
    )
    assert login.status_code == 200


def test_register_existing_band_resets_password(client, band):
    # `band` fixture created TEST_BAND; re-registering resets its password.
    response = client.post(
        "/api/auth/register-band",
        json={
            "admin_password": ADMIN_PW,
            "band_name": TEST_BAND,
            "password": "brand-new-pw",
        },
    )
    assert response.status_code == 200
    assert response.json()["created"] is False
    assert (
        client.post(
            "/api/auth/login",
            json={"band_name": TEST_BAND, "password": "brand-new-pw"},
        ).status_code
        == 200
    )


def test_register_band_wrong_owner_password_rejected(client):
    response = client.post(
        "/api/auth/register-band",
        json={
            "admin_password": "not-the-owner-secret",
            "band_name": "Sneaky",
            "password": "sneakypw",
        },
    )
    assert response.status_code == 401
    # Nothing was created.
    assert (
        client.post(
            "/api/auth/login", json={"band_name": "Sneaky", "password": "sneakypw"}
        ).status_code
        == 401
    )


def test_register_band_short_password_rejected(client):
    response = client.post(
        "/api/auth/register-band",
        json={"admin_password": ADMIN_PW, "band_name": "Tiny", "password": "abc"},
    )
    assert response.status_code == 422
