import logging
import re
import time
import uuid
from sqlalchemy import text
from app.config import settings
from app.generation.answer import generate_answer
from app.generation.context import build_evidence
from app.generation.grounding import NO_EVIDENCE_ANSWER
from app.retrieval.hybrid import hybrid_search
from app.retrieval.planner import plan_query
from app.storage.database import SessionLocal

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "when", "should", "what", "happened", "with", "about", "have", "has",
    "been", "were", "are", "is", "the", "and", "for", "you", "your", "did",
    "does", "this", "that", "will", "would", "from", "into", "completed",
    "like", "they", "them", "some", "more", "most", "than", "then", "which",
    "where", "whom", "whose", "why", "how", "also", "could", "shall",
    # Question framing, intent, and meta-words (prevent flagging meta-queries as uncorroborated)
    "themes", "theme", "topics", "topic", "session", "sessions", "meeting",
    "meetings", "guidelines", "guideline", "changed", "change", "changes",
    "difference", "differences", "compare", "comparison", "summary",
    "summarize", "assessment", "relationship", "support", "system",
    "manager", "follow", "followed", "according", "details", "detailed",
    "happen", "talks", "talk", "talked", "discuss", "discussed", "discusses",
    "regarding", "concerning", "across", "between", "during", "biggest",
    "risk", "risks", "need", "needs", "think", "seems", "important",
    # Person names - these are metadata filters, not text search terms
    "nathan", "robert",
}


def _no_evidence_response(request_id: str, plan, retrieval_count: int = 0) -> dict:
    out: dict = {
        "answer": NO_EVIDENCE_ANSWER,
        "sources": [],
        "request_id": request_id,
        "metadata": {"retrieval_count": retrieval_count, "grounding_status": "NO_EVIDENCE"},
    }
    if settings.debug_trace:
        out["trace"] = {"plan": plan.model_dump()}
    return out


def _has_uncorroborated_term(session, question: str, candidates: list) -> bool:
    """Detect a query term that appears nowhere in the corpus (e.g. an invented question)."""
    raw_terms = [t.replace("'", "").rstrip('s') for t in re.findall(r"[a-zA-Z']+", question.lower()) if len(t) > 3]
    terms = [t for t in raw_terms if t not in _STOPWORDS] or raw_terms
    rarest = None
    min_cnt = 10**9
    for term in terms:
        try:
            cnt = session.execute(
                text("SELECT count(*) FROM chunks WHERE retrieval_text ILIKE :pat"),
                {"pat": f"%{term}%"},
            ).scalar() or 0
        except Exception:
            cnt = 0
        if cnt < min_cnt:
            min_cnt = cnt
            rarest = term
    if rarest and min_cnt == 0:
        return not any(rarest in getattr(c, "retrieval_text", "").lower() for c in candidates[:10])
    return False


def execute_query(
    session,
    question: str,
    request_id: str | None = None,
    rerank: bool = True,
    debug_trace: bool | None = None,
) -> dict:
    """Core unified RAG pipeline function used by API routes and evaluation harness alike.

    Flow: Plan -> Hybrid Search (FTS + Vector + Rerank) -> Filter/Uncorroborated Check ->
          Build Evidence Context -> Generate Answer & Ground Claims.
    """
    start_time = time.perf_counter()
    request_id = request_id or str(uuid.uuid4())
    debug_trace = debug_trace if debug_trace is not None else settings.debug_trace

    plan = plan_query(question)
    candidates = hybrid_search(session, question, plan, rerank=rerank)

    # De-dupe to document-level list for metrics/tracing
    seen_files: set[str] = set()
    retrieved_files: list[str] = []
    for c in candidates:
        fn = getattr(c, "file_name", "")
        if fn and fn not in seen_files:
            seen_files.add(fn)
            retrieved_files.append(fn)

    if not candidates or _has_uncorroborated_term(session, question, candidates):
        res = _no_evidence_response(request_id, plan)
        res["plan"] = plan
        res["candidates"] = candidates
        res["retrieved_files"] = retrieved_files
        res["evidence"] = []
        res["structured_answer"] = None
        return res

    evidence = build_evidence(session, candidates, plan)
    if not evidence:
        res = _no_evidence_response(request_id, plan, retrieval_count=len(candidates))
        res["plan"] = plan
        res["candidates"] = candidates
        res["retrieved_files"] = retrieved_files
        res["evidence"] = []
        res["structured_answer"] = None
        return res

    structured = generate_answer(question, evidence)

    sources = [
        {
            "source_id": e.evidence_id,
            "title": e.provenance.get("title"),
            "document_type": e.document_type,
            "page": e.page_number,
            "session_date": str(e.session_date) if e.session_date else None,
            "session_id": e.session_id,
            "section": " > ".join(e.heading_path) if e.heading_path else None,
            "person_id": e.person_id,
            "heading_path": e.heading_path,
        }
        for e in evidence
    ]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "query_executed request_id=%s duration_ms=%.2f evidence_count=%d grounding_status=%s",
        request_id,
        duration_ms,
        len(evidence),
        structured.grounding_status,
    )

    out: dict = {
        "answer": structured.answer,
        "sources": sources,
        "request_id": request_id,
        "metadata": {
            "retrieval_count": len(evidence),
            "grounding_status": structured.grounding_status,
            "duration_ms": duration_ms,
        },
        "plan": plan,
        "candidates": candidates,
        "retrieved_files": retrieved_files,
        "evidence": evidence,
        "structured_answer": structured,
    }
    if debug_trace:
        out["trace"] = {"plan": plan.model_dump(), "evidence": [e.provenance for e in evidence]}

    return out


def handle_query(question: str, request_id: str | None = None) -> dict:
    request_id = request_id or str(uuid.uuid4())
    with SessionLocal() as session:
        return execute_query(session, question, request_id)

