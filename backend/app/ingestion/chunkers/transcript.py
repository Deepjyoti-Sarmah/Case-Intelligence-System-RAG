import re

TOPIC_KEYWORDS = ["address","phone","employment","drug screen","ankle monitor","medication","medications","fees","police contact","schedule","family","health","treatment","jail","job","work","housing","court","probation","fees","money","taxes"]

def _has_topic(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in TOPIC_KEYWORDS)

def _is_question_turn(turn) -> bool:
    return bool(getattr(turn, "is_question", False))

def chunk_transcript_turns(turns, document_id, transcript_id, person_id, session_id, session_date, source_type="transcript", document_type="transcript"):
    chunks = []
    if not turns:
        return chunks
    episodes: list[list] = []
    cur: list = []
    for idx, turn in enumerate(turns):
        cur.append(turn)
        if len(cur) >= 4 and len(cur) < 12:
            nxt = turns[idx+1] if idx+1 < len(turns) else None
            if nxt and _has_topic(nxt.raw_text) and not _is_question_turn(turn):
                if len(cur) >= 6 or _has_topic(nxt.raw_text):
                    episodes.append(cur)
                    cur = []
                    continue
        if len(cur) >= 12:
            if _is_question_turn(turn) and idx+1 < len(turns):
                continue
            episodes.append(cur)
            cur = []
    if cur:
        if episodes and len(cur) < 4:
            episodes[-1].extend(cur)
        else:
            episodes.append(cur)

    pos = 0
    for ep in episodes:
        if not ep:
            continue
        texts = [t.raw_text for t in ep]
        retrieval_texts = [t.normalized_text for t in ep]
        text = "\n".join(texts)
        retrieval_text = " ".join(retrieval_texts)
        turn_start = ep[0].sequence
        turn_end = ep[-1].sequence
        page_number = ep[0].page_number
        topics = sorted({kw for kw in TOPIC_KEYWORDS if kw in retrieval_text})
        chunks.append({
            "document_id": document_id,
            "section_id": None,
            "transcript_id": transcript_id,
            "turn_start": turn_start,
            "turn_end": turn_end,
            "text": text,
            "retrieval_text": retrieval_text,
            "token_count": int(len(retrieval_text.split())*1.3),
            "position": pos,
            "heading_path": None,
            "page_number": page_number,
            "person_id": person_id,
            "session_id": session_id,
            "session_date": session_date,
            "source_type": source_type,
            "document_type": document_type,
            "metadata": {"topics": topics, "turn_count": len(ep)},
        })
        pos += 1
    return chunks
