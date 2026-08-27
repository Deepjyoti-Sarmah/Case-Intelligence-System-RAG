import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.retrieval.hybrid import hybrid_search
from app.retrieval.planner import QueryPlan

def _engine():
    url = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/rag")
    if "postgres:5432" in url:
        try:
            e = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
            with e.connect() as c:
                c.execute(__import__("sqlalchemy").text("SELECT 1"))
            return e
        except Exception:
            url = "postgresql+psycopg://postgres:postgres@localhost:5433/rag"
    return create_engine(url)

def test_grievance_top5():
    eng = _engine()
    with Session(eng) as s:
        res = hybrid_search(s, "When should a client submit a grievance?")
        top_files = [r.file_name for r in res[:5]]
        assert any("grievance" in f.lower() for f in top_files), f"top5 {top_files}"

def test_nathan_drug_screen_top5():
    eng = _engine()
    with Session(eng) as s:
        res = hybrid_search(s, "What happened with Nathan's drug screen?")
        top_files = [r.file_name for r in res[:5]]
        # at least one Nathan transcript chunk should be in top5
        assert any("nathan" in f.lower() for f in top_files), f"top5 {top_files}"
