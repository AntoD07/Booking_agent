# CLAUDE.md — Gig Pipeline

## What this project is

A booking-management web app for a Gypsy jazz quartet (300+ concerts, first
album out) targeting European festivals, venues, and jazz bars for the 2027
season. It replaces a Notion-based workflow.

Core jobs, in priority order:
1. **Pipeline tracking** — venues/festivals as cards moving through statuses:
   Discovered → Researched → Draft Ready → Sent → Follow-up → Confirmed / Declined / Not a fit.
2. **Reference-artist discovery** — track 10–20 similar bands (manouche/swing
   scene) and the venues they've played; every such venue is a qualified lead.
3. **Email drafting** — generate personalized pitch drafts using the
   "similar artist X played here" hook. Drafts are ALWAYS reviewed by a human
   before sending; the app never sends email automatically.
4. **Deadlines** — calendar of application windows (most European festivals
   close applications Sept–Jan for the following summer).

Later phases (do NOT build until asked): scheduled scans of artist gig feeds,
enrichment via web search, multi-user.

## Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.x, SQLite (single-user app —
  no Postgres, no Docker, no auth in phase 1). Pydantic v2 schemas.
- **Frontend**: React 18 + Vite + TypeScript. Plain CSS or CSS modules —
  no Tailwind, no component library (see Design).
- **Repo layout**: `/backend` and `/frontend` in this monorepo.
- **Testing**: pytest for the API. Frontend tests only for non-trivial logic.

## Commands

- Backend dev: `cd backend && uvicorn app.main:app --reload`
- Frontend dev: `cd frontend && npm run dev`
- Tests: `cd backend && pytest`

## Design identity — read carefully

This is a tool for a musician, not a SaaS dashboard. The aesthetic is
**elegant, sober, artist-oriented**: think concert program / album sleeve,
not admin panel.

- Typography-first: a good serif for headings (e.g. Cormorant, EB Garamond,
  or Fraunces), quiet humanist sans for body. Generous whitespace.
- Palette: warm paper tones (ivory/cream background), deep ink text,
  ONE accent (burgundy or brass/gold). No gradients, no glassmorphism,
  no drop-shadow cards everywhere, no emoji in the UI.
- Density: calm. Prefer fewer, larger elements over dense grids.
- Motion: minimal, subtle transitions only.
- Language in UI: musician's vocabulary ("Venues", "Programmers",
  "Season", "Set") not CRM-speak ("Leads", "Conversion").

## Conventions

- Small, focused commits with clear messages.
- Backend: type hints everywhere, one router per resource, schemas separate
  from ORM models.
- Frontend: colocate component + styles; no global state library until
  actually needed (React Query for server state is fine).
- Never add dependencies without stating why.
- When a task is ambiguous, ask before building.

## Data model (phase 1)

- `Venue`: name, type (festival/venue/jazz club/bar/cultural center), country,
  city, status, fit_score, booking_contact, contact_email, application_method,
  application_url, application_deadline, event_dates, website, research_notes,
  last_contact, next_action, source.
- `Artist` (reference artist): name, styles, country_base, similarity,
  gig_feed_url, website, last_scanned, notes.
- `VenueArtist`: many-to-many — which reference artists played which venue.
- `EmailDraft`: venue_id, subject, body, status (draft/approved/sent), created_at.
