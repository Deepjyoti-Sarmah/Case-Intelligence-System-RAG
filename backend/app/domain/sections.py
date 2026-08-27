from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Section(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    parent_section_id: UUID | None = None
    heading: str
    level: int
    position: int
    page_number: int
