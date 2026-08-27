# Case Intelligence RAG — Implementation Plan

## Context

The repo is empty (git initialised, zero commits). It contains only
`case-intelligence-rag-implementation-spec.md` plus two unpacked test-data folders.
We are building the system that spec describes, from scratch: a local,
Docker-Compose'd RAG app over 5 client transcripts and 5 reference documents, with a
single-page React UI that answers open-ended questions and shows the evidence behind
each answer.

The point of the exercise is **not** "chunk → embed → stuff into an LLM". It is an
evidence-retrieval system whose every answer can be traced back through
`query plan → filters → candidates → fused → reranked → evidence → claims → citations`.
The graders will probe cross-transcript reasoning, policy-vs-transcript comparison,
temporal questions, and — importantly — questions with *no* answer in the corpus, where
the correct behaviour is to say so.

This plan is written to be executed by an implementing agent. Follow the phases in
order; each has a concrete acceptance check.

---

## Locked decisions

| Concern | Decision | Rationale |
|---|---|---|
| Embeddings | **Local `fastembed`, `BAAI/bge-small-en-v1.5`, 384-dim** | No API key, offline, free, model baked into the image. Corpus is ~90 pages. |
| Reranker | **Local cross-encoder `BAAI/bge-reranker-base`** | Deterministic, ~100ms, and honestly A/B-able against fusion-only in Phase 9. |
| LLM | **Anthropic `claude-opus-5`** via the official `anthropic` Python SDK | Query planning + answer generation. |
| Speaker attribution | **Always `unknown`, confidence `0.0`. No heuristics, no LLM labelling.** | The transcripts contain zero speaker labels (verified). Spec §10 and §49.2 forbid inventing them. |
| Datastore | **PostgreSQL 16 + `pgvector`**, one container | Spec §4. No separate vector DB or search engine. |

**Do not** add a graph DB, agent loop, Redis, Kafka, or a second embedding model (spec §50).

---

## Ground truth about the corpus (verified — build the parsers to these facts)

### Transcripts — `transcriptions_for_test/`

| File | Pages | Person | Session date |
|---|---|---|---|
| `nathan-04-14.pdf` | 7 | nathan | 2025-04-14 |
| `nathan-05-19.pdf` | 8 | nathan | 2025-05-19 |
| `nathan-06-02.pdf` | 6 | nathan | 2025-06-02 |
| `robert-05-07.pdf` | 5 | robert | 2025-05-07 |
| `robert-5-21.pdf` | 10 | robert | 2025-05-21 |

Critical facts, all confirmed by extracting the text:

1. **No speaker labels. Anywhere.** Raw ASR output only.
2. **No timestamps.**
3. **Person and date exist only in the filename.** Note the inconsistent padding:
   `robert-5-21.pdf` vs `robert-05-07.pdf` — the regex must accept both
   (`^(?P<person>[a-z]+)-(?P<m>\d{1,2})-(?P<d>\d{1,2})\.pdf$`).
4. **No year in the filename.** Assume **2025** (file mtimes are 2025; and
   `nathan-05-19` says "June 2nd will be our next one", which matches `nathan-06-02`).
   Put the year in an explicit manifest, do not bury it in a regex.
5. **Two interleaved text styles within every file**, and this is the main parsing trap:
   - *Sentence-per-line, punctuated, cased* — e.g. `Yes, sir.` / `Drug screen was negative on the 26th.`
   - *Lowercase, unpunctuated, hard-wrapped mid-sentence run-ons* — e.g.
     `okay i'll get that caught up i got house taxes right now so if it gets a little high i` / `mean` / `yeah if i can drag it out ...`

   The second style **must have its wrapped lines re-joined** before turn segmentation,
   or you will get garbage turns like `mean`.
6. `.DS_Store` and `__MACOSX/` are present in both folders — **skip non-`.pdf` files**.

### Reference documents — `docs_for_test/`

