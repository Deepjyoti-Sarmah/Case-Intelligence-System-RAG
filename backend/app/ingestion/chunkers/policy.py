import re

def _tokens(text: str) -> int:
    return int(len(text.split()) * 1.3) or 1

def chunk_policy_sections(sections, document_id, source_type, document_type, max_tokens=500):
    chunks = []
    pos = 0
    for s in sections:
        body = (s.body or "").strip()
        if not body:
            body = s.heading
        heading_path_str = " > ".join(s.heading_path) if s.heading_path else s.heading
        parts = [body]
        if _tokens(body) > max_tokens:
            paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
            if paras and len(paras) > 1:
                parts = []
                cur = ""
                for p in paras:
                    if _tokens(cur + "\n\n" + p) > max_tokens and cur:
                        parts.append(cur)
                        cur = p
                    else:
                        cur = (cur + "\n\n" + p).strip() if cur else p
                if cur:
                    parts.append(cur)
            else:
                words = body.split()
                step = 350
                parts = [" ".join(words[i:i+step]) for i in range(0, len(words), step)]
        for part in parts:
            text = part
            retrieval_text = f"{heading_path_str}\n{part}" if heading_path_str else part
            chunks.append({
                "document_id": document_id,
                "section_id": getattr(s, "id", None),
                "transcript_id": None,
                "turn_start": None,
                "turn_end": None,
                "text": text,
                "retrieval_text": retrieval_text,
                "token_count": _tokens(part),
                "position": pos,
                "heading_path": s.heading_path,
                "page_number": s.page_number,
                "source_type": source_type,
                "document_type": document_type,
                "metadata": {"section_heading": s.heading, "level": s.level},
            })
            pos += 1
    return chunks
