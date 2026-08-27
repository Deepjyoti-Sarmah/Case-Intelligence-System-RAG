import hashlib
import uuid

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.storage.base import Base
from app.storage.models import ChunkORM, DocumentORM, TranscriptORM, TranscriptTurnORM


def _engine():
    # Use localhost:5433 for host dev (docker maps 5433->5432), fallback to postgres host in docker
    import os

    url = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/rag")
    # Allow postgres host inside docker compose backend container
    if "postgres:5432" in url:
        try:
            # quick probe to avoid hanging
            engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return engine
        except Exception:
            url = "postgresql+psycopg://postgres:postgres@localhost:5433/rag"
    return create_engine(url, pool_pre_ping=True)


def test_tables_exist():
    engine = _engine()
    with psycopg.connect("host=localhost port=5433 dbname=rag user=postgres password=postgres") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            tables = {r[0] for r in cur.fetchall()}
    assert {"documents", "sections", "transcripts", "transcript_turns", "chunks", "ingestion_runs"}.issubset(tables)


def test_document_chunk_roundtrip():
    engine = _engine()
    # ensure tables exist (alembic upgrade head creates them)
    Base.metadata.create_all(engine)  # no-op if already exists

    h = hashlib.sha256(f"test-{uuid.uuid4()}".encode()).hexdigest()
    doc_id = uuid.uuid4()
    with Session(engine) as s:
        doc = DocumentORM(
            id=doc_id,
            title="Test Doc",
            source_type="transcript",
            document_type="transcript",
            authority="case_transcript",
            file_name="nathan-04-14.pdf",
            content_hash=h,
        )
        s.add(doc)
        s.commit()

        # read back
        fetched = s.get(DocumentORM, doc_id)
        assert fetched is not None
        assert fetched.content_hash == h
        assert fetched.source_type == "transcript"

        # chunk round-trip — denormalised fields single-table WHERE
        chunk = ChunkORM(
            document_id=doc_id,
            text="Hello world",
            retrieval_text="hello world",
            position=0,
            person_id="nathan",
            session_id="nathan_2025_04_14",
            page_number=1,
            document_type="transcript",
            source_type="transcript",
        )
        s.add(chunk)
        s.commit()
        fetched_chunk = s.get(ChunkORM, chunk.id)
        assert fetched_chunk.document_id == doc_id
        assert fetched_chunk.retrieval_text == "hello world"

        # cleanup
        s.delete(fetched_chunk)
        s.delete(fetched)
        s.commit()


def test_transcript_turn_defaults_unknown():
    engine = _engine()
    with Session(engine) as s:
        # Use a throwaway transcript to test turn defaults
        doc = DocumentORM(
            title="tmp",
            source_type="transcript",
            document_type="transcript",
            authority="case_transcript",
            file_name=f"tmp-{uuid.uuid4()}.pdf",
            content_hash=hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest(),
        )
        s.add(doc)
        s.flush()
        tr_id = uuid.uuid4()
        doc_id_inner = doc.id
        tr = TranscriptORM(
            id=tr_id,
            document_id=doc_id_inner,
            person_id="robert",
            session_id=f"robert_test_{uuid.uuid4().hex[:8]}",
            session_date="2025-05-07",
        )
        s.add(tr)
        s.flush()
        turn = TranscriptTurnORM(
            transcript_id=tr_id,
            sequence=0,
            raw_text="yeah okay",
            normalized_text="yeah okay",
            page_number=1,
        )
        s.add(turn)
        s.commit()
        tid_saved = tr_id
        did_saved = doc_id_inner
        # keep speaker values before detached
        spk = turn.speaker
        conf = turn.speaker_confidence
        assert spk == "unknown"
        assert conf == 0.0
        # cleanup with fresh session to avoid deleted-state issues
    with Session(engine) as s2:
        s2.execute(text("DELETE FROM transcript_turns WHERE transcript_id = :tid"), {"tid": tid_saved})
        s2.execute(text("DELETE FROM transcripts WHERE id = :id"), {"id": tid_saved})
        s2.execute(text("DELETE FROM documents WHERE id = :id"), {"id": did_saved})
        s2.commit()
