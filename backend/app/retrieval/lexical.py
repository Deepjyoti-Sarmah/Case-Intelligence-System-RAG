from dataclasses import dataclass
import uuid
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from app.retrieval.filters import build_filters
from app.retrieval.planner import QueryPlan
from app.storage.models import ChunkORM, DocumentORM
from app.config import settings


@dataclass
class LexicalCandidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    text: str
    retrieval_text: str
    score: float
    rank: int


def lexical_search(session: Session, plan: QueryPlan, top_k: int | None = None) -> list[LexicalCandidate]:
    top_k = top_k or settings.top_k_lexical
    conds = build_filters(plan, session)
    q = plan.semantic_query.strip()
    if not q:
        return []
    import re
    raw_terms = [t.replace("'", "") for t in re.findall(r"[a-zA-Z']+", q.lower()) if len(t) > 2]
    stop = {
        "when", "should", "what", "happened", "with", "about", "should", "client",
        "would", "could", "should", "have", "has", "been", "were", "are", "is",
        "the", "and", "for", "you", "your", "did", "does", "this", "that", "will",
        "from", "into", "completed", "like", "they", "them", "some", "more",
        "most", "than", "then", "which", "where", "whom", "whose", "why", "how",
        "themes", "theme", "topics", "topic", "session", "sessions", "meeting",
        "meetings", "guidelines", "guideline", "changed", "change", "changes",
        "difference", "differences", "compare", "comparison", "summary",
        "summarize", "assessment", "relationship", "support", "system",
        "manager", "follow", "followed", "according", "details", "detailed",
        "happen", "talks", "talk", "talked", "discuss", "discussed", "discusses",
        "regarding", "concerning", "across", "between", "during", "biggest",
        "risk", "risks", "need", "needs", "think", "seems", "important",
    }
    terms = [t for t in raw_terms if t not in stop]
    if not terms:
        terms = raw_terms

    # Only include terms that actually exist in the database (count > 0)
    valid_scored = []
    for term in terms:
        try:
            cnt = session.execute(
                text("SELECT count(*) FROM chunks WHERE retrieval_text ILIKE :pat"),
                {"pat": f"%{term}%"},
            ).scalar() or 0
            if cnt > 0:
                valid_scored.append((cnt, term))
        except Exception:
            pass

    if valid_scored:
        valid_scored.sort()
        search_terms = [t for _, t in valid_scored[:5]]
    else:
        search_terms = terms[:5]

    q_or = " | ".join(search_terms) if search_terms else q

    sql = text("""
        SELECT c.id as chunk_id, c.document_id, d.file_name, c.text, c.retrieval_text,
               ts_rank_cd(to_tsvector('english', c.retrieval_text), to_tsquery('english', :q)) as score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE to_tsvector('english', c.retrieval_text) @@ to_tsquery('english', :q)
        ORDER BY score DESC
        LIMIT :topk
    """)

    rows = []
    try:
        rows = session.execute(sql, {"q": q_or, "topk": top_k * 3}).mappings().all()
    except Exception:
        rows = []

    # Fallback to ILIKE if tsquery returned 0 rows for valid search_terms
    if not rows and search_terms:
        ilike_conds = " OR ".join(f"c.retrieval_text ILIKE :t{i}" for i in range(len(search_terms)))
        params = {f"t{i}": f"%{term}%" for i, term in enumerate(search_terms)}
        params["topk"] = top_k * 3
        sql_fallback = text(f"""
            SELECT c.id as chunk_id, c.document_id, d.file_name, c.text, c.retrieval_text,
                   1.0 as score
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE {ilike_conds}
            LIMIT :topk
        """)
        try:
            rows = session.execute(sql_fallback, params).mappings().all()
        except Exception:
            rows = []

    filtered = []
    for r in rows:
        chunk = session.get(ChunkORM, r["chunk_id"])
        if chunk is None:
            continue
        ok = True
        for c in conds:
            try:
                left = c.left.key  # type: ignore
                right = c.right.value  # type: ignore
                op_name = getattr(c.operator, "__name__", str(c.operator))
                val = getattr(chunk, left)
                if op_name == "ne":
                    if val == right:
                        ok = False
                        break
                else:
                    if val != right:
                        ok = False
                        break
            except Exception:
                pass
        if not ok:
            continue
        filtered.append(r)
        if len(filtered) >= top_k:
            break

    boosted = []
    for r in filtered:
        base = float(r["score"])
        rt = r["retrieval_text"].lower()
        fn = r["file_name"].lower()
        bonus = sum(rt.count(term) * 0.15 for term in search_terms)
        for term in search_terms:
            if term in fn:
                bonus += 1.5
        boosted.append((r, base + bonus))
    boosted.sort(key=lambda x: x[1], reverse=True)
    out: list[LexicalCandidate] = []
    for idx, (r, sc) in enumerate(boosted, start=1):
        out.append(LexicalCandidate(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            file_name=r["file_name"],
            text=r["text"],
            retrieval_text=r["retrieval_text"],
            score=sc,
            rank=idx,
        ))
    return out

