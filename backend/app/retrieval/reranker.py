import logging
from dataclasses import dataclass
from app.config import settings

logger = logging.getLogger(__name__)

@dataclass
class RerankCandidate:
    chunk_id: object
    score: float

class NoOpReranker:
    async def rank(self, query: str, candidates: list) -> list:
        return candidates[: settings.top_k_rerank]

    def rank_sync(self, query: str, candidates: list) -> list:
        return candidates[: settings.top_k_rerank]

class CrossEncoderReranker:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.reranker_model
        self.model = None
        self.enabled = settings.enable_reranker
        if not self.enabled:
            logger.info("reranker disabled via ENABLE_RERANKER=false")
            return
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name, max_length=512)
            logger.info("loaded reranker %s", self.model_name)
        except Exception as e:
            logger.warning("reranker load failed %s: %s -> fallback NoOp", self.model_name, e)
            self.model = None

    def _score(self, query: str, candidates: list) -> list[tuple[float, object]]:
        if self.model is None:
            return [(c.rrf_score if hasattr(c, "rrf_score") else 0, c) for c in candidates]
        pairs = [(query, c.retrieval_text[:1000]) for c in candidates]
        try:
            scores = self.model.predict(pairs)
            return list(zip(scores, candidates))
        except Exception as e:
            logger.warning("reranker predict failed: %s", e)
            return [(c.rrf_score if hasattr(c, "rrf_score") else 0, c) for c in candidates]

    async def rank(self, query: str, candidates: list) -> list:
        scored = self._score(query, candidates)
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[: settings.top_k_rerank]]

    def rank_sync(self, query: str, candidates: list) -> list:
        scored = self._score(query, candidates)
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[: settings.top_k_rerank]]

_reranker_instance = None

def get_reranker():
    global _reranker_instance
    if _reranker_instance is not None:
        return _reranker_instance
    if not settings.enable_reranker:
        _reranker_instance = NoOpReranker()
        return _reranker_instance
    r = CrossEncoderReranker()
    if r.model is None:
        _reranker_instance = NoOpReranker()
    else:
        _reranker_instance = r
    return _reranker_instance
