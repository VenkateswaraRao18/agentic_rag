import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import get_cors_allow_origins, settings
from app.graph.workflow import build_graph
from app.schemas import AskRequest, AskResponse, Citation
from app.services.embeddings import TorchEmbedder
from app.services.retriever import Retriever
from app.services.vector_store import FaissStore

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self) -> None:
        self.embedder = TorchEmbedder(embedding_dim=256)
        self.store = FaissStore(
            dim=256,
            index_path=settings.vector_index_path,
            metadata_path=settings.metadata_path,
        )
        self.retriever = Retriever(self.embedder, self.store)
        self.graph = None


runtime = Runtime()


@asynccontextmanager
async def lifespan(_: FastAPI):
    runtime.store.load()
    logger.info(
        "Vector index loaded: ntotal=%s path=%s",
        runtime.store.index.ntotal,
        runtime.store.index_path,
    )
    runtime.graph = build_graph(runtime.retriever)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Origins from CORS_ORIGINS / ENVIRONMENT (see app.config.get_cors_allow_origins).
# `allow_private_network` helps Chrome when the browser origin is localhost but the API is 127.0.0.1.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allow_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health() -> dict:
    # Bump when changing health shape so you can confirm the running process picked up new code.
    index_path = runtime.store.index_path.resolve()
    ntotal = runtime.store.index.ntotal
    meta_len = len(runtime.store.metadata)
    out: dict = {
        "status": "ok",
        "code_revision": 5,
        "index_size": ntotal,
        "metadata_rows": meta_len,
        "vector_index_path": str(index_path),
        "vector_paths_from_env": settings.use_env_vector_index_paths,
        "repo_root": str(Path(__file__).resolve().parent.parent),
        "app_main_path": str(Path(__file__).resolve()),
    }
    if runtime.store.index_load_note:
        out["index_load_note"] = runtime.store.index_load_note
    if ntotal < 4:
        out["warning"] = (
            "Vector index looks unusually small; rebuild with "
            "`python -m ingestion.build_index --docs-dir data/docs` from the repo root "
            "and restart the API so retrieval and routing behave as expected."
        )
    return out


@app.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask the ops copilot (JSON body)",
    description=(
        "Send a JSON object, e.g. `{\"question\": \"...\"}`. "
        "Plain text or an empty body causes a JSON decode error in /docs."
    ),
)
async def ask(payload: AskRequest) -> AskResponse:
    start = time.perf_counter()
    initial_state = {
        "question": payload.question,
        "intent": "unknown",
        "retrieved_docs": [],
        "tool_result": None,
        "answer": "",
        "citations": [],
        "used_tool": False,
        "fallback_used": False,
    }
    try:
        result = runtime.graph.invoke(initial_state)
    except Exception:
        logger.exception("LangGraph /ask pipeline failed")
        raise HTTPException(status_code=500, detail="Internal error while running the agent.") from None

    latency_ms = int((time.perf_counter() - start) * 1000)
    citations_out: list[Citation] = []
    for c in result["citations"]:
        try:
            citations_out.append(Citation.model_validate(c))
        except Exception:
            citations_out.append(
                Citation(
                    source=str(c.get("source", "unknown")),
                    chunk_id=str(c.get("chunk_id", "na")),
                    score=float(c.get("score", 0.0)),
                    section_path=c.get("section_path"),
                    section_title=c.get("section_title"),
                    page_start=c.get("page_start"),
                    page_end=c.get("page_end"),
                )
            )

    tr = result.get("tool_result") if isinstance(result.get("tool_result"), dict) else None
    debug: dict = {"retrieved_count": len(result["retrieved_docs"])}
    if tr:
        debug["tool_op"] = tr.get("op")
        debug["tool_count"] = tr.get("count")

    return AskResponse(
        answer=result["answer"],
        intent=result["intent"],
        citations=citations_out,
        used_tool=result["used_tool"],
        fallback_used=result["fallback_used"],
        latency_ms=latency_ms,
        debug=debug,
    )
