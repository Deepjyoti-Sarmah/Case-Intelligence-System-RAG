from datetime import date
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    section_id: UUID | None = None
    transcript_id: UUID | None = None
    turn_start: int | None = None
    turn_end: int | None = None
    text: str  # shown to LLM/user — spec §9
    retrieval_text: str  # embedded + FTS-indexed — spec §9
    token_count: int | None = None
    position: int
    embedding: list[float] | None = None  # 384-dim bge-small-en-v1.5
    content_hash: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    # denormalised for single-table WHERE — plan.md:166
    person_id: str | None = None
    session_id: str | None = None
    session_date: date | None = None
    document_type: str | None = None
    source_type: str | None = None
    page_number: int | None = None
