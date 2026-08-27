def enrich_chunk(chunk: dict) -> dict:
    md = chunk.get("metadata") or {}
    if "topics" not in md and chunk.get("source_type") == "transcript":
        md["topics"] = []
    chunk["metadata"] = md
    if not chunk.get("document_type") and chunk.get("source_type"):
        chunk["document_type"] = chunk["source_type"]
    return chunk
