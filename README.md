# Datarix Monorepo

Unified workspace for Datarix Data Sharing Platform.

## Structure
- frontend/ — Next.js 15 app (port 3001)
- backend/  — FastAPI service (port 8000)
- infrastructure/ — Docker Compose + ops
- docs/ — specs and references
- scripts/ — verification + helper scripts

## First run

The frontend was copied WITHOUT `node_modules` or `.next`. Reinstall
dependencies and rebuild on first run:

    cd frontend
    npm install
    npm run dev

Backend dependencies live in `backend/pyproject.toml` and are
installed inside the API container automatically on `docker compose
up` — no extra step locally.

## Running

Backend:

    cd infrastructure
    docker compose -f docker-compose.dev.yml up -d

Frontend:

    cd frontend
    npm install   # only needed on first run after the copy
    npm run dev

Visit http://localhost:3001

## Test users
See `docs/CHECKLIST_FRONTEND.md` (section "Test Users").

## What was NOT carried over from the source repos
- frontend/node_modules and frontend/.next (rebuild with `npm install` / `npm run dev`)
- backend __pycache__ / *.pyc / .venv
- The OLD frontend copy that lived at `NDI-dev 3/frontend` (the
  authoritative frontend is the one now under `frontend/`).
