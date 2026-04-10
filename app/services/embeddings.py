import hashlib

import numpy as np
import torch
import torch.nn as nn


class HashEmbeddingModel(nn.Module):
    def __init__(self, vocab_size: int = 5000, embedding_dim: int = 256) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        torch.manual_seed(42)
        nn.init.xavier_uniform_(self.embedding.weight)
        self.vocab_size = vocab_size

    def forward(self, token_ids: torch.Tensor) -> torch.Tensor:
        embedded = self.embedding(token_ids)
        return embedded.mean(dim=0)


class TorchEmbedder:
    def __init__(self, vocab_size: int = 5000, embedding_dim: int = 256) -> None:
        self.model = HashEmbeddingModel(vocab_size=vocab_size, embedding_dim=embedding_dim)
        self.model.eval()
        self.embedding_dim = embedding_dim
        self.vocab_size = vocab_size

    def _tokenize(self, text: str) -> torch.Tensor:
        tokens = text.lower().split()
        if not tokens:
            tokens = ["empty"]
        ids: list[int] = []
        for token in tokens[:256]:
            digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
            ids.append(int(digest, 16) % self.vocab_size)
        return torch.tensor(ids, dtype=torch.long)

    def embed_text(self, text: str) -> np.ndarray:
        token_ids = self._tokenize(text)
        with torch.no_grad():
            vec = self.model(token_ids)
        arr = vec.numpy().astype("float32")
        norm = np.linalg.norm(arr) + 1e-12
        return arr / norm

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        vectors = [self.embed_text(text) for text in texts]
        return np.stack(vectors).astype("float32")