| File | Pages | `source_type` | Structure |
|---|---|---|---|
| `8 Principles of Effective Intervention.pdf` | 1 | `evidence_based_practice` | Numbered list 1–8; item 3 has nested sub-items 1–5 (Risk / Need / Responsivity / Dosage / Treatment Principle) |
| `check-in-guidelines.pdf` | 1 | `policy` | Numbered 11-step procedure |
| `grievance-and-appeal.pdf` | 3 | `policy` | "Policy Number 148"; named sections (`Timeline for Filing a Grievance`, `Interviews and Investigation`, …) each with a numbered list |
| `internal-programming.pdf` | 3 | `service_reference` | Program catalog: `T4G:`, `MRT:`, `SQ:` … each with bullets (Length, focus, risk level) |
| `2022 Colorado Community Corrections Standards copy.pdf` | 63 | `state_standard` | Coded hierarchy `CS-010:` → `CS-011:`; TOC on pages 3–5; running footer on every page |

Parser-critical notes:

- **`check-in-guidelines.pdf` is the rubric the transcripts are graded against.** Its 11
  steps (confirm address → phone → employment → drug screen → ankle monitor →
  medications → fees → police contact → schedule → follow-up → personal life) map almost
  one-to-one onto what happens in every transcript. This is the highest-value
  cross-source pairing in the corpus — the "did the case manager follow procedure"
  class of question resolves here. Make sure each of the 11 steps is its own retrievable
  chunk carrying its step number.
- **Colorado Standards**: strip the repeating footer
  `2022 Colorado Community Corrections Standards` / `Published: October 2022` / `N | Page`
  before chunking, and **skip the TOC (pages 3–5)** — TOC lines look like headings and
  will pollute retrieval. Body headings match `^(?P<code>[A-Z]{2}-\d{3}):\s*(?P<title>.+)$`;
  indentation in the TOC indicates nesting (`CS-011` is a child of `CS-010`), but in the
  body use the code numbering itself to infer parent (`CS-011` → parent `CS-010`).
- **8 Principles**: `heading_path` must be `["8 Principles of Effective Intervention", "2. Enhance Intrinsic Motivation"]`
  style, with sub-principles nested under `3. Target Interventions`. Queries say
  "principle 2", "the risk principle", "dosage" — store `section_number` separately so
  these resolve deterministically, not just semantically.

---

## Repository layout

Follow spec §5 exactly. Create it at the repo root (the spec's outer
`case-intelligence-rag/` directory is *this* repo — do not nest another folder).

Also add at the root, before anything else:

- `.gitignore` — must exclude `.env`, `__pycache__/`, `node_modules/`, `.DS_Store`,
  `__MACOSX/`, `*.zip`, `data/processed/`, `.venv/`, model caches
- `.dockerignore`
- Move the corpus: `docs_for_test/` → `data/raw/documents/`,
  `transcriptions_for_test/` → `data/raw/transcripts/`. Commit the PDFs (they are the
  eval corpus). Delete `__MACOSX/`, the two `.zip` files, and both `.DS_Store` files.

---

## Phase 0 — Repo hygiene

- `git init` is already done; make the first commit.
- Create `.gitignore` / `.dockerignore`, relocate the corpus as above, remove the junk.
- `README.md` skeleton with a Quickstart section (filled in properly at Phase 10).

**Acceptance:** `git status` is clean; `data/raw/` holds 10 PDFs and nothing else.

---

## Phase 1 — Skeleton that boots

Files: `docker-compose.yml`, `backend/Dockerfile`, `backend/pyproject.toml`,
`backend/app/main.py`, `backend/app/config.py`, `frontend/` (Vite scaffold),
`frontend/Dockerfile`, `.env.example`, `Makefile`.

- Three services: `postgres` (image `pgvector/pgvector:pg16`), `backend` (uvicorn, port
  8000), `frontend` (Vite dev server or nginx, port 5173).
- Postgres healthcheck; backend `depends_on: {postgres: {condition: service_healthy}}`.
- `app/config.py`: a Pydantic `Settings` (from `pydantic-settings`) reading every var in
  spec §38 — `DATABASE_URL`, `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_MODEL`,
  `RERANKER_MODEL`, `TOP_K_LEXICAL=30`, `TOP_K_DENSE=30`, `TOP_K_RERANK=10`,
  `MAX_CONTEXT_TOKENS=8000`, `RRF_K=60`, `DEBUG_TRACE=false`, plus
  `ENABLE_RERANKER=true`. Never hardcode a key.
- `GET /health` (liveness only) and `GET /ready` (`SELECT 1` against the DB + assert
  required config present + assert `ANTHROPIC_API_KEY` is set).
- Alembic initialised against `DATABASE_URL`, with the `vector` extension created in the
  first migration (`CREATE EXTENSION IF NOT EXISTS vector`).
