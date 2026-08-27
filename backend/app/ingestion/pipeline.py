import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingestion.chunkers.policy import chunk_policy_sections
from app.ingestion.chunkers.transcript import chunk_transcript_turns
from app.ingestion.classify import classify
from app.ingestion.enrichers.metadata import enrich_chunk
from app.ingestion.parsers.policy import parse_policy
from app.ingestion.parsers.transcript import parse_transcript
from app.storage.base import Base
from app.storage.database import SessionLocal, engine
from app.storage.models import (
    ChunkORM,
    DocumentORM,
    IngestionRunORM,
    SectionORM,
    TranscriptORM,
    TranscriptTurnORM,
)

logger = logging.getLogger(__name__)
RAW_ROOT = Path("data/raw")

DOC_META = {
    "8 Principles of Effective Intervention.pdf": ("evidence_based_practice", "official_standard"),
    "check-in-guidelines.pdf": ("policy", "official_policy"),
    "grievance-and-appeal.pdf": ("policy", "official_policy"),
    "internal-programming.pdf": ("service_reference", "service_reference"),
    "2022 Colorado Community Corrections Standards copy.pdf": (
        "state_standard",
        "official_standard",
    ),
}


def fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def discover() -> list[Path]:
    files: list[Path] = []
    for sub in ["transcripts", "documents"]:
        root = RAW_ROOT / sub
        if not root.exists():
            continue
        for p in root.rglob("*.pdf"):
            if "__MACOSX" in p.parts or p.name == ".DS_Store":
                continue
            files.append(p)
    return sorted(files)


def _doc_type_authority(path: Path, kind: str):
    if kind == "transcript":
        return ("transcript", "case_transcript")
    return DOC_META.get(path.name, ("policy", "official_policy"))


def _dummy_embedding(text: str) -> list[float]:
    h = hashlib.sha256(text.encode()).digest()
    vals = []
    for i in range(384):
        vals.append((h[i % len(h)] / 255.0) * 2 - 1)
    import math

    norm = math.sqrt(sum(v * v for v in vals)) or 1
    return [v / norm for v in vals]


