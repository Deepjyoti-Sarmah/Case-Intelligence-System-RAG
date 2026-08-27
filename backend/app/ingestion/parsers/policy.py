import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

try:
    import pdfplumber

    HAS_PLUMBER = True
except ImportError:
    HAS_PLUMBER = False


@dataclass
class ParsedSection:
    heading: str
    level: int
    position: int
    page_number: int
    parent_idx: int | None
    body: str
    heading_path: list[str]


COLORADO_RE = re.compile(r"^([A-Z]{2}-\d{3}):\s*(.+)$")
PRINCIPLES_TOP = re.compile(r"^\s*(\d)\.\s+(.+?)(?:\s+-\s+(.*))?$")
PRINCIPLES_SUB = re.compile(r"^\s{8,}(\d)\.\s+(.+?)(?:\s+-\s+(.*))?$")
CHECKIN_RE = re.compile(r"^\s*(\d{1,2})\.\s+(.+)$")
PROGRAM_RE = re.compile(r"^([A-Z0-9]{2,4}):\s*(.+)$")
FOOTER_PATTERNS = [
    "2022 Colorado Community Corrections Standards",
    "Published: October 2022",
]


def _read_pages_pypdf(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    out = []
    for i, p in enumerate(reader.pages, start=1):
        out.append((i, p.extract_text() or ""))
    return out


def _read_pages_plumber(path: Path) -> list[tuple[int, str]]:
    if not HAS_PLUMBER:
        return _read_pages_pypdf(path)
    out = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            out.append((i, page.extract_text() or ""))
    return out


def _strip_colorado_footer(text: str) -> str:
    for pat in FOOTER_PATTERNS:
        text = text.replace(pat, "")
    text = re.sub(r"\bN\s*\|\s*Page\b", "", text)
    text = re.sub(r"\|\s*Page\s*\d+", "", text)
    return text


def _colorado_parent(code: str) -> str | None:
    m = re.match(r"([A-Z]{2})-(\d{3})", code)
    if not m:
        return None
    num = int(m.group(2))
    if num % 10 == 0 or num == 10:
        return None
    parent_num = (num // 10) * 10
    return f"{m.group(1)}-{parent_num:03d}"


def parse_policy(path: Path) -> list[ParsedSection]:
    name = path.name.lower()
    if "colorado" in name:
        return _parse_colorado(path)
    if "8 principles" in name or "8_principles" in name:
        return _parse_principles(path)
    if "check-in" in name or "check_in" in name:
        return _parse_checkin(path)
    if "grievance" in name:
        return _parse_grievance(path)
    if "internal-programming" in name or "internal_programming" in name:
        return _parse_programming(path)
    return _parse_generic(path)


def _parse_colorado(path: Path) -> list[ParsedSection]:
    pages = _read_pages_plumber(path)
    sections: list[ParsedSection] = []
    code_to_idx: dict[str, int] = {}
    for pnum, text in pages:
        if 3 <= pnum <= 5:
            continue
        text = _strip_colorado_footer(text)
        lines = text.splitlines()
        current = None
        buf: list[str] = []
        for line in lines:
            m = COLORADO_RE.match(line.strip())
            if m:
                if current:
                    current.body = "\n".join(buf).strip()
                    sections.append(current)
                    cm = re.match(r"([A-Z]{2}-\d{3})", current.heading)
                    if cm:
                        code_to_idx[cm.group(1)] = len(sections) - 1
                code, title = m.group(1), m.group(2).strip()
                title = re.sub(r"\s+\d+\s*$", "", title).strip()
                heading = f"{code}: {title}"
                parent_code = _colorado_parent(code)
                parent_idx = code_to_idx.get(parent_code) if parent_code else None
                level = 1 if parent_idx is None else 2
                current = ParsedSection(
                    heading=heading,
                    level=level,
                    position=len(sections),
                    page_number=pnum,
                    parent_idx=parent_idx,
                    body="",
                    heading_path=[],
                )
                buf = []
            else:
                if current is not None:
                    buf.append(line)
        if current:
            current.body = "\n".join(buf).strip()
            sections.append(current)
            cm = re.match(r"([A-Z]{2}-\d{3})", current.heading)
            if cm:
                code_to_idx[cm.group(1)] = len(sections) - 1
    for s in sections:
        path_list = []
        cur = s
        while cur is not None:
            path_list.append(cur.heading)
            cur = sections[cur.parent_idx] if cur.parent_idx is not None else None
        s.heading_path = list(reversed(path_list))
    return sections


def _parse_principles(path: Path) -> list[ParsedSection]:
    pages = _read_pages_pypdf(path)
    full = "\n".join(t for _, t in pages)
    sections: list[ParsedSection] = []
    title = "8 Principles of Effective Intervention"
    top_idx: dict[str, int] = {}
    in_sub_block = False
    for line in full.splitlines():
        if PRINCIPLES_SUB.match(line):
            in_sub_block = True
        m_sub = PRINCIPLES_SUB.match(line)
        m_top = PRINCIPLES_TOP.match(line)
        if m_sub and in_sub_block:
            num, heading = m_sub.group(1), m_sub.group(2).strip()
            body = (m_sub.group(3) or "").strip()
            parent = top_idx.get("3")
            sections.append(
                ParsedSection(
                    heading=f"{num}. {heading}",
                    level=2,
                    position=len(sections),
                    page_number=1,
                    parent_idx=parent,
                    body=body,
                    heading_path=[],
                )
            )
        elif m_top:
            _heading_tmp = m_top.group(2).strip()
            if in_sub_block and _heading_tmp in (
                "Risk Principle",
                "Need Principle",
                "Responsivity Principle",
                "Dosage",
                "Treatment Principle",
            ):
                num, heading = m_top.group(1), _heading_tmp
                body = (m_top.group(3) or "").strip()
                parent = top_idx.get("3")
                sections.append(
                    ParsedSection(
                        heading=f"{num}. {heading}",
                        level=2,
                        position=len(sections),
                        page_number=1,
                        parent_idx=parent,
                        body=body,
                        heading_path=[],
                    )
                )
            else:
                num, heading = m_top.group(1), m_top.group(2).strip()
                body = (m_top.group(3) or "").strip()
                heading_full = f"{num}. {heading}"
                sections.append(
                    ParsedSection(
                        heading=heading_full,
                        level=1,
                        position=len(sections),
                        page_number=1,
                        parent_idx=None,
                        body=body,
                        heading_path=[],
                    )
                )
                top_idx[num] = len(sections) - 1
                if num == "3" and heading == "Target Interventions":
                    in_sub_block = True
                elif num in ("4", "5", "6", "7", "8"):
                    in_sub_block = False
    sub_names = {
        "Risk Principle",
        "Need Principle",
        "Responsivity Principle",
        "Dosage",
        "Treatment Principle",
    }
    for s in sections:
        if any(n in s.heading for n in sub_names):
            s.level = 2
            if s.parent_idx is None:
                s.parent_idx = top_idx.get("3")
        elif s.level == 2 and not any(n in s.heading for n in sub_names):
            s.level = 1
            s.parent_idx = None
        if s.level == 2 and s.parent_idx is not None:
            s.heading_path = [title, sections[s.parent_idx].heading, s.heading]
        else:
            s.heading_path = [title, s.heading]
    if not sections:
        sections.append(
            ParsedSection(
                heading=title,
                level=0,
                position=0,
                page_number=1,
                parent_idx=None,
                body=full.strip(),
                heading_path=[title],
            )
        )
    return sections


def _parse_checkin(path: Path) -> list[ParsedSection]:
    pages = _read_pages_pypdf(path)
    full = "\n".join(t for _, t in pages)
    sections: list[ParsedSection] = []
    lines = full.splitlines()
    intro_buf: list[str] = []
    current = None
    pos = 0
    for line in lines:
        m = CHECKIN_RE.match(line)
        if m:
            if pos == 0 and intro_buf:
                intro = "\n".join(intro_buf).strip()
                if intro:
                    sections.append(
                        ParsedSection(
                            heading="Introduction",
                            level=0,
                            position=0,
                            page_number=1,
                            parent_idx=None,
                            body=intro,
                            heading_path=["Check-In Guidelines", "Introduction"],
                        )
                    )
                    pos = 1
            if current:
                sections.append(current)
            num, body = m.group(1), m.group(2).strip()
            current = ParsedSection(
                heading=f"{num}. {body[:80]}",
                level=1,
                position=len(sections),
                page_number=1,
                parent_idx=None,
                body=body,
                heading_path=[],
            )
            intro_buf = []
        else:
            if current is None:
                intro_buf.append(line)
            else:
                current.body += "\n" + line
    if current:
        sections.append(current)
    for s in sections:
        s.heading_path = ["Check-In Guidelines", s.heading]
    return sections


def _parse_grievance(path: Path) -> list[ParsedSection]:
    pages = _read_pages_pypdf(path)
    full = "\n".join(t for _, t in pages)
    version = None
    vm = re.search(r"Policy Number\s+(\d+)", full)
    if vm:
        version = vm.group(1)
    sections: list[ParsedSection] = []
    current = ParsedSection(
        heading="Grievance and Appeal",
        level=0,
        position=0,
        page_number=1,
        parent_idx=None,
        body="",
        heading_path=["Grievance and Appeal"],
    )
    buf: list[str] = []
    for line in full.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_list = (
            re.match(r"^\d+\.\s+", stripped) or stripped.startswith("•") or stripped.startswith("-")
        )
        is_heading = (
            not is_list
            and stripped.istitle()
            and len(stripped.split()) <= 6
            and not stripped.endswith(".")
        )
        if is_heading and buf:
            current.body = "\n".join(buf).strip()
            if version:
                current.heading_path = ["Grievance and Appeal", current.heading]
            sections.append(current)
            current = ParsedSection(
                heading=stripped,
                level=1,
                position=len(sections),
                page_number=1,
                parent_idx=0,
                body="",
                heading_path=[],
            )
            buf = []
        else:
            buf.append(line)
    current.body = "\n".join(buf).strip()
    sections.append(current)
    for s in sections:
        if not s.heading_path:
            s.heading_path = ["Grievance and Appeal", s.heading]
    return sections


def _parse_programming(path: Path) -> list[ParsedSection]:
    pages = _read_pages_pypdf(path)
    full = "\n".join(t for _, t in pages)
    sections: list[ParsedSection] = []
    current = None
    buf: list[str] = []
    for line in full.splitlines():
        m = PROGRAM_RE.match(line.strip())
        if m:
            if current:
                current.body = "\n".join(buf).strip()
                sections.append(current)
            code, title = m.group(1), m.group(2).strip()
            current = ParsedSection(
                heading=f"{code}: {title}",
                level=1,
                position=len(sections),
                page_number=1,
                parent_idx=None,
                body="",
                heading_path=[],
            )
            buf = []
        else:
            if current is not None:
                buf.append(line)
    if current:
        current.body = "\n".join(buf).strip()
        sections.append(current)
    for s in sections:
        s.heading_path = ["Internal Programming", s.heading]
    return sections


def _parse_generic(path: Path) -> list[ParsedSection]:
    pages = _read_pages_pypdf(path)
    full = "\n".join(t for _, t in pages)
    return [
        ParsedSection(
            heading=path.stem,
            level=0,
            position=0,
            page_number=1,
            parent_idx=None,
            body=full.strip(),
            heading_path=[path.stem],
        )
    ]