- `Makefile`: `up`, `down`, `ingest`, `reset-db`, `eval`, `test`, `fmt`.

**Acceptance:** `docker compose up --build` → `curl localhost:8000/health` and `/ready`
both 200; the Vite page loads.

---

## Phase 2 — Domain model and storage

Tables per spec §55: `documents`, `sections`, `transcripts`, `transcript_turns`,
`chunks`, `ingestion_runs`.

SQLAlchemy models in `app/storage/`, pure-Python domain dataclasses/Pydantic in
`app/domain/`. **The ORM model is not the domain model** (spec §6, §57) — keep the
mapping explicit in the repository layer.

Column notes beyond the spec's field lists:

- `documents.content_hash` — SHA-256, `UNIQUE`. Drives idempotency.
- `documents.source_type` — enum: `policy | service_reference | evidence_based_practice | state_standard | transcript`.
- `documents.authority` — enum per §24: `official_policy | official_standard | service_reference | case_transcript`.
- `chunks` carries **denormalised** `person_id`, `session_id`, `session_date`,
  `document_type`, `source_type`, `page_number` so hard filters are a single-table WHERE
  with no joins. This is deliberate.
- `chunks.retrieval_text` — the normalised text that gets embedded and FTS-indexed.
  `chunks.text` — what is shown to the LLM and the user. Keep both (§9).
- `chunks.embedding vector(384)`.
- `chunks.heading_path JSONB`, `chunks.metadata JSONB`.
- `transcript_turns`: `speaker` (default `'unknown'`), `speaker_confidence` (default
  `0.0`), `raw_text`, `normalized_text`, `sequence`, `page_number`, `is_question` (bool,
  set by a trailing `?` or a leading interrogative — used only for episode boundaries,
  never for role inference).

Indexes: `documents.content_hash`, `chunks.document_id`, `chunks.transcript_id`,
`chunks(person_id, session_date)`, `chunks.document_type`,
GIN on `to_tsvector('english', retrieval_text)`, and an HNSW index on
`chunks.embedding` with `vector_cosine_ops`.

**Acceptance:** `alembic upgrade head` creates all six tables; a round-trip unit test
inserts and reads back a Document + Chunk.

---

## Phase 3 — Ingestion

`app/ingestion/pipeline.py` orchestrates: discover → fingerprint → classify → parse →
normalise → chunk → enrich → persist → embed.

Use **`pypdf`** for text plus **`pdfplumber`** where layout matters (the Colorado
standards). Extract per page so `page_number` is always real, never estimated.

### 3a. Classification
Route by directory (`data/raw/transcripts/` vs `data/raw/documents/`) and confirm with a
filename map. Do not use an LLM to classify — there are ten files.

### 3b. Transcript parser — `app/ingestion/parsers/transcript.py`

This is the hardest component. Stages:

1. Extract text page by page, keeping `(page_number, line)` pairs.
2. **Re-join wrapped lines.** A line belongs to the previous line if the previous line
   does not end in `.?!` **and** the current line starts lowercase. Apply this only to
   the lowercase/unpunctuated style; leave the clean sentence-per-line style intact.
3. **Segment into turns.** Since there are no speaker labels, a "turn" is a sentence or
   short utterance group. Split the re-joined blocks on sentence boundaries; for the
   unpunctuated run-ons, split on discourse markers (`yeah`, `okay`, `all right`, `so`,
   `right`) only when the segment exceeds ~30 words, so short exchanges stay whole.
   A turn is never allowed to be empty or whitespace-only.
4. Set `speaker='unknown'`, `speaker_confidence=0.0` on every turn. **No exceptions.**
5. Store `raw_text` verbatim from step 1–2 and `normalized_text` (lowercased, collapsed
   whitespace, filler `um/uh` removed) separately.
6. `sequence` is a 0-based counter across the whole session.

### 3c. Policy parsers — `app/ingestion/parsers/policy.py`

One generic hierarchical parser driven by a per-document heading spec, rather than five
bespoke parsers:

- Colorado: heading regex `^([A-Z]{2}-\d{3}):\s*(.+)$`, footer strip, skip pages 3–5,
  parent inferred from the code (`CS-011` → `CS-010`; `CS-010` → section family `CS`).
