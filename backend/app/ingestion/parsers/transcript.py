import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

# plan.md:212 — discourse markers only when segment > ~30 words
DISCOURSE_MARKERS = re.compile(r"^(yeah|okay|ok|all right|alright|so|right|mean|well|uh|um)\b", re.IGNORECASE)
# question detection for is_question — plan.md:175
QUESTION_RE = re.compile(r"\?\s*$")
LEADING_INTERROGATIVE = re.compile(r"^(what|when|where|who|why|how|is|are|did|do|does|have|has|can|could|would|will)\b", re.IGNORECASE)
FILLER_RE = re.compile(r"\b(um|uh)\b", re.IGNORECASE)


@dataclass
class ParsedTurn:
    sequence: int
    speaker: str  # always unknown per plan traps:6
    speaker_confidence: float
    raw_text: str
    normalized_text: str
    page_number: int
    is_question: bool


@dataclass
class ParsedTranscript:
    person: str
    session_date: str  # YYYY-MM-DD
    session_id: str
    turns: list[ParsedTurn]


def _extract_pages(path: Path) -> list[tuple[int, list[str]]]:
    """Extract per page lines preserving page_number — plan.md:194."""
    reader = PdfReader(str(path))
    pages: list[tuple[int, list[str]]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        # keep line boundaries as delivered by pypdf
        lines = text.splitlines()
        pages.append((idx, lines))
    return pages


def _rejoin_wrapped(pages: list[tuple[int, list[str]]]) -> list[tuple[int, str]]:
    """
    Re-join wrapped lines — plan.md:205.
    A line belongs to previous if previous does NOT end in .?! and current starts lowercase.
    Only apply to lowercase/unpunctuated style; leave clean sentence-per-line intact.
    Returns list of (page_number, rejoined_block).
    """
    rejoined: list[tuple[int, str]] = []
    for page_num, lines in pages:
        # filter empties but keep page association
        buf: list[str] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if not buf:
                buf.append(line)
                continue
            prev = buf[-1]
            # condition: previous does NOT end in .?! and current starts lowercase
            if not re.search(r"[.!?]\s*$", prev) and line and line[0].islower():
                # re-join with space
                buf[-1] = prev + " " + line
            else:
                buf.append(line)
        for block in buf:
            rejoined.append((page_num, block))
    return rejoined


def _normalize(text: str) -> str:
    # plan.md:214-215 lowercased, collapsed whitespace, filler um/uh removed
    t = text.lower()
    t = FILLER_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _is_question(text: str) -> bool:
    t = text.strip()
    if QUESTION_RE.search(t):
        return True
    if LEADING_INTERROGATIVE.match(t):
        return True
    return False


def _segment_turns(blocks: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """
    Segment rejoined blocks into turns — plan.md:212.
    - Split on sentence boundaries for clean style (already sentence-per-line)
    - For unpunctuated run-ons, split on discourse markers only when segment >30 words
    - Never empty
    """
    turns: list[tuple[int, str]] = []
    for page_num, block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        # If block contains sentence punctuation, treat as one turn (clean style)
        # but also split overly long clean blocks on sentence boundaries (keep whole for now)
        # For unpunctuated style (no .?! in block and many words), apply word-count + marker split
        has_punct = bool(re.search(r"[.!?]", stripped))
        words = stripped.split()
        if not has_punct and len(words) > 30:
            # split on discourse markers when segment >30 words
            current: list[str] = []
            cur_len = 0
            # naive token walk: split into sentences by marker detection
            # we iterate words and start new turn when we hit marker and cur_len >=30
            # Simpler: split block into chunks at marker boundaries
            parts: list[str] = []
            # split block by marker regex preserving marker start
            # Use split keeping delimiter
            tokens = re.split(r"\s+(?=(?:yeah|okay|ok|all right|alright|so|right|mean|well)\b)", stripped, flags=re.IGNORECASE)
            for part in tokens:
                part = part.strip()
                if not part:
                    continue
                pw = len(part.split())
                if cur_len + pw > 30 and current:
                    turns.append((page_num, " ".join(current).strip()))
                    current = [part]
                    cur_len = pw
                else:
                    current.append(part)
                    cur_len += pw
            if current:
                turns.append((page_num, " ".join(current).strip()))
        else:
            # sentence boundary kept as single turn; but if block is huge and has punctuation, split on sentence
            if has_punct and len(words) > 60:
                # split on sentence boundaries
                sentences = re.split(r"(?<=[.!?])\s+", stripped)
                for s in sentences:
                    s = s.strip()
                    if s:
                        turns.append((page_num, s))
            else:
                turns.append((page_num, stripped))

    # filter empties
    return [(p, t) for p, t in turns if t.strip()]


def parse_transcript(path: Path, person: str, session_date: str, session_id: str) -> ParsedTranscript:
    pages = _extract_pages(path)
    rejoined = _rejoin_wrapped(pages)
    segmented = _segment_turns(rejoined)

    turns: list[ParsedTurn] = []
    for idx, (page_num, raw) in enumerate(segmented):
        normalized = _normalize(raw)
        if not normalized:
            continue
        is_q = _is_question(raw)
        turns.append(
            ParsedTurn(
                sequence=idx,
                speaker="unknown",
                speaker_confidence=0.0,
                raw_text=raw,
                normalized_text=normalized,
                page_number=page_num,
                is_question=is_q,
            )
        )

    # re-index sequence after filtering
    for i, t in enumerate(turns):
        t.sequence = i

    return ParsedTranscript(person=person, session_date=session_date, session_id=session_id, turns=turns)
