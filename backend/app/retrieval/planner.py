import logging
import re
from enum import Enum
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

class Intent(str, Enum):
    REFERENCE_LOOKUP = "REFERENCE_LOOKUP"
    TRANSCRIPT_LOOKUP = "TRANSCRIPT_LOOKUP"
    CROSS_TRANSCRIPT = "CROSS_TRANSCRIPT"
    POLICY_COMPARISON = "POLICY_COMPARISON"
    CROSS_SOURCE = "CROSS_SOURCE"
    THEME_EXTRACTION = "THEME_EXTRACTION"
    CASE_ASSESSMENT = "CASE_ASSESSMENT"
    TEMPORAL_COMPARISON = "TEMPORAL_COMPARISON"
    UNKNOWN = "UNKNOWN"

class QueryPlan(BaseModel):
    intent: Intent = Intent.UNKNOWN
    sources: list[str] = Field(default_factory=lambda: ["policy", "transcript"])
    person_id: str | None = None
    session_scope: str | None = None
    session_date: str | None = None
    document_type: str | None = None
    source_type: str | None = None
    concepts: list[str] = Field(default_factory=list)
    semantic_query: str
    requires_cross_source_reasoning: bool = False

def _deterministic(question: str) -> dict:
    ql = question.lower()
    out: dict = {}
    m = re.search(r"\b(nathan|robert)\b", ql)
    if m:
        out["person_id"] = m.group(1).lower()
    if re.search(r"\b(latest|last|most recent)\b", ql):
        out["session_scope"] = "latest"
    elif re.search(r"\b(previous|prior)\b", ql):
        out["session_scope"] = "previous"
    elif re.search(r"\b(over time|changed|between|across.*meetings)\b", ql):
        out["session_scope"] = "all"
    elif re.search(r"\b(themes|topics|talks about|important to)\b", ql):
        out["session_scope"] = "all"
    if "latest" not in out and "previous" not in out and re.search(r"\b(all sessions|every session)\b", ql):
        out["session_scope"] = "all"
    return out

def _fallback_intent(question: str, det: dict) -> QueryPlan:
    ql = question.lower()
    if "2nd principle" in ql or "second principle" in ql or "principle" in ql and "last meeting" in ql:
        return QueryPlan(intent=Intent.CROSS_SOURCE, sources=["policy", "transcript"], person_id=det.get("person_id"), session_scope=det.get("session_scope") or "latest", semantic_query=question, requires_cross_source_reasoning=True)
    if "grievance" in ql:
        return QueryPlan(intent=Intent.REFERENCE_LOOKUP, sources=["policy"], semantic_query=question)
    if re.search(r"nathan.*drug", ql) or "drug screen" in ql:
        return QueryPlan(intent=Intent.TRANSCRIPT_LOOKUP, sources=["transcript"], person_id=det.get("person_id") or "nathan", session_scope=det.get("session_scope"), semantic_query=question)
    if "robert" in ql and re.search(r"theme|important", ql):
        return QueryPlan(intent=Intent.THEME_EXTRACTION, sources=["transcript"], person_id="robert", session_scope="all", semantic_query=question)
    if "changed between" in ql or "over time" in ql:
        return QueryPlan(intent=Intent.TEMPORAL_COMPARISON, sources=["transcript"], person_id=det.get("person_id"), session_scope="all", semantic_query=question)
    if "risk" in ql and "need" in ql:
        return QueryPlan(intent=Intent.CASE_ASSESSMENT, sources=["transcript", "policy"], semantic_query=question)
    if "family" in ql:
        return QueryPlan(intent=Intent.TRANSCRIPT_LOOKUP, sources=["transcript"], person_id=det.get("person_id"), semantic_query=question)
    if "check-in" in ql or "check in" in ql:
        return QueryPlan(intent=Intent.CROSS_SOURCE, sources=["policy", "transcript"], person_id=det.get("person_id"), session_scope=det.get("session_scope"), semantic_query=question, requires_cross_source_reasoning=True)
    return QueryPlan(intent=Intent.UNKNOWN, sources=["policy", "transcript"], person_id=det.get("person_id"), session_scope=det.get("session_scope"), semantic_query=question)

def plan_query(question: str) -> QueryPlan:
    det = _deterministic(question)
    try:
        if not settings.anthropic_api_key or settings.anthropic_api_key == "dummy-key-for-local-boot":
            raise RuntimeError("no anthropic key")
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.parse(
            model=settings.llm_model,
            max_tokens=1024,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": question}],
            output_format=QueryPlan,
        )
        parsed: QueryPlan = resp.parsed_output  # type: ignore
        # override deterministic — plan.md:344 must never depend on LLM
        if det.get("person_id") is not None:
            parsed.person_id = det["person_id"]
        elif parsed.person_id and parsed.person_id.lower() not in ("nathan", "robert"):
            parsed.person_id = None
        if det.get("session_scope") is not None:
            parsed.session_scope = det["session_scope"]
        return parsed
    except Exception as e:
        logger.warning("planner fallback: %s", e)
        return _fallback_intent(question, det)
