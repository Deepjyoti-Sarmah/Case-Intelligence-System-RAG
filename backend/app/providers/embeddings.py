import hashlib
import math
from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class DummyHashEmbeddingProvider:
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        vals = [(h[i % len(h)] / 255.0) * 2 - 1 for i in range(self.dim)]
        norm = math.sqrt(sum(v * v for v in vals)) or 1
        return [v / norm for v in vals]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]