- 8 Principles: `^\s*(\d)\.\s+(.+?)\s+-\s+(.*)$` for top level,
  `^\s{8,}(\d)\.\s+(.+?)\s+-\s+(.*)$` for the nested sub-principles under item 3.
- check-in-guidelines: `^\s*(\d{1,2})\.\s+(.+)$`, each step its own section, with the
  intro paragraph as section 0.
- grievance: title-case standalone lines that are not list items become sections;
  capture `Policy Number 148` into `document.version`/metadata.
- internal-programming: `^([A-Z0-9]{2,4}):\s*(.+)$` for program entries.

Every `Section` records `heading`, `level`, `position`, `page_number`,
`parent_section_id`, and the parser writes the full `heading_path` onto each chunk.

### 3d. Chunking — `app/ingestion/chunkers/`

- **Policy chunker:** one chunk per leaf section. If a section exceeds ~500 tokens,
  split on paragraph boundaries and repeat the `heading_path` on each part. Never merge
  across sections. Prepend the heading path to `retrieval_text` (not to `text`) so
  lexical search can match "risk principle" even when the body never repeats the phrase.
- **Transcript chunker:** episode-based (spec §11). Group consecutive turns into
  episodes of ~6–12 turns, cutting at a boundary when a turn introduces a new topic
  keyword from a small controlled vocabulary (address, phone, employment, drug screen,
  ankle monitor, medication, fees, police contact, schedule, family, health, treatment,
  jail) **and** the current episode already has ≥4 turns. Never cut between a question
  turn and the turn immediately after it. Store `turn_start`/`turn_end`.

### 3e. Enrichment and persistence

- Denormalise person/session/date/type onto every chunk.
- Tag each transcript chunk with the topic keywords it hit, in `metadata.topics` — the
  theme-extraction flow (§28) uses these for grouping.
- **Idempotency (§8.1):** hash the normalised source bytes. Same hash → no-op, log a
  skip. Changed hash → bump `version`, delete that document's chunks, re-insert.
  Wrap each document in one transaction. Record every run in `ingestion_runs`.
- Embed with fastembed in batches; write vectors in the same transaction.

`make ingest` runs this; it must be safe to run twice.

**Acceptance:** `make ingest` indexes 10 documents, 5 transcripts, >0 turns per
transcript, and a sane chunk count. Running it a second time inserts **zero** new rows.
Assert in a test that no `transcript_turns` row has `speaker != 'unknown'`, and that
every chunk resolves to a document + page.

---

## Phase 4 — Hybrid retrieval

`app/retrieval/`.

- `filters.py` — builds a SQL WHERE from a `QueryPlan`. All hard constraints
  (person, session, date range, document_type, source_type, section) are applied
  **here, before search** (§18, §49.6).
- `lexical.py` — Postgres FTS: `websearch_to_tsquery('english', :q)` against the GIN
  index, ranked by `ts_rank_cd`, `top_k = TOP_K_LEXICAL`.
- `vector.py` — pgvector cosine (`<=>`) over `chunks.embedding`, `top_k = TOP_K_DENSE`,
  same WHERE clause.
- `hybrid.py` — RRF: `score = Σ 1/(RRF_K + rank)` (§20), dedupe by `chunk_id`, keep the
  contributing per-retriever ranks on the candidate for the trace.
- `planner.py` is stubbed at this phase: it returns a generic plan (no filters, both
  sources) so retrieval can be tested standalone.

Define `Protocol`s (`LexicalRetriever`, `VectorRetriever`, `Reranker`,
`EmbeddingProvider`, `LLMProvider`) in `app/providers/` — the pgvector implementation
must be swappable (§57).

**Acceptance:** a `tests/retrieval/` test asserting "When should a client submit a
grievance?" puts `grievance-and-appeal.pdf` in the top 5, and "What happened with
Nathan's drug screen?" puts Nathan transcript chunks in the top 5.

---

## Phase 5 — Reranker

`app/retrieval/reranker.py`. `CrossEncoderReranker` wrapping `BAAI/bge-reranker-base`
over the fused pool (~40–60), returning `TOP_K_RERANK`. A `NoOpReranker` returns fused
order unchanged — selected when `ENABLE_RERANKER=false` **and** used as the automatic
fallback if the model fails to load (§39). Download the model at image build time, not
at first request.

**Acceptance:** the Phase 9 harness can run with `ENABLE_RERANKER` on and off and report
both numbers. Keep the reranker only if it wins (§ spec Phase 5).

