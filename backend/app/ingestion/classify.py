import re
from dataclasses import dataclass
from pathlib import Path

TRANSCRIPT_DIR = Path("data/raw/transcripts")
DOCUMENT_DIR = Path("data/raw/documents")

# plan.md:54 — must accept both robert-5-21.pdf and robert-05-07.pdf
TRANSCRIPT_RE = re.compile(r"^(?P<person>[a-z]+)-(?P<m>\d{1,2})-(?P<d>\d{1,2})\.pdf$")

# year manifest — plan.md:58-59, do not bury in regex
TRANSCRIPT_YEAR = 2025


@dataclass(frozen=True)
class ClassifiedFile:
    path: Path
    kind: str  # transcript | document
    person: str | None = None
    session_date: str | None = None  # YYYY-MM-DD
    session_id: str | None = None


def classify(path: Path) -> ClassifiedFile | None:
    if not path.is_file() or path.suffix.lower() != ".pdf":
        return None
    if "__MACOSX" in path.parts or path.name == ".DS_Store":
        return None

    # route by directory — plan.md:197
    if TRANSCRIPT_DIR in path.parents or path.parent.name == "transcripts":
        m = TRANSCRIPT_RE.match(path.name)
        if not m:
            return None
        person = m.group("person").lower()
        month = int(m.group("m"))
        day = int(m.group("d"))
        date_str = f"{TRANSCRIPT_YEAR}-{month:02d}-{day:02d}"
        session_id = f"{person}_{TRANSCRIPT_YEAR}_{month:02d}_{day:02d}"
        return ClassifiedFile(path=path, kind="transcript", person=person, session_date=date_str, session_id=session_id)

    if DOCUMENT_DIR in path.parents or path.parent.name == "documents":
        return ClassifiedFile(path=path, kind="document")

    # fallback: try transcript regex anyway
    m = TRANSCRIPT_RE.match(path.name)
    if m:
        person = m.group("person").lower()
        month = int(m.group("m"))
        day = int(m.group("d"))
        date_str = f"{TRANSCRIPT_YEAR}-{month:02d}-{day:02d}"
        session_id = f"{person}_{TRANSCRIPT_YEAR}_{month:02d}_{day:02d}"
        return ClassifiedFile(path=path, kind="transcript", person=person, session_date=date_str, session_id=session_id)

    return ClassifiedFile(path=path, kind="document")
