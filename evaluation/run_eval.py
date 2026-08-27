"""Evaluation harness entry point.

Runs the golden question set through the real retrieval/generation pipeline (the same
functions the API route uses — no HTTP hop), computes retrieval and answer metrics once
with the reranker on and once with it off, writes a timestamped report to reports/, and
diffs the reranker-on run against reports/baseline.json. Exits non-zero if a core metric
regresses beyond tolerance.

Usage: python evaluation/run_eval.py   (run inside the backend container, or anywhere
`app` and this directory are both importable — see Makefile `eval` target)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import retrieval_metrics as rm
import answer_metrics as am

from app.services.query import execute_query
from app.generation.grounding import NO_EVIDENCE_ANSWER
from app.storage.database import SessionLocal

DATASET_PATH = Path(__file__).parent / "datasets" / "golden.jsonl"
REPORTS_DIR = Path(__file__).parent / "reports"
BASELINE_PATH = REPORTS_DIR / "baseline.json"

REGRESSION_TOLERANCE = 0.05  # absolute drop allowed on core metrics before failing


def load_golden() -> list[dict]:
    records = []
    with open(DATASET_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def run_record(session, record: dict, rerank: bool) -> dict:
    question = record["question"]
    res = execute_query(session, question, rerank=rerank)

    retrieved_files = res.get("retrieved_files", [])
    retrieval_scores = rm.score_query(retrieved_files, record.get("expected_sources", []))

    evidence = res.get("evidence", [])
    valid_ids = {e.evidence_id for e in evidence}
    source_files = [e.provenance.get("file_name", "") for e in evidence]

    structured = res.get("structured_answer")
    answer = res["answer"]
    grounding_status = res["metadata"].get("grounding_status", "NO_EVIDENCE")

    claims = [c.model_dump() for c in structured.claims] if structured else []

    grounding_scores = am.claim_grounding(claims, valid_ids)
    answer_scores = {
        "citation_correctness": am.citation_correctness(source_files, record.get("expected_sources", [])),
        "fact_coverage": am.fact_coverage(answer, record.get("expected_facts", [])),
        "answer_relevance": am.llm_judge_relevance(question, answer),
        **grounding_scores,
    }

    result = {
        "id": record["id"],
        "type": record["type"],
        "question": question,
        "retrieved_files": retrieved_files,
        "answer": answer,
        "grounding_status": grounding_status,
    }

    if record["type"] == "no_evidence":
        answer_scores["no_evidence_correct"] = am.no_evidence_correct(
            grounding_status, answer, NO_EVIDENCE_ANSWER
        )
        answer_scores["must_not_claim_violation"] = am.must_not_claim_violation(
            answer, record.get("must_not_claim", [])
        )
    else:
        result["retrieval"] = {"type": record["type"], "scores": retrieval_scores}

    result["answer_scores"] = answer_scores
    return result



def run_pass(session, records: list[dict], rerank: bool) -> dict:
    results = [run_record(session, r, rerank) for r in records]

    retrieval_inputs = [r["retrieval"] for r in results if "retrieval" in r]
    retrieval_report = rm.aggregate(retrieval_inputs) if retrieval_inputs else {"overall": {}, "per_type": {}}

    answer_inputs = [{"type": r["type"], "scores": r["answer_scores"]} for r in results]
    answer_report = am.aggregate(answer_inputs)

    no_evidence_results = [r for r in results if r["type"] == "no_evidence"]
    violations = [r["id"] for r in no_evidence_results if r["answer_scores"].get("must_not_claim_violation")]

    return {
        "retrieval": retrieval_report,
        "answer": answer_report,
        "no_evidence_violations": violations,
        "records": results,
    }


def check_regression(current: dict, baseline: dict) -> list[str]:
    failures = []
    cur_recall = current["retrieval"]["overall"].get("recall_at_10")
    base_recall = baseline.get("retrieval", {}).get("overall", {}).get("recall_at_10")
    if cur_recall is not None and base_recall is not None and cur_recall < base_recall - REGRESSION_TOLERANCE:
        failures.append(f"Recall@10 regressed: {base_recall:.3f} -> {cur_recall:.3f}")

    cur_unsupported = current["answer"]["overall"].get("unsupported_claim_rate")
    base_unsupported = baseline.get("answer", {}).get("overall", {}).get("unsupported_claim_rate")
    if cur_unsupported is not None and base_unsupported is not None and cur_unsupported > base_unsupported + REGRESSION_TOLERANCE:
        failures.append(f"unsupported_claim_rate regressed: {base_unsupported:.3f} -> {cur_unsupported:.3f}")

    if current["no_evidence_violations"]:
        failures.append(f"no-evidence questions produced a claimed fact: {current['no_evidence_violations']}")

    return failures


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    records = load_golden()

    with SessionLocal() as session:
        reranked = run_pass(session, records, rerank=True)
        no_rerank = run_pass(session, records, rerank=False)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(DATASET_PATH),
        "num_records": len(records),
        "reranker_on": reranked,
        "reranker_off": no_rerank,
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = REPORTS_DIR / f"report_{timestamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {out_path}")

    print("\n=== Retrieval (reranker ON) — overall ===")
    print(json.dumps(reranked["retrieval"]["overall"], indent=2))
    print("\n=== Retrieval (reranker OFF) — overall ===")
    print(json.dumps(no_rerank["retrieval"]["overall"], indent=2))
    print("\n=== Answer metrics (reranker ON) — overall ===")
    print(json.dumps(reranked["answer"]["overall"], indent=2))

    if not BASELINE_PATH.exists():
        BASELINE_PATH.write_text(json.dumps(reranked, indent=2, default=str))
        print(f"\nno baseline found — bootstrapped {BASELINE_PATH} from this run")
        return 0

    baseline = json.loads(BASELINE_PATH.read_text())
    failures = check_regression(reranked, baseline)
    if failures:
        print("\nREGRESSION DETECTED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nno regression vs baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