---

## Phase 6 — Evidence builder

`app/generation/context.py` + `app/domain/evidence/`. Per §22:

1. Dedupe by `chunk_id`, then by near-identical text.
2. Re-verify scope filters against the plan (defence in depth).
3. **Parent expansion:** transcript chunks pull ±3 neighbouring turns from
   `transcript_turns` by `sequence`; policy chunks pull their parent section's heading
   and, if short, the sibling context.
4. Order transcript evidence chronologically (`session_date`, then `turn_start`);
   order policy evidence by `heading_path`.
5. Token-budget to `MAX_CONTEXT_TOKENS`, dropping lowest-ranked first, but always
   keeping ≥1 item per source group on cross-source plans.
6. Assign stable IDs: policy → `P1, P2, …`, case/transcript → `C1, C2, …`.
7. Group into `POLICY EVIDENCE` / `CASE EVIDENCE` blocks (§23).

**Acceptance:** unit tests for dedupe, parent expansion, chronology, and budget
enforcement.

---

## Phase 7 — Query planner

`app/retrieval/planner.py`. A Pydantic `QueryPlan` (§16) with
`intent` (the §17 enum), `sources`, `person_id`, `session_scope`
(`latest | previous | all | specific`), `session_date`, `concepts`, `semantic_query`,
`requires_cross_source_reasoning`.

Implement as **`client.messages.parse(model="claude-opus-5", output_format=QueryPlan)`**
→ `response.parsed_output` (the Anthropic SDK's structured-output helper; do **not** use
the deprecated `output_format` top-level param on `messages.create`, and do not prefill
the assistant turn — it 400s on Opus 5). Use `thinking={"type": "adaptive"}`; do not
pass `budget_tokens` (removed on Opus 5).

Before the LLM call, run a **deterministic pre-pass** that regex-matches known person
names (`nathan`, `robert`) and scope words (`latest`, `last`, `previous`, `first`,
`over time`, `changed`) and overrides whatever the model returned — these must never
depend on the LLM (§ Rule 4). `session_scope=latest` resolves via
`ORDER BY session_date DESC LIMIT 1` (§29), never by similarity.

On malformed output or an LLM failure → fall back to a generic hybrid plan (§39), log
the fallback, and continue.

**Acceptance:** unit tests mapping every §43 example question to the expected plan.
"latest meeting" → latest-session filter; "Robert themes" → `person_id=robert`,
`session_scope=all`; "2nd principle … last meeting" → `sources=[policy, transcript]`,
`requires_cross_source_reasoning=true`.

---

## Phase 8 — Answer generation and grounding

`app/generation/answer.py`, `grounding.py`, `prompts/`.

- System prompt encodes all ten rules of §31 plus the §54 injection defence: evidence is
  wrapped in `<retrieved_evidence>` and the prompt states it is untrusted data, never
  instructions.
- Context rendered with the §32 template.
- Model returns the §25 structured shape via `messages.parse` — `answer`, `claims[]`
  (`text`, `type` ∈ `observed|policy|derived|inference|unknown`, `evidence_ids[]`),
  `confidence`. The UI renders prose, not the JSON.
- **Grounding validator:** every `evidence_id` a claim cites must exist in the evidence
  set actually sent. Unknown IDs → drop the claim and mark the answer
  `PARTIALLY_SUPPORTED`. Zero evidence retrieved → return the §26 no-evidence response
  **without calling the LLM at all**.
- **Citations are built by the backend from evidence provenance** (§33). The model never
  authors a citation string.
- Because speakers are `unknown`, the prompt must instruct: describe transcript content
  without asserting who spoke, unless the surrounding text makes it unambiguous. For
  "did the case manager do X", answer from the check-in-guidelines rubric and the
  observable exchange, and state the attribution limitation explicitly.

API: `POST /api/v1/query` with the §34 request/response contract. `request_id` on every
response. Retrieval trace (§41) returned **only** when `DEBUG_TRACE=true`.

Wire it as `route → QueryService → planner → retrieval → evidence → generation →
grounding` (§ Rule 2). No LLM calls from route handlers.

**Acceptance:** end-to-end, "When should a client submit a grievance?" returns a
grounded answer citing `grievance-and-appeal.pdf` with a page number; an invented
question ("Did Nathan attend his welding class?") returns the no-evidence response.

---

