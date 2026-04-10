import argparse
from pathlib import Path

from tqdm import tqdm

from app.config import settings
from app.services.embeddings import TorchEmbedder
from app.services.vector_store import FaissStore
from ingestion.chunking import chunk_text
from ingestion.parse_docs import parse_plain_document


def discover_docs(docs_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    for ext in ("*.pdf", "*.html", "*.htm", "*.txt", "*.md"):
        candidates.extend(docs_dir.rglob(ext))
    return sorted(candidates)


def chunks_from_pdf(path: Path) -> list[dict]:
    from docuweave import parse

    doc = parse(str(path))
    raw = doc.to_chunks(
        max_tokens=settings.docuweave_max_tokens,
        model_name=settings.docuweave_token_model,
    )
    rows: list[dict] = []
    for ch in raw:
        rows.append(
            {
                "chunk_id": ch["id"],
                "source": str(path),
                "text": ch.get("text") or "",
                "section_path": ch.get("section_path"),
                "section_title": ch.get("section_title"),
                "page_start": ch.get("page_start"),
                "page_end": ch.get("page_end"),
            }
        )
    return rows


def chunks_from_plain(path: Path) -> list[dict]:
    text = parse_plain_document(path)
    out: list[dict] = []
    for i, chunk in enumerate(chunk_text(text)):
        out.append(
            {
                "chunk_id": f"{path.name}-{i}",
                "source": str(path),
                "text": chunk,
                "section_path": None,
                "section_title": None,
                "page_start": None,
                "page_end": None,
            }
        )
    return out


def build(docs_dir: Path) -> None:
    embedder = TorchEmbedder(embedding_dim=256)
    store = FaissStore(256, settings.vector_index_path, settings.metadata_path)

    docs = discover_docs(docs_dir)
    all_chunks: list[str] = []
    all_meta: list[dict] = []

    for doc_path in tqdm(docs, desc="Ingesting docs"):
        if doc_path.suffix.lower() == ".pdf":
            metas = chunks_from_pdf(doc_path)
        else:
            metas = chunks_from_plain(doc_path)
        for row in metas:
            if not row["text"].strip():
                continue
            all_chunks.append(row["text"])
            all_meta.append(row)

    if not all_chunks:
        print("No chunks found. Add docs to data/docs first.")
        return

    vectors = embedder.embed_batch(all_chunks)
    store.add(vectors, all_meta)
    store.save()
    print(f"Indexed {len(all_chunks)} chunks from {len(docs)} docs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-dir", default=settings.docs_dir)
    args = parser.parse_args()
    build(Path(args.docs_dir))
