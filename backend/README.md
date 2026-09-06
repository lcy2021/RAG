# RAG Lab backend

Python package `raglab`: FastAPI API for the RAG laboratory.

See the root [README.md](../README.md) for product context and [docs/design/backend.md](../docs/design/backend.md) for layers.

## Setup

```bash
docker compose up --build
```

Or Postgres only, then a local venv **from `backend/`**:

```bash
docker compose up -d postgres
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
# optional: OCR loader backends (system Tesseract required; scanned PDF also needs poppler)
pip install -e ".[ocr]"
copy .env.example .env
```

Config priority: **process env (`RAGLAB_*`) > optional `.env` > defaults**.

- **Docker Compose**: injects env in `docker-compose.yml` (hostname `postgres`). No `.env` file is required or copied into the image.
- **Local uvicorn**: copy `.env.example` → `.env` and use `localhost` in `RAGLAB_DATABASE_URL` (not hostname `postgres`).

Startup creates tables and upserts the plugin catalog. Credentials, pipelines, and knowledge bases stay empty until you save them in the UI.

## Run

```bash
uvicorn main:app --reload --app-dir src --port 6660
```

Startup ensures the Postgres database named in `RAGLAB_DATABASE_URL` exists (`CREATE DATABASE` if missing), applies Alembic migrations (`upgrade head`), then registers builtin plugins in memory and upserts them into `plugins`.

Model calls (chat + embeddings) go through **LiteLLM** (`infra.models.LiteLLMClient`). Credentials still store `model_name` + optional `base_url` + secret; a custom base maps to `openai/<model>`. Optional credential `extra` keys: `litellm_model`, `provider`.

Revision files live in `src/alembic/versions/`. To add a migration (from `backend/`):

```bash
alembic revision --autogenerate -m "describe the change"
```

`alembic upgrade head` is optional locally; the API does it on boot. `raglab-migrate` is the same command for scripts/CI.

- Health: `GET /api/v1/health`
- OpenAPI: `/api/v1/docs`
- Catalog: `GET /api/v1/plugins`
- Settings: `/api/v1/settings/credentials`
- Pipelines: `/api/v1/pipelines` (list/create; get/update/delete by id)
- KB: `/api/v1/knowledge-bases` (upload auto-ingests; optional `.../ingest`; delete KB is soft-delete + background hard-delete; delete document)
- Chat: `/api/v1/conversations`
- Chat stream (SSE): `POST /api/v1/conversations/{id}/messages/stream` (`meta` → `progress*` → `delta*` → `done` | `error`); `progress` reports each plugin `running`/`done`/`error` with stage output; `done` includes `sources` + `citations`
- Chat sources: `GET /api/v1/conversations/{id}/rag-runs/{rag_run_id}/sources` (includes `sources`, `citations`, and stage `traces`)

## Test and lint

```bash
ruff check src tests
pytest
```

Unit tests set `RAGLAB_DATABASE_ENABLED=false` and do not require Postgres.