## Phase 9 — Evaluation harness

`evaluation/`. `golden.jsonl` with ≥18 records covering every §43 category, including
**at least 3 no-evidence questions**. Record shape per §42, plus `expected_facts` and
`must_not_claim` where useful.

- `retrieval_metrics.py` — Recall@5, Recall@10, MRR, NDCG, reported overall **and per
  query type** (§44).
- `answer_metrics.py` — groundedness, citation correctness, and the key negative metric,
  **unsupported claim rate** (§45): fraction of claims whose `evidence_ids` are empty or
  unresolvable, plus an LLM-judge pass for answer relevance.
- `run_eval.py` — runs the set, writes a timestamped JSON to `reports/`, and diffs
  against `reports/baseline.json`, exiting non-zero if a core metric regresses beyond a
  configured tolerance (§46).
- Run it once with the reranker on and once off; record both. This is the Phase 5
  decision evidence.

**Acceptance:** `make eval` produces a report; the baseline is committed.

---

## Phase 10 — Frontend and hardening

**Frontend** (`frontend/src/`) — one page, exactly the §36 layout: question input + Ask
button, answer panel, sources/evidence list. Five states: `idle`, `loading`, `success`,
`error`, `empty`. Sources render title / section-or-session / page. No extra product
features, no chat history, no auth.

**Hardening:**
- `request_id` (UUID) generated per request, returned, and attached to every log line.
- Structured JSON logging (`structlog`) with the §40 fields. **Never log raw transcript
  text** unless `DEBUG_TRACE=true`.
- Timeouts on every external call; bounded retries (SDK default `max_retries=2`); no
  infinite loops.
- Degradation ladder per §39: dense fails → lexical only; reranker fails → fused order;
  planner fails → generic plan; **LLM fails → user-facing error, never a fabricated
  answer**.
- README: prerequisites, `.env` setup, `docker compose up --build`, `make ingest`,
  `make reset-db && make ingest`, `make eval`, plus a short architecture section and an
  honest "known limitations" note about speaker attribution.
- Auto-run idempotent ingestion on backend startup so a grader needs one command (§37).

**Acceptance:** fresh clone + `ANTHROPIC_API_KEY` + `docker compose up --build` yields a
working app; walk the §59 Definition-of-Done checklist and confirm every box.

---

## Verification

Run in this order once Phase 10 lands:

```bash
docker compose down -v && docker compose up --build -d
curl -s localhost:8000/health && curl -s localhost:8000/ready
make ingest && make ingest          # second run must insert nothing
make test                           # unit + integration
make eval                           # retrieval + generation metrics
```

Then exercise these by hand in the UI — they cover every reasoning mode the grader will
probe:

| Question | What it proves |
|---|---|
| When should a client submit a grievance? | Reference lookup, page-accurate citation |
| What happened with Nathan's drug screen? | Transcript lookup + person filter |
| What are some key themes that Robert talks about? | Cross-transcript, all sessions, not just the latest |
| Did the case manager follow the check-in guidelines in Nathan's last meeting? | Cross-source + `latest` resolved from `session_date` |
| Did the case manager use the 2nd principle of effective intervention in their last meeting? | Policy criterion vs observed behaviour, kept distinct |
| What changed between Nathan's meetings? | Temporal comparison across three sessions |
| What do you think are the client's biggest risks/needs? | Observed vs inferred, explicitly labelled |
| Did Nathan attend his welding class? | **No-evidence** — must decline, not confabulate |
| What is Nathan's relationship with his family like? | Semantic retrieval over conversational content |

For each: confirm the sources panel is populated, citations point at real pages, and
nothing is asserted about *who* spoke.

---

## Traps worth restating for the implementer

1. **Re-join the wrapped lowercase transcript lines** before turn segmentation, or turns
   will be fragments like `mean`.
2. **Skip the Colorado TOC (pages 3–5) and strip the running footer** — otherwise TOC
   entries out-rank real content.
3. **`robert-5-21.pdf` is not zero-padded.** Handle both filename shapes.
4. **Filter before retrieving, never after** — no cross-person leakage (§49.6).
5. **`latest` is SQL, not similarity** (§49.4).
6. **Never write a speaker other than `unknown`.**
7. **Citations come from the database, never from the model** (§49.9).
8. **The LLM is never asked to determine dates, people, or source identity** — the
   backend already knows them (§31).
