import os

# Must be set before app modules are imported: the engine and auth config
# read the environment at import/request time.
os.environ["DATABASE_URL"] = "sqlite:///./test_gigpipeline.db"
os.environ["APP_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["COOKIE_SECURE"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Band
from app.passwords import hash_password

TEST_BAND = "Test Band"
TEST_BAND_PASSWORD = "test-password"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def band(client) -> Band:
    """The default band tests act as. Created fresh per test."""
    with SessionLocal() as db:
        row = Band(name=TEST_BAND, password_hash=hash_password(TEST_BAND_PASSWORD))
        db.add(row)
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row


@pytest.fixture()
def auth_client(client, band):
    response = client.post(
        "/api/auth/login",
        json={"band_name": TEST_BAND, "password": TEST_BAND_PASSWORD},
    )
    assert response.status_code == 200
    return client
