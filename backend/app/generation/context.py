import hashlib
from sqlalchemy.orm import Session
from app.config import settings
from app.domain.evidence import Evidence
from app.retrieval.planner import QueryPlan
from app.storage.models import ChunkORM, DocumentORM, SectionORM, TranscriptTurnORM

def _tokens(text: str) -> int:
    return int(len(text.split()) * 1.3) or 1

def _dedupe(cands):
    seen_id = set()
    seen_text = set()
    out = []
    for c in cands:
        cid = str(c.chunk_id)
        if cid in seen_id:
            continue
        norm = c.retrieval_text.strip().lower()
        h = hashlib.sha256(norm.encode()).hexdigest()
        if h in seen_text:
            continue
        seen_id.add(cid)
        seen_text.add(h)
        out.append(c)
    return out

def build_evidence(session: Session, candidates: list, plan: QueryPlan) -> list[Evidence]:
    cands = _dedupe(candidates)

    filtered = []
    for c in cands:
        chunk = session.get(ChunkORM, c.chunk_id)
        if chunk is None:
            continue
        if plan.person_id and chunk.person_id and chunk.person_id.lower() != plan.person_id.lower():
            continue
        filtered.append(c)
    cands = filtered

    expanded = []
    for c in cands:
        chunk = session.get(ChunkORM, c.chunk_id)
        doc = session.get(DocumentORM, c.document_id)
        if chunk is None or doc is None:
            continue
        text = chunk.text
        retrieval_text = chunk.retrieval_text
        heading_path = chunk.heading_path
        provenance = {"file_name": doc.file_name, "title": doc.title, "page_number": chunk.page_number, "chunk_id": str(chunk.id)}

        if chunk.transcript_id and chunk.turn_start is not None:
            turns = session.query(TranscriptTurnORM).filter(
                TranscriptTurnORM.transcript_id == chunk.transcript_id,
                TranscriptTurnORM.sequence >= chunk.turn_start - 3,
                TranscriptTurnORM.sequence <= (chunk.turn_end or chunk.turn_start) + 3,
            ).order_by(TranscriptTurnORM.sequence).all()
            if turns:
                text = "\n".join(t.raw_text for t in turns)
                retrieval_text = " ".join(t.normalized_text for t in turns)
                provenance["turn_start"] = turns[0].sequence
                provenance["turn_end"] = turns[-1].sequence
                provenance["expanded"] = True

        if chunk.section_id and chunk.heading_path:
            sec = session.get(SectionORM, chunk.section_id)
            if sec and sec.parent_section_id:
                parent = session.get(SectionORM, sec.parent_section_id)
                if parent:
                    provenance["parent_heading"] = parent.heading

        score = getattr(c, "rrf_score", 0) or getattr(c, "score", 0) or 0
        expanded.append({
            "chunk": chunk,
            "doc": doc,
            "candidate": c,
            "text": text,
            "retrieval_text": retrieval_text,
            "heading_path": heading_path,
            "provenance": provenance,
            "score": score,
        })

    transcript_items = [e for e in expanded if e["chunk"].source_type == "transcript"]
    policy_items = [e for e in expanded if e["chunk"].source_type != "transcript"]

    transcript_items.sort(key=lambda x: (x["chunk"].session_date or "", x["chunk"].turn_start or 0))
    policy_items.sort(key=lambda x: (x["heading_path"] or []))

    ordered = policy_items + transcript_items
    # if cross-source, interleave to keep at least 1 per group after budgeting
    if plan.sources and len(plan.sources) > 1:
        ordered = []
        max_len = max(len(policy_items), len(transcript_items))
        for i in range(max_len):
            if i < len(policy_items):
                ordered.append(policy_items[i])
            if i < len(transcript_items):
                ordered.append(transcript_items[i])

    total = sum(_tokens(e["text"]) for e in ordered)
    budget = settings.max_context_tokens
    if total > budget:
        ordered.sort(key=lambda x: x["score"])
        kept = []
        # always keep at least 1 per source group if cross-source
        groups = {}
        for e in ordered:
            g = e["chunk"].source_type
            groups.setdefault(g, []).append(e)
        for g, items in groups.items():
            items.sort(key=lambda x: x["score"], reverse=True)
            kept.append(items[0])
        remaining = [e for e in ordered if e not in kept]
        remaining.sort(key=lambda x: x["score"], reverse=True)
        cur_tokens = sum(_tokens(e["text"]) for e in kept)
        for e in remaining:
            nt = _tokens(e["text"])
            if cur_tokens + nt <= budget:
                kept.append(e)
                cur_tokens += nt
        ordered = kept
        transcript_items = [e for e in ordered if e["chunk"].source_type == "transcript"]
        policy_items = [e for e in ordered if e["chunk"].source_type != "transcript"]
        transcript_items.sort(key=lambda x: (x["chunk"].session_date or "", x["chunk"].turn_start or 0))
        policy_items.sort(key=lambda x: (x["heading_path"] or []))
        ordered = policy_items + transcript_items

    evidence: list[Evidence] = []
    p_idx = c_idx = 1
    for e in ordered:
        chunk = e["chunk"]
        doc = e["doc"]
        is_policy = chunk.source_type != "transcript"
        eid = f"P{p_idx}" if is_policy else f"C{c_idx}"
        if is_policy:
            p_idx += 1
        else:
            c_idx += 1
        evidence.append(Evidence(
            evidence_id=eid,
            chunk_id=chunk.id,
            document_id=doc.id,
            source_type=chunk.source_type or doc.source_type,
            document_type=chunk.document_type or doc.document_type,
            person_id=chunk.person_id,
            session_id=chunk.session_id,
            session_date=chunk.session_date,
            page_number=chunk.page_number,
            heading_path=chunk.heading_path,
            text=e["text"],
            retrieval_text=e["retrieval_text"],
            relevance_score=e["score"],
            provenance=e["provenance"],
        ))
    return evidence

def render_context(evidence: list[Evidence]) -> str:
    policy = [e for e in evidence if e.evidence_id.startswith("P")]
    case = [e for e in evidence if e.evidence_id.startswith("C")]
    parts = []
    if policy:
        parts.append("POLICY EVIDENCE")
        for e in policy:
            parts.append(f"[{e.evidence_id}] Source: {e.provenance.get('title')} | Section: {' > '.join(e.heading_path or [])} | Page: {e.page_number}\nText: {e.text}")
    if case:
        parts.append("CASE EVIDENCE")
        for e in case:
            parts.append(f"[{e.evidence_id}] Source: {e.provenance.get('title')} | Person: {e.person_id} | Session: {e.session_id} | Date: {e.session_date} | Turns: {e.provenance.get('turn_start')}-{e.provenance.get('turn_end')} | Page: {e.page_number}\nText: {e.text}")
    return "\n\n".join(parts)
