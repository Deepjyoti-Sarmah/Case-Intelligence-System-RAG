from sqlalchemy import and_
from app.retrieval.planner import QueryPlan
from app.storage.models import ChunkORM, TranscriptORM


def build_filters(plan: QueryPlan, session=None):
    conds = []
    if plan.person_id:
        conds.append(ChunkORM.person_id == plan.person_id.lower())
    if plan.document_type:
        conds.append(ChunkORM.document_type == plan.document_type)
    if plan.source_type:
        conds.append(ChunkORM.source_type == plan.source_type)
    if plan.sources:
        if len(plan.sources) == 1:
            src = plan.sources[0]
            if src == "transcript":
                conds.append(ChunkORM.source_type == "transcript")
            elif src in ("policy", "reference"):
                conds.append(ChunkORM.source_type != "transcript")
    if plan.session_scope == "latest" and plan.person_id and session is not None:
        latest = session.query(TranscriptORM.session_id).filter(TranscriptORM.person_id == plan.person_id.lower()).order_by(TranscriptORM.session_date.desc()).limit(1).scalar()
        if latest:
            conds.append(ChunkORM.session_id == latest)
    elif plan.session_scope == "latest" and plan.person_id and session is None:
        pass
    return conds
