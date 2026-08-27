from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    policy = "policy"
    service_reference = "service_reference"
    evidence_based_practice = "evidence_based_practice"
    state_standard = "state_standard"
    transcript = "transcript"


class Authority(str, Enum):
    official_policy = "official_policy"
    official_standard = "official_standard"
    service_reference = "service_reference"
    case_transcript = "case_transcript"


class Document(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    source_type: SourceType
    document_type: str  # denormalised alias of source_type for filters
    authority: Authority
    file_name: str
    content_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    effective_from: date | None = None
    effective_to: date | None = None
    version: int = 1
    metadata: dict = Field(default_factory=dict)
