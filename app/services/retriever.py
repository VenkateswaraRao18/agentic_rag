from app.config import settings
from app.services.embeddings import TorchEmbedder
from app.services.vector_store import FaissStore


class Retriever:
    def __init__(self, embedder: TorchEmbedder, store: FaissStore) -> None:
        self.embedder = embedder
        self.store = store

    def retrieve(self, question: str, top_k: int | None = None) -> list[dict]:
        k = top_k or settings.default_top_k
        qvec = self.embedder.embed_text(question)
        return self.store.search(qvec, top_k=k)
