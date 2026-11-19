# FinAxis GSTR-9C Microservice + Workbench

Standalone FastAPI service for **GSTR-9C preparation** (port **8789**) plus a **standalone React workbench** (port **5174**).

This repo lives at `d:\workspace\GSTR` and is **separate from** the FinAxis Client Portal (`d:\workspace\client-portal`).

## Design

- Reuses the **existing FinAxis Supabase** project (auth, `profiles`, `gst_registrations`, RLS via `employee_has_client_access`)
- Does **not** create a new database, tenant, or auth system
- Does **not** modify the client-portal codebase
- Workbench + any future portal UI call this API with the user’s Supabase JWT

```text
Workbench (web/)  --JWT-->  FastAPI (:8789)  -->  FinAxis Supabase + GSTZen
                 --JWT-->  Supabase (clients / GSTINs / employees)
```

## Features

- Case CRUD (client + GSTIN registration + FY)
- GSTIN validation via GSTZen
- Async jobs: fetch returns, Excel/CSV ingest, reconcile, generate 9C draft, export
- Deterministic reconciliation engine
- Decimal-based GSTR-9C draft calculations
- Excel / PDF exports (**no automatic filing**)
- Standalone workbench UI for the full workflow

## Setup

### 1. Database

Apply `supabase/migrations/20261114_gst_9c.sql` in the **FinAxis** Supabase SQL Editor.

### 2. API (`.env` in repo root)

```bash
copy .env.example .env
# fill SUPABASE_* and GSTZEN_*
```

```bash
cd d:\workspace\GSTR
pip install -r requirements.txt
set PYTHONPATH=.
uvicorn app.main:app --host 0.0.0.0 --port 8789 --reload
```

Or: `docker compose up --build`

### 3. Workbench UI (`web/`)

```bash
cd d:\workspace\GSTR\web
copy .env.example .env
# set VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_GSTR_API_URL=http://localhost:8789
npm install
npm run dev
```

Open **http://localhost:5174** and sign in with a FinAxis **employee/admin** account.

## Ports

| Service | Port |
|---------|------|
| GSTR FastAPI | 8789 |
| Workbench Vite | 5174 |

## Workbench pages

| Route | Purpose |
|-------|---------|
| `/login` | FinAxis Supabase login |
| `/` | Dashboard stats |
| `/cases` | List + create cases |
| `/cases/:id` | Fetch returns, upload books, jobs |
| `/cases/:id/reconciliation` | Run / filter reconciliation |
| `/cases/:id/review` | Draft preview, adjustments, approve |
| `/cases/:id/reports` | Excel / PDF export + download |

## API tests

```bash
cd d:\workspace\GSTR
set PYTHONPATH=.
pytest -q
```

## API (selected)

| Method | Path |
|--------|------|
| GET | `/health` |
| GET | `/api/v1/gst/dashboard` |
| POST | `/api/v1/gst/cases` |
| GET | `/api/v1/gst/cases/{id}` |
| POST | `/api/v1/gst/cases/{id}/fetch-returns` |
| POST | `/api/v1/gst/cases/{id}/documents` |
| POST | `/api/v1/gst/cases/{id}/reconcile` |
| POST | `/api/v1/gst/cases/{id}/generate` |
| GET | `/api/v1/gst/cases/{id}/preview` |
| POST | `/api/v1/gst/cases/{id}/approve` |
| POST | `/api/v1/gst/cases/{id}/exports` |
| GET | `/api/v1/gst/jobs/{job_id}` |

## Pending verification

- GSTR-9 portal API fetch (manual upload supported)
- GST portal-compatible JSON filing (out of MVP)

## Integrating FinAxis later

Keep business logic here. Add a thin client in `client-portal` that calls this API when product wants 9C inside the main portal.
