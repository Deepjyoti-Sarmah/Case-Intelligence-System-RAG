def validate(evidence_ids: set[str], claims: list[dict]) -> tuple[list[dict], str]:
    if not claims:
        return claims, "SUPPORTED"
    valid = []
    has_invalid = False
    for c in claims:
        ids = c.get("evidence_ids") or []
        if not ids:
            has_invalid = True
            continue
        if any(i not in evidence_ids for i in ids):
            has_invalid = True
            continue
        valid.append(c)
    status = "PARTIALLY_SUPPORTED" if has_invalid and valid else "SUPPORTED" if valid else "PARTIALLY_SUPPORTED"
    return valid, status

NO_EVIDENCE_ANSWER = "I could not find evidence in the indexed material to answer this question."
