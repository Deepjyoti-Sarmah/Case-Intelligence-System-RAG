from dataclasses import dataclass
import uuid
from datetime import date

@dataclass
class Evidence:
    evidence_id: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    source_type: str
    document_type: str
    person_id: str | None
    session_id: str | None
    session_date: date | None
    page_number: int | None
    heading_path: list[str] | None
    text: str
    retrieval_text: str
    relevance_score: float
    provenance: dict
