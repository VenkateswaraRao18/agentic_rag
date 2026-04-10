# Ops Copilot

An operations copilot backed by retrieval-augmented generation: documents in `data/docs` are chunked (DocuWeave for PDFs, simpler chunking for other formats), embedded into a FAISS index, and queried through a LangGraph workflow. A FastAPI service exposes the agent; a Next.js application provides the chat interface and server-side proxy to the API.

## Capabilities

- Intent routing, retrieval, optional ticket tool calls, and grounded answers with citations
- Synthetic incident data for demonstration (`data/synthetic_incidents.json`) without a live ITSM integration
- Optional **Amazon Bedrock** for generation; template-based fallback when Bedrock is disabled or errors occur
- Basic guardrails: prompt-injection filtering, low-confidence retrieval handling, and structured health reporting

## Requirements

| Component | Notes |
| --- | --- |
| Python | 3.11 or newer (container image targets 3.12) |
| Node.js | 20.x for the web client (see `web/Dockerfile`) |
| Docker | Optional; used for Compose-based local stacks and API image builds |

## Architecture

1. **Ingestion** — `ingestion/build_index.py` produces vectors and metadata under `data/index/`.
2. **Runtime** — `app/` loads the index, runs `app/graph/workflow.py`, and serves HTTP via FastAPI.
3. **Web** — `web/` serves the UI and forwards API traffic using a catch-all route under `/api/backend/` so the browser does not require direct API access when the proxy is used.

## Repository layout

| Path | Purpose |
| --- | --- |
| `app/` | API, LangGraph pipeline, retrieval, Bedrock client, ticket tooling |
| `ingestion/` | Index build and chunking helpers |
| `data/docs/` | Source documents for RAG |
| `data/index/` | Generated FAISS index and metadata (not hand-edited) |
| `web/` | Next.js 14 application (App Router, Tailwind) |
| `Dockerfile.api` | Production-oriented API image; runs index build during build |
| `docker-compose.yml` | Local multi-service stack (API + web) |
| `run_api.py` | Uvicorn entrypoint that fixes import path from repo root |
| `scripts/evaluate.py` | Offline evaluation helper |

## Local development

### Backend

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m ingestion.build_index --docs-dir data/docs
uvicorn run_api:app --reload --host 0.0.0.0 --port 8000
```

On Windows, activate `.venv\Scripts\activate`, use `copy` instead of `cp`, or run `api.bat` / `dev-up.ps1` after creating the virtual environment. `dev-up.ps1` clears processes bound to port 8000 before starting the server.

Environment variables are documented in `.env.example`. Set `USE_BEDROCK=false` to avoid AWS calls. Always run Uvicorn with `run_api:app` from the repo root unless you have arranged `PYTHONPATH` yourself.

### Frontend

```bash
cd web
cp .env.local.example .env.local
npm install
npm run dev
```

Set `BACKEND_PROXY_TARGET` to the origin of your running API (scheme, host, and port only, no trailing slash). For Compose, this is overridden for the `web` service. Leave `NEXT_PUBLIC_API_URL` unset unless you intentionally call the API from the browser and have configured CORS on the API.

```bash
npm run lint
```

Default dev ports: API **8000**, web **3000**. OpenAPI UI is served at path `/docs` on the API process; health checks at `/health`.

## HTTP surface

| Method | Path | Description |
| --- | --- | --- |
| GET | `/` | Redirect to interactive API documentation |
| GET | `/health` | Liveness, index statistics, diagnostic fields |
| POST | `/ask` | JSON body with a `question` field |

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The API service publishes port **8000**; the web service publishes **3000**. The compose file sets the web container’s proxy target to the internal API hostname and port.

For platform deployment (e.g. managed containers), build from `Dockerfile.api` and bind the application to the port supplied by the environment (for example `PORT`). Deploy the web application separately and point its `BACKEND_PROXY_TARGET` at the public API origin.

## Evaluation and CI

```bash
python scripts/evaluate.py
```

Continuous integration (`.github/workflows/ci-cd.yml`) installs Python dependencies and performs an import smoke test on pushes and pull requests to `main`. A follow-on deploy job is reserved for future registry and host automation.

## Operational notes

Monitor `/health` after deployments to confirm index load and revision markers. Server logs record Bedrock fallback paths and agent failures. Tune `CORS_ORIGINS` in production when clients call the API directly from additional browser origins.
