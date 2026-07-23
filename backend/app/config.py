import os


def database_url() -> str:
    """Resolve DATABASE_URL, defaulting to a local SQLite file.

    Hosting providers (Neon, Render, Heroku) often hand out URLs starting
    with `postgres://` or `postgresql://`; SQLAlchemy needs an explicit
    driver, so both are rewritten to use psycopg 3.
    """
    url = os.environ.get("DATABASE_URL", "sqlite:///./gigpipeline.db")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def secret_key() -> str:
    return os.environ.get("SECRET_KEY", "dev-only-insecure-secret")


def app_password() -> str | None:
    return os.environ.get("APP_PASSWORD") or None


def anthropic_api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None


def seed_band_name() -> str:
    """Name of the band that owns data created before multi-band access —
    the existing venues/artists, and the rows the Notion import re-adds on
    every deploy. Overridable via env, defaults to our own band."""
    return os.environ.get("SEED_BAND_NAME") or "Gipsy Tonic"


def cookie_secure() -> bool:
    # Secure cookies on by default; opt out for local http development.
    return os.environ.get("COOKIE_SECURE", "true").lower() != "false"
