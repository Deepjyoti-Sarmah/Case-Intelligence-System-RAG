"""Retrieval-quality metrics: Recall@k, MRR, NDCG — overall and per query type."""
import math


def _is_relevant(file_name: str, expected: list[str]) -> bool:
    fn = file_name.lower()
    return any(exp.lower() == fn or exp.lower() in fn for exp in expected)


def recall_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return None
    top_k = retrieved[:k]
    hit_count = sum(1 for exp in expected if any(_is_relevant(r, [exp]) for r in top_k))
    return hit_count / len(expected)


def mrr(retrieved: list[str], expected: list[str]) -> float:
    if not expected:
        return None
    for rank, file_name in enumerate(retrieved, start=1):
        if _is_relevant(file_name, expected):
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    """Binary relevance NDCG@k."""
    if not expected:
        return None
    top_k = retrieved[:k]
    dcg = sum(
        1.0 / math.log2(i + 2) for i, r in enumerate(top_k) if _is_relevant(r, expected)
    )
    ideal_hits = min(len(expected), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def score_query(retrieved: list[str], expected: list[str]) -> dict:
    return {
        "recall_at_5": recall_at_k(retrieved, expected, 5),
        "recall_at_10": recall_at_k(retrieved, expected, 10),
        "mrr": mrr(retrieved, expected),
        "ndcg_at_10": ndcg_at_k(retrieved, expected, 10),
    }


def _mean(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def aggregate(per_query: list[dict]) -> dict:
    """per_query: list of {"type": str, "scores": {metric: value}}. Returns overall + per-type means."""
    metrics = ["recall_at_5", "recall_at_10", "mrr", "ndcg_at_10"]
    overall = {m: _mean([q["scores"][m] for q in per_query]) for m in metrics}
    by_type: dict[str, dict] = {}
    for q in per_query:
        by_type.setdefault(q["type"], []).append(q["scores"])
    per_type = {
        t: {m: _mean([s[m] for s in scores]) for m in metrics}
        for t, scores in by_type.items()
    }
    return {"overall": overall, "per_type": per_type}
