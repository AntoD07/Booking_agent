# Gig Pipeline

Booking-management app for a Gypsy jazz quartet: venues and festivals move
through a pipeline (Discovered → … → Confirmed) toward the 2027 season.
See `CLAUDE.md` for the full project brief.

Monorepo: FastAPI backend (`/backend`) + Vite/React frontend (`/frontend`),
deployed as a single service — the backend serves the built frontend.

## Local development

Backend (Python 3.12, uses SQLite unless `DATABASE_URL` points elsewhere):

```sh
cd backend
pip install -r requirements.txt
alembic upgrade head          # create/upgrade the database schema
python -m app.seed            # optional: 3 venues + 2 artists
APP_PASSWORD=change-me COOKIE_SECURE=false uvicorn app.main:app --reload
```

Frontend (dev server proxies `/api` to `localhost:8000`):

```sh
cd frontend
npm install
npm run dev
```

Tests:

```sh
cd backend
pytest
```

To test the single-service setup locally, run `npm run build` in `frontend/`
and open `http://localhost:8000` — FastAPI serves `frontend/dist`.

## Deployment (Render)

`render.yaml` defines one web service that installs the backend, builds the
frontend, runs migrations, and starts uvicorn. Create the service via
Render's *Blueprints* with this repo, then set the environment variables
below. The database is expected to be a managed Postgres (e.g. Neon free
tier).

To seed production data once, open a Render shell and run
`cd backend && python -m app.seed`.

## Environment variables

Values live only in the hosting platform's settings (or your local shell) —
never in the repo.

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | production | Postgres connection string (`postgres://…` accepted). Defaults to local SQLite `backend/gigpipeline.db`. |
| `APP_PASSWORD` | yes | The single shared password for the login gate. Login is disabled until it is set. |
| `SECRET_KEY` | production | Signs the session cookie. Render generates it via `render.yaml`; any long random string works. |
| `COOKIE_SECURE` | no | Set to `false` for local plain-HTTP development only. |
