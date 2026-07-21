def test_wrong_password_rejected(client):
    response = client.post("/api/auth/login", json={"password": "nope"})
    assert response.status_code == 401


def test_api_requires_session(client):
    assert client.get("/api/venues").status_code == 401
    assert client.get("/api/artists").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_login_grants_access(auth_client):
    assert auth_client.get("/api/auth/me").status_code == 200
    assert auth_client.get("/api/venues").status_code == 200


def test_logout_clears_session(auth_client):
    auth_client.post("/api/auth/logout")
    assert auth_client.get("/api/auth/me").status_code == 401
