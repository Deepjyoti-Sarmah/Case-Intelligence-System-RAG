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
    conds = build_filters(plan)
    q = plan.semantic_query.strip()
    if not q:
        return []
    import re
    raw_terms = [t.replace("'", "") for t in re.findall(r"[a-zA-Z']+", q.lower()) if len(t) > 2]
    stop = {"when","should","what","happened","with","about","should","client","would","could","should","have","has","been","were","are","is","the","and","for","you","your"}
    terms = [t for t in raw_terms if t not in stop]
    if not terms:
        terms = raw_terms
    # pick 2 rarest terms by DF for better precision on reference lookups
    try:
        scored = []
        for term in terms:
            cnt = session.execute(text("SELECT count(*) FROM chunks WHERE retrieval_text ILIKE :pat"), {"pat": f"%{term}%"}).scalar() or 999
            scored.append((cnt, term))
        scored.sort()
        terms = [t for _, t in scored[:2]]
    except Exception:
        terms = terms[:2]
    q_or = " | ".join(terms) if terms else q
    sql = text("""
        SELECT c.id as chunk_id, c.document_id, d.file_name, c.text, c.retrieval_text,
               ts_rank_cd(to_tsvector('english', c.retrieval_text), to_tsquery('english', :q)) as score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE to_tsvector('english', c.retrieval_text) @@ to_tsquery('english', :q)
        ORDER BY score DESC
        LIMIT :topk
    """)
    q = q_or
    # apply hard filters manually by adding WHERE clauses if needed — for phase 4 we filter in python if needed
    rows = session.execute(sql, {"q": q, "topk": top_k * 3}).mappings().all()
    # python-side filtering for plan constraints (simple, keeps SQL simple for phase 4)
    filtered = []
    for r in rows:
        # fetch chunk to check filters — quick and acceptable for small corpus
        chunk = session.get(ChunkORM, r["chunk_id"])
        if chunk is None:
            continue
        ok = True
        for c in conds:
            # evaluate simple equality filters on chunk object
            # c is BinaryExpression like ChunkORM.person_id == 'nathan'
            # we evaluate by checking chunk attribute
            try:
                left = c.left.key  # type: ignore
                right = c.right.value  # type: ignore
                if getattr(chunk, left) != right:
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
        bonus = sum(rt.count(term) * 0.15 for term in terms)
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
