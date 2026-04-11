# Data Management Platform

Multi-product SaaS portal for Saudi Arabian enterprises. The platform provides a governed, PDPL-compliant channel for data sharing between departments and organisations.

## Architecture

```
LOGIN → PRODUCT PORTAL → [ Data Sharing ] [ Data Quality ] [ NDMO ] [ DSR ]
                               ↓
                         (enter product)
```

**Platform Core** (`app/platform/`) — shared auth, tenants, users, product registry.
**Products** (`app/products/`) — one subfolder per product module.

## Stack

- Python 3.12 / FastAPI
- PostgreSQL 15
- Redis 7
- MinIO (S3-compatible object storage)
- Keycloak (identity & SSO)
- Docker / Docker Compose

## Quick Start (Dev)

```bash
# Start all services
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d

# API docs: http://localhost:8000/api/docs
# MailHog:  http://localhost:8025
# MinIO:    http://localhost:9001
# Keycloak: http://localhost:8080
```

## Project Structure

```
backend/
├── app/
│   ├── core/           # Config, database, security, tenant context
│   ├── platform/       # Platform Core (auth, users, tenants, products)
│   ├── products/       # Product modules
│   │   ├── data_sharing/
│   │   └── data_quality/   (placeholder)
│   ├── gateways/       # External service integrations
│   ├── structures/     # Base classes and shared models
│   └── utils/          # Exceptions, pagination, helpers
├── setup/db/           # SQL migrations
└── tests/
```

## Adding a New Product

1. Create `app/products/{slug}/` with routers, services, repositories, workers, enums.
2. Add a row to `t_products` seed data.
3. Register its router in `main.py` under `/api/v1/products/{slug}/`.
4. Add SQL migrations under `setup/db/`.
5. The portal screen automatically shows it for any tenant that has it enabled.

## Git Workflow

- `main` — production
- `dev` — development
- `feature/*` — feature branches cut from `dev`
- Conventional commits: `feat:`, `fix:`, `chore:`, `refactor:`
