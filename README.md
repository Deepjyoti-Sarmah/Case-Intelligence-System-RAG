# Case Intelligence System — Production RAG Application

A local, evidence-grounded RAG application built over 5 client transcripts (Nathan ×3, Robert ×2) and 5 reference documents (policies, state standards, service catalog, and evidence-based practice guidelines).

Every answer is deterministically backed by retrieved evidence: `query plan → filters → candidates → fused → reranked → evidence → claims → citations`.

---

## Architecture Overview

```text
                             USER / BROWSER
                                   |
                                   v
                        +---------------------+
                        |  React + Vite UI    |
                        +----------+----------+
                                   |
                                   v
                        +---------------------+
                        |  FastAPI Backend    |
                        +----------+----------+
                                   |
                                   v
                       +-----------------------+
                       |  Query Planner        |
                       +-----------+-----------+
                                   |
            +----------------------+----------------------+
            |                      |                      |
            v                      v                      v
       Hard Filters          Lexical Search         Dense Search
      (Person/Scope)           (Postgres FTS)        (pgvector)
            |                      |                      |
            +----------------------+----------------------+
                                   |
                                   v
                        +---------------------+
                        | Candidate RRF Fusion|
                        +----------+----------+
                                   |
                                   v
                        +---------------------+
                        | Cross-Encoder Rerank|
                        +----------+----------+
                                   |
                                   v
                        +---------------------+
                        |  Evidence Builder   |
                        +----------+----------+
                                   |
                                   v
                        +---------------------+
                        | LLM Generation      |
                        +----------+----------+
                                   |
                                   v
                        +---------------------+
                        | Grounding & Claims  |
                        +----------+----------+
                                   |
                                   v
                             Answer + Sources
```

---

## Quickstart (Single Command)

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY (optional for local fallback)
```

### 2. Single-Command Launch
```bash
docker compose up --build
```
*(or `make start`)*

That's it! Running this single command automatically:
1. Boots PostgreSQL with the `pgvector` extension.
2. Runs database migrations via Alembic.
3. Automatically ingests all 10 raw PDFs (client transcripts + policy standards) into PostgreSQL.
4. Starts the FastAPI backend at **http://localhost:8000**.
5. Starts the React single-page UI at **http://localhost:5173**.

---

## Evaluation & Testing

```bash
make eval  # Run 21-question golden evaluation harness
make test  # Run pytest unit and integration tests
make ingest # Run manual re-ingestion if raw PDFs are modified
```

---

## Known Limitations

- **Speaker Attribution**: Transcript turns default to `speaker="unknown"` (`confidence=0.0`). The raw source PDFs contain no speaker labels; per spec §10 & §49.2, the system never invents or hallucinates speaker identities.
- **Colorado Standards Processing**: Pages 3–5 (Table of Contents) and running footers are automatically stripped during ingestion to avoid TOC keyword pollution during lexical and dense retrieval.
- **Corpus Constraints**: Corpus comprises 10 PDFs (~90 pages total). Data storage uses a single PostgreSQL 16 + pgvector instance without external vector databases or message queues per spec §4.

