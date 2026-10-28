# Deployment Guide

How to take the app from local-only to a live URL. It's 12-factor (all config via env), uses **Alembic** migrations, is **Postgres-ready**, and can run as a **single service** (FastAPI serves the built frontend) or as two (API + static site). No Docker required — Railway and Render build from source with Nixpacks/buildpacks.

---

## What you need to decide

- **Database:** SQLite is fine for a personal single-instance deploy, but most hosts have ephemeral disks (the file is wiped on redeploy). Use **Postgres** for anything you want to persist. The code supports both via `DATABASE_URL`.
- **One service or two:** single-service (set `STATIC_DIR`, FastAPI serves the SPA) is simplest. Two-service (static frontend + API) scales the frontend on a CDN.
- **Keeping data fresh:** a scheduled job must run `scripts/refresh_data.py` daily and `scripts/train_model.py` + `scripts/seed_picks.py` periodically (see §5).

---

## 1. Environment variables

| Var | Example | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` | SQLite default is local-only. The `+psycopg` driver is already in requirements. |
| `CORS_ORIGINS` | `https://app.example.com` | Comma-separated. Only needed for the **two-service** setup (different origin). Single-service needs none. |
| `STATIC_DIR` | `/app/frontend/dist` | Set for **single-service**; leave empty for API-only. |
| `ARTIFACTS_DIR` | `/app/backend/artifacts` | Where model artifacts live. Needs persistent storage if you train in-place. |
| `DATA_PROVIDER` | `yfinance` | Swap point for a paid provider later. |
| `PREDICTION_HORIZON_DAYS` | `21` | Model horizon. |

## 2. Database migrations (Alembic)

Schema is managed by Alembic (`backend/alembic/`). On a **fresh Postgres** database:

```bash
cd backend
DATABASE_URL="postgresql+psycopg://..." .venv/bin/alembic upgrade head
```

This creates all 9 tables. `app/main.py` only auto-creates tables on SQLite (dev convenience); on Postgres it relies on migrations, so run `alembic upgrade head` as a **release/deploy step** before the server starts.

- **Already have a SQLite DB with data you migrated from?** `alembic stamp head` marks it as up-to-date without re-running.
- **Changed a model later?** `alembic revision --autogenerate -m "describe change"` then `alembic upgrade head`. (SQLite uses batch mode automatically for ALTERs.)

## 3. Single-service deploy (recommended for personal use)

One web service runs both the API and the UI.

**Build step:**
```bash
pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build        # produces frontend/dist
```
**Release step (migrations):**
```bash
cd backend && alembic upgrade head
```
**Start command:**
```bash
cd backend && STATIC_DIR=../frontend/dist uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
FastAPI serves the SPA at `/`, falls back to `index.html` for client routes, and handles `/api/*`. Same origin, so no CORS needed.

### Railway
1. New Project → Deploy from GitHub → this repo.
2. Add a **Postgres** plugin; Railway injects `DATABASE_URL` (ensure the `postgresql+psycopg://` scheme — set it explicitly if needed).
3. Set `STATIC_DIR=../frontend/dist`.
4. Build command: `pip install -r backend/requirements.txt && cd frontend && npm ci && npm run build`.
5. Pre-deploy/release command: `cd backend && alembic upgrade head`.
6. Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

### Render
Use a `render.yaml` (Blueprint) or the dashboard with the same build/release/start commands and a Postgres instance.

## 4. Two-service deploy (API + static frontend)

- **API service:** start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, set `CORS_ORIGINS` to the frontend URL, leave `STATIC_DIR` empty.
- **Static site:** build `frontend` with `VITE`'s API base pointed at the API URL. The frontend currently calls `/api` (same-origin). For a split origin, add a Vite proxy/rewrite or an env-based axios `baseURL` in `src/api.js` and set it to the API host.

## 5. Keeping data fresh (scheduled jobs)

The app only reflects data that has been fetched. Schedule (Railway cron, Render cron job, or GitHub Actions):

- **Daily, after US market close:** `cd backend && python scripts/refresh_data.py`
  (incremental bars → fundamentals → snapshots → AI re-score → log live picks).
- **Monthly (or quarterly):** `cd backend && python scripts/train_model.py && python scripts/seed_picks.py`
  (retrain on the latest data; refresh the track record + walk-forward prediction panel).

Model artifacts and the Postgres data persist between runs, so the scheduled retrain just updates them.

## 6. First-time data load on a fresh deploy

A brand-new database is empty. Run once (as a one-off job or locally against the prod `DATABASE_URL`):
```bash
cd backend
python scripts/seed_universe.py     # S&P 500 list
python scripts/refresh_data.py      # ~5-10 min: 5y of bars + fundamentals + snapshots
python scripts/train_model.py       # train the model
python scripts/seed_picks.py        # seed the track record + AI-backtest panel
```

## 7. Notes & gotchas

- **OpenMP for XGBoost:** Nixpacks/Render Linux images include `libgomp`; no action needed. (Locally on macOS it's `brew install libomp`.)
- **Ephemeral disk:** if you keep SQLite, the DB resets on every redeploy — use Postgres or a persistent volume.
- **Artifacts persistence:** if you train in the deployed environment, `ARTIFACTS_DIR` needs a persistent volume; otherwise train locally/in CI and ship artifacts, or store them in object storage.
- **Secrets:** never commit `.env`; set vars in the host's dashboard.
- **Auth:** the app has no authentication yet. On a public URL, add a shared password or auth before exposing the watchlist/plan (see `CHECKLIST.md`).
