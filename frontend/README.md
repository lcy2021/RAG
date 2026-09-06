# RAG Lab web UI

Operator console for the RAG laboratory. Talks to the FastAPI service under `/api/v1`.

## Stack

- Vite 8 + React 19 + TypeScript
- React Router
- TanStack Query
- Ant Design (lab/admin surfaces: layout, tables, forms, upload) with a Linear-inspired dark theme
- i18next + react-i18next (zh / en, header language switch)
- ESLint + Prettier + oxlint
- Vitest + Testing Library

Ant Design is used because M1–M5 are form- and table-heavy (slot editor, JSON Schema params, ingest, traces). A CSS-only UI would delay those pages; a marketing-oriented kit (for example shadcn) would require assembling the same primitives.

## Setup

Stack (Postgres + API + UI):

```bash
docker compose up --build
```

UI: http://localhost:6650 (nginx proxies `/api` to the API container).

Local Vite:

```bash
cd frontend
npm install
npm run dev
```

Dev server: http://localhost:6650 (proxies `/api` to `http://127.0.0.1:6660`).

Optional `.env`:

```
VITE_API_BASE=http://127.0.0.1:6660
```

Leave `VITE_API_BASE` empty in local dev to use the Vite proxy.

## Scripts

```bash
npm run dev
npm run build
npm run lint
npm run format
npm test
```

## Pages (M1)

`/settings` (credentials: vector or LLM; list shows key hint), `/plugins`, `/pipelines`, `/kb` are list pages (search; Add where create exists). Create/detail live on nested routes: `/settings/credentials/new`, `/pipelines/new`, `/kb/new`, `/kb/:id`. `/scenarios` list/create/detail: pick KB + evaluator metrics, add gold questions and paste evidence quotes from KB documents. `/experiments` list/create/detail: bind a scenario to explicit variants (optional one-stage plugin override), queue offline eval (poll until done), inspect the variant × metric table, and promote the winner into a new query pipeline / KB default. Chat is a dialog: defaults to the first knowledge base and first query pipeline; history sessions can be deleted from the left rail; while answering, each assistant card shows a scrollable progress block (plugin stage + output) above the answer; after refresh, traces reload from the rag-run sources API.

Plugin params use `binding_id`; credentials are managed on the settings page.

## i18n

UI copy lives in `src/i18n/locales/{zh,en}.json`. Switch language from the header control; the choice is stored as `raglab.locale`. Ant Design locale follows the same switch.
