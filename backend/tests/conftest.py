import os

# Must be set before app modules are imported: the engine and auth config
# read the environment at import/request time.
os.environ["DATABASE_URL"] = "sqlite:///./test_gigpipeline.db"
os.environ["APP_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["COOKIE_SECURE"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    response = client.post("/api/auth/login", json={"password": "test-password"})
    assert response.status_code == 200
    return client
