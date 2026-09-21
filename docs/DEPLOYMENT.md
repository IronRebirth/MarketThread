# MarketThread Production Deployment

## Release architecture

The production release uses Vercel for the Next.js web application and a separate managed service for the FastAPI API and PostgreSQL database.

The browser talks to the API through the Vercel domain:

```text
Browser
  |
  v
Vercel /api/*
  |
  v
FastAPI API
  |
  +--> PostgreSQL
  +--> external market/news/LLM providers
```

The Vercel proxy keeps browser API requests same-origin. This is important for the HttpOnly authentication cookie and avoids exposing the backend hostname to browser JavaScript.

## Vercel web project

Create a Vercel project from the MarketThread GitHub repository.

Use:

- Framework: Next.js
- Root Directory: `apps/web`
- Build Command: default Next.js build
- Output Directory: default
- Install Command: `pnpm install`

Production environment variables:

```text
NEXT_PUBLIC_API_BASE_URL=/api
MARKETTHREAD_API_URL=https://<public-api-host>
```

The `MARKETTHREAD_API_URL` value is server-side only. Do not prefix it with `NEXT_PUBLIC_`.

Vercel should deploy production from the release branch selected in Project Settings.

## API environment

Run the FastAPI application with a production ASGI server:

```text
uv run uvicorn app.main:app --host 0.0.0.0 --port $API_PORT
```

Required production settings:

```text
APP_ENV=production
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=<managed-postgresql-connection-string>
JWT_SECRET_KEY=<random-secret-at-least-32-characters>
JWT_ALGORITHM=HS256
JWT_ISSUER=marketthread-api
ACCESS_TOKEN_EXPIRE_MINUTES=30
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
CORS_ALLOWED_ORIGINS=https://<vercel-domain>
```

Do not copy development values from `.env.example` into production.

## Database migration

Run migrations against the production database before marking the API ready:

```text
cd apps/api
uv sync --frozen
uv run alembic upgrade head
```

The production database must be backed up by the managed database provider before destructive or irreversible migration work.

## Health checks

Use:

```text
GET /health
GET /ready
```

`/health` verifies that the process is serving requests.

`/ready` performs a database connectivity check and returns HTTP 503 when the application database is unavailable.

## Release smoke test

After deployment:

1. Open the Vercel production URL.
2. Register a test account.
3. Log in and confirm the `marketthread.access` cookie is HttpOnly.
4. Refresh the page and confirm the session remains authenticated.
5. Exercise one authenticated read and one authenticated state-changing operation.
6. Log out and confirm authenticated requests are rejected.
7. Check `/health` and `/ready` on the API host.
8. Confirm the Vercel deployment logs and API logs contain no startup or runtime errors.

## Current release scope

This release intentionally does not add new product features. Missing roadmap items such as password reset and email verification remain candidates for the next product version.

The release goal is to ship the functionality already present with a documented production deployment path and a controlled release process.
