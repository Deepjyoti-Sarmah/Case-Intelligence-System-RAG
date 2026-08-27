from dataclasses import dataclass
import uuid
from sqlalchemy.orm import Session
from app.config import settings
from app.retrieval.planner import QueryPlan, plan_query
from app.retrieval.lexical import lexical_search, LexicalCandidate
from app.retrieval.vector import vector_search, VectorCandidate


@dataclass
class HybridCandidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    text: str
    retrieval_text: str
    rrf_score: float
    lexical_rank: int | None
    vector_rank: int | None


def reciprocal_rank_fusion(lexical: list[LexicalCandidate], vector: list[VectorCandidate], k: int | None = None) -> list[HybridCandidate]:
    k = k or settings.rrf_k
    scores: dict[uuid.UUID, dict] = {}
    for c in lexical:
        entry = scores.setdefault(c.chunk_id, {"doc": c, "lex": None, "vec": None})
        entry["lex"] = c.rank
    for c in vector:
        entry = scores.setdefault(c.chunk_id, {"doc": c, "lex": None, "vec": None})
        entry["vec"] = c.rank

    fused: list[HybridCandidate] = []
    for cid, info in scores.items():
        lex_r = info["lex"]
        vec_r = info["vec"]
        score = 0.0
        if lex_r is not None:
            score += 1.0 / (k + lex_r)
        if vec_r is not None:
            score += 1.0 / (k + vec_r)
        doc = info["doc"]
        fused.append(HybridCandidate(
            chunk_id=cid,
            document_id=doc.document_id,
            file_name=doc.file_name,
            text=doc.text,
            retrieval_text=doc.retrieval_text,
            rrf_score=score,
            lexical_rank=lex_r,
            vector_rank=vec_r,
        ))
    fused.sort(key=lambda x: x.rrf_score, reverse=True)
    return fused


def hybrid_search(session: Session, question: str, plan: QueryPlan | None = None, rerank: bool | None = None) -> list[HybridCandidate]:
    if plan is None:
        plan = plan_query(question)
    lex = lexical_search(session, plan)
    # for pure policy lookup, lexical is authoritative — skip noisy dummy vector
    if plan.sources == ["policy"]:
        fused = [
            HybridCandidate(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                file_name=c.file_name,
                text=c.text,
                retrieval_text=c.retrieval_text,
                rrf_score=c.score,
                lexical_rank=c.rank,
                vector_rank=None,
            )
            for c in lex
        ]
        fused.sort(key=lambda x: x.rrf_score, reverse=True)
    else:
        vec = vector_search(session, plan)
        fused = reciprocal_rank_fusion(lex, vec)
    do_rerank = rerank if rerank is not None else settings.enable_reranker
    if do_rerank:
        try:
            from app.retrieval.reranker import get_reranker
            reranker = get_reranker()
            # sync path for phase 4/5 tests
            if hasattr(reranker, "rank_sync"):
                return reranker.rank_sync(question, fused)  # type: ignore
        except Exception:
            pass
    return fused[: settings.top_k_rerank] if do_rerank else fused
