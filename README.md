# Project A: Enterprise Agentic AI Copilot on AWS

Production-style Ops Copilot that supports enterprise support teams with:

- RAG over internal docs (layout-aware PDFs via **DocuWeave**)
- LangGraph workflow (`classify → retrieve → tool → answer`)
- **AWS Bedrock** (Titan, Llama, Mistral, or Anthropic) for grounded answers when configured
- Guardrails + fallback behavior
- **Next.js** chat UI + FastAPI API
- AWS-oriented deployment (EC2, S3, Lambda ingestion)

**Resume / demo (no real ITSM API):** Incident data lives in **`data/synthetic_incidents.json`** (~32 synthetic rows: INC-1001–INC-1032) with fields like service, team, tags, SLA hints, and summaries. `app/services/tooling.py` loads that file at import. The agent supports **get by INC**, **list open/all**, and **keyword search** (including tags). RAG overlap: `data/docs/synthetic-incident-playbook.txt` and `data/docs/synthetic-services-catalog.txt`. After adding docs, run `python -m ingestion.build_index --docs-dir data/docs`.

## Stack

- Python, FastAPI, LangGraph, LangChain
- PyTorch (local embeddings), FAISS
- DocuWeave (`parse` → `to_chunks` with section metadata)
- Next.js 14 (App Router, Tailwind)
- AWS Bedrock, S3, Lambda; Docker + GitHub Actions

## Architecture

1. **Ingestion** (`ingestion/build_index.py`)
   - **PDF**: `docuweave.parse()` → `to_chunks()` → rich metadata (`section_path`, pages, chunk ids)
   - **HTML / TXT / MD**: plain text + simple character windows (`ingestion/chunking.py`)
   - Embeddings (PyTorch) → FAISS index + JSON metadata
2. **Agent** (`app/graph/workflow.py`): intent → retrieve → ticket tool → answer + citations
3. **LLM** (`app/services/llm.py`, `app/services/bedrock.py`): Bedrock when `USE_BEDROCK=true` (`BEDROCK_MODEL_ID` + optional `BEDROCK_PROVIDER`), else template fallback
4. **UI** (`web/`): chat against `POST /ask` with CORS enabled on the API

## Backend quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`: set `AWS_REGION=us-east-1`, `BEDROCK_MODEL_ID` (e.g. `google.gemma-3-12b-it` or `amazon.titan-text-express-v1`), and in the Bedrock console enable **Model access** for that model. Use **local-only** credentials if needed (never commit secrets). On EC2 prefer an IAM role with `bedrock:InvokeModel`.

Build the index:

```bash
python -m ingestion.build_index --docs-dir data/docs
```

Run the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health: `GET http://127.0.0.1:8000/health`  
Swagger: `http://127.0.0.1:8000/docs`

Set `USE_BEDROCK=false` in `.env` if you want template answers only (no AWS calls).

## Frontend (Next.js)

```bash
cd web
copy .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. `NEXT_PUBLIC_API_URL` should point at the FastAPI origin (default `http://127.0.0.1:8000`).

## Evaluation

```bash
python scripts/evaluate.py
```

## Guardrails & fallback

- Prompt-injection phrase blocking  
- Low-confidence retrieval fallback when there is no tool result  
- Bedrock errors fall back to the template composer (logged server-side)

## AWS deployment (summary)

- **EC2**: Docker image + IAM role with `bedrock:InvokeModel` and S3 access  
- **S3**: source docs + optional published index artifacts  
- **Lambda**: `lambda/ingest_handler.py` pattern for async re-indexing  
- **GitHub Actions**: `.github/workflows/ci-cd.yml` scaffold (fill in ECR/EC2 deploy steps)

## Success metrics

- P95 latency, Recall@k / MRR, hallucination reduction, cost per 1k queries, uptime/SLA  
