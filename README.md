# Case Intelligence RAG

Local, evidence-grounded RAG over 5 client transcripts (Nathan ×3, Robert ×2) and 5 reference documents (policies, standards, service catalog, EBP).

Every answer traces: `query plan → filters → candidates → fused → reranked → evidence → claims → citations`.

## Quickstart

```bash
cp .env.example .env        # set ANTHROPIC_API_KEY
docker compose up --build   # backend :8000, frontend :5173, postgres :5432
make ingest                 # idempotent — safe to run twice
```

Verify:

```bash
curl localhost:8000/health  # liveness
curl localhost:8000/ready   # db + config check
```

Other commands:

```bash
make reset-db && make ingest
make eval                   # retrieval + answer harness
make test                   # unit + integration
make fmt
```

## Architecture

- **Backend:** FastAPI + SQLAlchemy + Alembic, PostgreSQL 16 + pgvector
- **Retrieval:** Hybrid lexical (FTS) + dense (pgvector) → RRF fusion → cross-encoder rerank (`BAAI/bge-reranker-base`)
- **Embeddings:** `fastembed` / `BAAI/bge-small-en-v1.5` (384-dim, local)
- **LLM:** Anthropic `claude-opus-5` for query planning + answer generation
- **Frontend:** React + TypeScript + Vite (single page: question → answer + sources)

See `plan.md` for the full phased implementation plan and `case-intelligence-rag-implementation-spec.md` for the spec.

## Known limitations

- Transcript `speaker` is always `unknown` (`confidence 0.0`) — no speaker labels exist in the source PDFs; the system never invents attribution.
- Colorado Standards TOC (pages 3–5) and running footer are stripped at ingestion; body headings match `CS-###: Title`.
- Corpus is 10 PDFs (~90 pages) — one Postgres + pgvector instance, no separate vector DB.

## Corpus layout

```
data/raw/documents/   # 5 reference PDFs
data/raw/transcripts/ # 5 transcript PDFs
```

Run `make ingest` after any corpus change; ingestion is content-hash idempotent.
