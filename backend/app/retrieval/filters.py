from sqlalchemy import and_
from app.retrieval.planner import QueryPlan
from app.storage.models import ChunkORM


def build_filters(plan: QueryPlan):
    conds = []
    if plan.person_id:
        conds.append(ChunkORM.person_id == plan.person_id.lower())
    if plan.document_type:
        conds.append(ChunkORM.document_type == plan.document_type)
    if plan.source_type:
        conds.append(ChunkORM.source_type == plan.source_type)
    if plan.sources:
        # sources is list like ["policy","transcript"] — map to source_type/document_type
        # for phase 4 stub we ignore if both present (no filter)
        if len(plan.sources) == 1:
            src = plan.sources[0]
            if src == "transcript":
                conds.append(ChunkORM.source_type == "transcript")
            elif src in ("policy", "reference"):
                conds.append(ChunkORM.source_type != "transcript")
    return conds
