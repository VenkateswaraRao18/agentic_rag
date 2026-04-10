import json
import logging
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Repo root (parent of the `app` package). Relative index paths must not depend on cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_under_repo(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return _REPO_ROOT / p


def _index_ntotal(path: Path) -> int:
    if not path.exists():
        return -1
    return int(faiss.read_index(str(path)).ntotal)


def _canonical_index_paths() -> tuple[Path, Path]:
    return (
        _REPO_ROOT / "data" / "index" / "faiss.index",
        _REPO_ROOT / "data" / "index" / "metadata.json",
    )


class FaissStore:
    def __init__(self, dim: int, index_path: str, metadata_path: str) -> None:
        self.dim = dim
        if settings.use_env_vector_index_paths:
            self.index_path = _resolve_under_repo(index_path)
            self.metadata_path = _resolve_under_repo(metadata_path)
        else:
            self.index_path, self.metadata_path = _canonical_index_paths()
        self.index = faiss.IndexFlatIP(dim)
        self.metadata: list[dict[str, Any]] = []
        self.index_load_note: str | None = None

    def load(self) -> None:
        """
        Default: paths already point at <repo>/data/index (see use_env_vector_index_paths).
        If honoring .env paths, prefer the in-repo index when it has more vectors or primary is missing.
        """
        if settings.use_env_vector_index_paths:
            canon_idx, canon_meta = _canonical_index_paths()
            primary_nt = _index_ntotal(self.index_path)
            canon_nt = _index_ntotal(canon_idx) if canon_idx.exists() else -1

            use_canon = canon_meta.exists() and canon_nt >= 0 and (
                primary_nt < 0 or canon_nt > primary_nt
            )
            if use_canon:
                if primary_nt >= 0 and canon_nt > primary_nt:
                    self.index_load_note = (
                        f"Switched to in-repo index ({canon_nt} vs {primary_nt} vectors). "
                        "Remove or fix VECTOR_INDEX_PATH / METADATA_PATH in .env if this is unexpected."
                    )
                    logger.warning("%s Was: %s", self.index_load_note, self.index_path)
                elif primary_nt < 0:
                    self.index_load_note = f"Configured index missing; loaded in-repo {canon_idx}"
                    logger.warning("%s (missing %s)", self.index_load_note, self.index_path)
                self.index_path = canon_idx
                self.metadata_path = canon_meta

        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
        if self.metadata_path.exists():
            self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        if self.metadata and self.index.ntotal != len(self.metadata):
            logger.warning(
                "FAISS index size (%s) != metadata rows (%s). Paths: index=%s meta=%s — run "
                "`python -m ingestion.build_index --docs-dir data/docs` from the repo root.",
                self.index.ntotal,
                len(self.metadata),
                self.index_path,
                self.metadata_path,
            )

    def save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    def add(self, vectors: np.ndarray, docs: list[dict[str, Any]]) -> None:
        if vectors.dtype != np.float32:
            vectors = vectors.astype("float32")
        self.index.add(vectors)
        self.metadata.extend(docs)

    def search(self, query_vector: np.ndarray, top_k: int = 4) -> list[dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)
        scores, ids = self.index.search(query_vector.astype("float32"), top_k)
        results: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            item = dict(self.metadata[idx])
            item["score"] = float(score)
            results.append(item)
        return results
