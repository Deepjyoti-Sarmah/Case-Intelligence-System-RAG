from datetime import date
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Transcript(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    person_id: str  # nathan | robert
    session_id: str  # e.g. nathan_2025_04_14
    session_date: date
    metadata: dict = Field(default_factory=dict)


class TranscriptTurn(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    transcript_id: UUID
    sequence: int
    speaker: str = "unknown"  # NEVER invent — plan.md:174 plan traps:6
    speaker_confidence: float = 0.0
    raw_text: str
    normalized_text: str
    page_number: int
    is_question: bool = False  # trailing ? or leading interrogative
    timestamp_start: float | None = None
    timestamp_end: float | None = None
