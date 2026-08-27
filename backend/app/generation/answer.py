import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Literal

from app.config import settings
from app.domain.evidence import Evidence
from app.generation.context import render_context
from app.generation.grounding import NO_EVIDENCE_ANSWER, validate

logger = logging.getLogger(__name__)

class Claim(BaseModel):
    text: str
    type: Literal["observed", "policy", "derived", "inference", "unknown"]
    evidence_ids: list[str] = Field(default_factory=list)

class StructuredAnswer(BaseModel):
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    grounding_status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "NO_EVIDENCE"] = "SUPPORTED"

SYSTEM_PROMPT = Path(__file__).parent.joinpath("prompts/system.txt").read_text()

def _render_user(question: str, evidence: list[Evidence]) -> str:
    ctx = render_context(evidence)
    return f"""QUESTION
{question}

TASK
Answer using only the evidence above. Distinguish policy statements from observations and observations from inference. If evidence is insufficient, state that explicitly. Do not invent sources or facts.

<retrieved_evidence>
{ctx}
</retrieved_evidence>

INSTRUCTIONS
- Answer using only the evidence above.
- Distinguish policy statements from observations.
- Distinguish observations from inference.
- If evidence is insufficient, state that explicitly.
- Do not invent sources or facts.
"""

def _fallback_answer(question: str, evidence: list[Evidence]) -> StructuredAnswer:
    if not evidence:
        return StructuredAnswer(answer=NO_EVIDENCE_ANSWER, claims=[], confidence="high")
    # pick most relevant by score, not just first ordered
    top = max(evidence, key=lambda e: e.relevance_score)
    claims = [Claim(text=top.text[:200], type="policy" if top.evidence_id.startswith("P") else "observed", evidence_ids=[top.evidence_id])]
    for e in evidence:
        if e.evidence_id == top.evidence_id:
            continue
        if len(claims) >= 3:
            break
        ctype = "policy" if e.evidence_id.startswith("P") else "observed"
        claims.append(Claim(text=e.text[:200], type=ctype, evidence_ids=[e.evidence_id]))
    answer = f"Based on the retrieved evidence: {top.text[:600]}"
    if len(evidence) > 1:
        answer += f"\n\nAdditional context from {len(evidence)-1} other sources supports this."
    return StructuredAnswer(answer=answer, claims=claims, confidence="medium")

def generate_answer(question: str, evidence: list[Evidence]) -> StructuredAnswer:
    if not evidence:
        return StructuredAnswer(answer=NO_EVIDENCE_ANSWER, claims=[], confidence="high", grounding_status="NO_EVIDENCE")
    if not settings.anthropic_api_key or settings.anthropic_api_key == "dummy-key-for-local-boot":
        return _fallback_answer(question, evidence)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=30.0, max_retries=2)
        user_content = _render_user(question, evidence)
        resp = client.messages.parse(
            model=settings.llm_model,
            max_tokens=1500,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_format=StructuredAnswer,
        )
        parsed: StructuredAnswer = resp.parsed_output  # type: ignore
        evidence_ids = {e.evidence_id for e in evidence}
        valid_claims, status = validate(evidence_ids, [c.model_dump() for c in parsed.claims])
        if status == "PARTIALLY_SUPPORTED" and not valid_claims:
            parsed.answer = parsed.answer + "\n\nNote: some claims lacked supporting evidence and were omitted."
        parsed.claims = [Claim(**c) for c in valid_claims]
        parsed.grounding_status = status
        return parsed
    except Exception as e:
        logger.warning("LLM generate failed: %s", e)
        return _fallback_answer(question, evidence)
