"""Register a band (or reset its password) from the command line.

Usage:
    cd backend && python -m app.register_band "Band Name" "the-password"

Run once per band from the Render shell to give friend bands their own
login. Passwords are stored hashed, never in the repo or env. Re-running
with an existing name updates that band's password.
"""

import sys

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Band
from app.passwords import hash_password


def register(name: str, password: str) -> str:
    name = name.strip()
    if not name or not password:
        raise SystemExit("Both a band name and a password are required.")
    with SessionLocal() as db:
        band = db.scalar(
            select(Band).where(func.lower(Band.name) == name.lower())
        )
        if band is None:
            band = Band(name=name, password_hash=hash_password(password))
            db.add(band)
            action = "Registered"
        else:
            band.password_hash = hash_password(password)
            action = "Updated password for"
        db.commit()
    return f"{action} band “{name}”."


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            'Usage: python -m app.register_band "Band Name" "the-password"'
        )
    print(register(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
