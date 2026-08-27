"""Generation-quality metrics: groundedness, citation correctness, unsupported claim rate,
fact coverage, and an optional LLM-judge pass for answer relevance.

These re-derive grounding independently of the production `grounding.validate` call so a
regression in the app's own self-reported status cannot silently pass the eval.
"""
import logging

logger = logging.getLogger(__name__)


def claim_grounding(claims: list[dict], valid_evidence_ids: set[str]) -> dict:
    """Returns groundedness (fraction of claims fully backed by real evidence ids) and
    the complementary unsupported_claim_rate (empty or unresolvable evidence_ids)."""
    if not claims:
        return {"groundedness": None, "unsupported_claim_rate": None}
    unsupported = 0
    for c in claims:
        ids = c.get("evidence_ids") or []
        if not ids or any(i not in valid_evidence_ids for i in ids):
            unsupported += 1
    return {
        "groundedness": 1 - (unsupported / len(claims)),
        "unsupported_claim_rate": unsupported / len(claims),
    }


def citation_correctness(source_files: list[str], expected_sources: list[str]) -> float | None:
    """Fraction of expected source documents actually present among the cited sources."""
    if not expected_sources:
        return None
    hits = 0
    for exp in expected_sources:
        exp_l = exp.lower()
        if any(exp_l == f.lower() or exp_l in f.lower() for f in source_files):
            hits += 1
    return hits / len(expected_sources)


def fact_coverage(answer: str, expected_facts: list[str]) -> float | None:
    if not expected_facts:
        return None
    answer_l = answer.lower()
    hits = sum(1 for fact in expected_facts if fact.lower() in answer_l)
    return hits / len(expected_facts)


def no_evidence_correct(grounding_status: str, answer: str, no_evidence_answer: str) -> bool:
    return grounding_status == "NO_EVIDENCE" or answer.strip() == no_evidence_answer.strip()


def must_not_claim_violation(answer: str, must_not_claim: list[str]) -> bool:
    if not must_not_claim:
        return False
    answer_l = answer.lower()
    return any(term.lower() in answer_l for term in must_not_claim)


def llm_judge_relevance(question: str, answer: str) -> float | None:
    """Optional LLM-as-judge pass for answer relevance (0-1). Returns None if no LLM is
    configured — this metric degrades gracefully rather than failing the run."""
    from app.config import settings

    if not settings.anthropic_api_key or settings.anthropic_api_key == "dummy-key-for-local-boot":
        return None
    try:
        import anthropic
        from pydantic import BaseModel, Field

        class Judgment(BaseModel):
            relevance: float = Field(ge=0, le=1)

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.parse(
            model=settings.llm_model,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Question: {question}\nAnswer: {answer}\n\n"
                    "Rate how relevant the answer is to the question on a 0.0-1.0 scale, "
                    "regardless of whether you think it is factually correct."
                ),
            }],
            output_format=Judgment,
        )
        return resp.parsed_output.relevance  # type: ignore
    except Exception as e:
        logger.warning("llm judge failed: %s", e)
        return None


def _mean(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def aggregate(per_query: list[dict]) -> dict:
    metrics = ["groundedness", "unsupported_claim_rate", "citation_correctness", "fact_coverage", "answer_relevance"]
    overall = {m: _mean([q["scores"].get(m) for q in per_query]) for m in metrics}
    no_evidence_records = [q for q in per_query if q["type"] == "no_evidence"]
    overall["no_evidence_accuracy"] = _mean(
        [1.0 if q["scores"].get("no_evidence_correct") else 0.0 for q in no_evidence_records]
    )
    return {"overall": overall}
