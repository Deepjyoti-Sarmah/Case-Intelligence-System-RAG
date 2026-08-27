from dataclasses import dataclass
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.providers.embeddings import DummyHashEmbeddingProvider
from app.retrieval.filters import build_filters
from app.retrieval.planner import QueryPlan
from app.storage.models import ChunkORM, DocumentORM


@dataclass
class VectorCandidate:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    file_name: str
    text: str
    retrieval_text: str
    distance: float
    rank: int


_embedder = DummyHashEmbeddingProvider()


def vector_search(session: Session, plan: QueryPlan, top_k: int | None = None) -> list[VectorCandidate]:
    top_k = top_k or settings.top_k_dense
    conds = build_filters(plan, session)
    q_emb = _embedder.embed(plan.semantic_query)
    # pgvector cosine distance <=> (0 = identical)
    query = select(ChunkORM, DocumentORM.file_name, ChunkORM.embedding.cosine_distance(q_emb).label("distance")).join(DocumentORM, ChunkORM.document_id == DocumentORM.id)
    for c in conds:
        query = query.where(c)
    query = query.order_by("distance").limit(top_k)
    rows = session.execute(query).all()
    out: list[VectorCandidate] = []
    for idx, (chunk, file_name, distance) in enumerate(rows, start=1):
        out.append(VectorCandidate(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            file_name=file_name,
            text=chunk.text,
            retrieval_text=chunk.retrieval_text,
            distance=float(distance) if distance is not None else 1.0,
            rank=idx,
        ))
    return out
