# Datarix — Workspace Guide for Claude

This is a monorepo. Always check both subprojects:

- frontend/ — Next.js 15 + TypeScript + Tailwind
  Read frontend/CLAUDE_FRONTEND.md and
       frontend/CHECKLIST_FRONTEND.md before working.

- backend/ — FastAPI + Postgres + MinIO + Keycloak
  Read backend/CLAUDE.md if it exists.

## Quick reference
- Frontend dev: `cd frontend && npm run dev`        (port 3001)
- Backend up:   `cd infrastructure && docker compose -f docker-compose.dev.yml up -d`
- DB query:     `docker exec ndi-dev3-postgres-1 psql -U dsplatform -d datasharing_dev -c "..."`
- Tests:        `scripts/verify.sh`

## Roles & users
See docs/CHECKLIST_FRONTEND.md → "Test Users" section.

## First-run note
After cloning / copying this tree fresh:
- `cd frontend && npm install`   (node_modules is not committed)
- Backend installs inside the api container on `docker compose up`.