def run(persist: bool = True) -> dict:
    files = discover()
    logger.info("discovered %d pdfs", len(files))
    results: dict = {"transcripts": [], "documents": [], "skipped": [], "inserted": 0, "chunks": 0}
    run_id = uuid.uuid4()
    started = datetime.utcnow()

    if persist:
        Base.metadata.create_all(engine)
        with SessionLocal() as s:
            s.add(IngestionRunORM(id=run_id, started_at=started, status="running"))
            s.commit()

    inserted_docs = 0
    inserted_chunks = 0
    try:
        for path in files:
            cf = classify(path)
            if not cf:
                results["skipped"].append(str(path))
                continue
            fp = fingerprint(path)
            title = path.stem
            source_type, authority = _doc_type_authority(path, cf.kind)

            if persist:
                with SessionLocal() as s:
                    existing = s.query(DocumentORM).filter_by(content_hash=fp).first()
                    if existing:
                        logger.info("skip %s fp=%s (exists %s)", path.name, fp[:8], existing.id)
                        results["skipped"].append(str(path))
                        continue

                    existing_by_name = s.query(DocumentORM).filter_by(file_name=path.name).first()
                    version = 1
                    if existing_by_name and existing_by_name.content_hash != fp:
                        version = existing_by_name.version + 1
                        logger.info(
                            "version bump %s %s -> %s",
                            path.name,
                            existing_by_name.content_hash[:8],
                            fp[:8],
                        )
                        s.execute(
                            text("DELETE FROM chunks WHERE document_id = :did"),
                            {"did": existing_by_name.id},
                        )
                        s.execute(
                            text(
                                "DELETE FROM transcript_turns WHERE transcript_id IN (SELECT id FROM transcripts WHERE document_id = :did)"
                            ),
                            {"did": existing_by_name.id},
                        )
                        s.execute(
                            text("DELETE FROM sections WHERE document_id = :did"),
                            {"did": existing_by_name.id},
                        )
                        s.execute(
                            text("DELETE FROM transcripts WHERE document_id = :did"),
                            {"did": existing_by_name.id},
                        )
                        s.delete(existing_by_name)
                        s.flush()

                    doc_id = uuid.uuid4()
                    doc = DocumentORM(
                        id=doc_id,
                        title=title,
                        source_type=source_type,
                        document_type=source_type,
                        authority=authority,
                        file_name=path.name,
                        content_hash=fp,
                        version=version,
                    )
                    s.add(doc)
                    s.flush()

                    if cf.kind == "transcript":
                        assert cf.person and cf.session_date and cf.session_id
                        parsed = parse_transcript(path, cf.person, cf.session_date, cf.session_id)
                        assert all(
                            t.speaker == "unknown" and t.speaker_confidence == 0.0
                            for t in parsed.turns
                        )
                        tr_id = uuid.uuid4()
                        tr = TranscriptORM(
                            id=tr_id,
                            document_id=doc_id,
                            person_id=cf.person,
                            session_id=cf.session_id,
                            session_date=cf.session_date,
                        )
                        s.add(tr)
                        s.flush()
                        for t in parsed.turns:
                            s.add(
                                TranscriptTurnORM(
                                    transcript_id=tr_id,
                                    sequence=t.sequence,
                                    speaker=t.speaker,
                                    speaker_confidence=t.speaker_confidence,
                                    raw_text=t.raw_text,
                                    normalized_text=t.normalized_text,
                                    page_number=t.page_number,
                                    is_question=t.is_question,
                                )
                            )
                        s.flush()
                        raw_chunks = chunk_transcript_turns(
                            parsed.turns,
                            doc_id,
                            tr_id,
                            cf.person,
                            cf.session_id,
                            cf.session_date,
                            source_type,
                            source_type,
                        )
                        for ch in raw_chunks:
                            enrich_chunk(ch)
                            emb = _dummy_embedding(ch["retrieval_text"])
                            s.add(
                                ChunkORM(
                                    document_id=ch["document_id"],
                                    transcript_id=ch["transcript_id"],
                                    turn_start=ch["turn_start"],
                                    turn_end=ch["turn_end"],
                                    text=ch["text"],
                                    retrieval_text=ch["retrieval_text"],
                                    token_count=ch["token_count"],
                                    position=ch["position"],
                                    embedding=emb,
                                    heading_path=ch["heading_path"],
                                    metadata_=ch["metadata"],
                                    person_id=ch.get("person_id"),
                                    session_id=ch.get("session_id"),
                                    session_date=ch.get("session_date"),
                                    document_type=ch.get("document_type"),
                                    source_type=ch.get("source_type"),
                                    page_number=ch.get("page_number"),
                                )
                            )
                        inserted_chunks += len(raw_chunks)
                        results["transcripts"].append(
                            {
                                "path": str(path),
                                "turns": len(parsed.turns),
                                "chunks": len(raw_chunks),
                            }
                        )
                    else:
                        secs = parse_policy(path)
                        sec_map: dict[int, uuid.UUID] = {}
                        for sec in secs:
                            sid = uuid.uuid4()
                            parent_id = (
                                sec_map.get(sec.parent_idx) if sec.parent_idx is not None else None
                            )
                            s.add(
                                SectionORM(
                                    id=sid,
                                    document_id=doc_id,
                                    parent_section_id=parent_id,
                                    heading=sec.heading,
                                    level=sec.level,
                                    position=sec.position,
                                    page_number=sec.page_number,
                                )
                            )
                            sec_map[sec.position] = sid
                            sec.id = sid
                        s.flush()
                        raw_chunks = chunk_policy_sections(secs, doc_id, source_type, source_type)
                        for ch in raw_chunks:
                            enrich_chunk(ch)
                            emb = _dummy_embedding(ch["retrieval_text"])
                            s.add(
                                ChunkORM(
                                    document_id=ch["document_id"],
                                    section_id=ch["section_id"],
                                    text=ch["text"],
                                    retrieval_text=ch["retrieval_text"],
                                    token_count=ch["token_count"],
                                    position=ch["position"],
                                    embedding=emb,
                                    heading_path=ch["heading_path"],
                                    metadata_=ch["metadata"],
                                    document_type=ch.get("document_type"),
                                    source_type=ch.get("source_type"),
                                    page_number=ch.get("page_number"),
                                )
                            )
                        inserted_chunks += len(raw_chunks)
                        results["documents"].append(
                            {"path": str(path), "sections": len(secs), "chunks": len(raw_chunks)}
                        )
                    s.commit()
                    inserted_docs += 1
            else:
                if cf.kind == "transcript":
                    parsed = parse_transcript(path, cf.person, cf.session_date, cf.session_id)  # type: ignore
                    raw_chunks = chunk_transcript_turns(
                        parsed.turns,
                        uuid.uuid4(),
                        uuid.uuid4(),
                        cf.person,
                        cf.session_id,
                        cf.session_date,
                    )
                    results["transcripts"].append(
                        {"path": str(path), "turns": len(parsed.turns), "chunks": len(raw_chunks)}
                    )
                else:
                    secs = parse_policy(path)
                    raw_chunks = chunk_policy_sections(secs, uuid.uuid4(), source_type, source_type)
                    results["documents"].append(
                        {"path": str(path), "sections": len(secs), "chunks": len(raw_chunks)}
                    )

        if persist:
            with SessionLocal() as s:
                run = s.get(IngestionRunORM, run_id)
                if run:
                    run.finished_at = datetime.utcnow()
                    run.status = "completed"
                    run.documents_processed = inserted_docs
                    run.chunks_created = inserted_chunks
                    s.commit()
        results["inserted"] = inserted_docs
        results["chunks"] = inserted_chunks
        logger.info("done inserted=%d chunks=%d", inserted_docs, inserted_chunks)
        return results
    except Exception as e:
        if persist:
            with SessionLocal() as s:
                run = s.get(IngestionRunORM, run_id)
                if run:
                    run.finished_at = datetime.utcnow()
                    run.status = "failed"
                    run.error = str(e)[:2000]
                    s.commit()
        raise


if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    res = run(persist="--dry" not in sys.argv)
    json.dump(res, sys.stdout, indent=2)
    print()
