from dataclasses import dataclass, field


@dataclass
class QueryPlan:
    semantic_query: str
    person_id: str | None = None
    session_scope: str | None = None
    session_date: str | None = None
    sources: list[str] = field(default_factory=list)
    document_type: str | None = None
    source_type: str | None = None
    intent: str = "UNKNOWN"
    concepts: list[str] = field(default_factory=list)
    requires_cross_source_reasoning: bool = False


def plan_query(question: str) -> QueryPlan:
    return QueryPlan(semantic_query=question, sources=["policy", "transcript"])
