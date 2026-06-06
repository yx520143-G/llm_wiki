from __future__ import annotations

import html
import math
import re
from numbers import Real
from pathlib import Path
from typing import Iterable, Sequence

from pcie_parser.models import BBox, SectionNode, TextSpan


OutlineEntry = tuple[int, str, int]

_NUMERIC_SECTION_RE = r"\d+(?:\.\d+)*"
_APPENDIX_SECTION_RE = r"(?:[A-Za-z]|\d+)(?:\.\d+)*"
_SECTION_SEPARATOR_RE = r"(?:[\s.:;-]+|$)"
_SECTION_PREFIX_RES = (
    (
        "section",
        re.compile(rf"^\s*Section\s+(?P<number>{_NUMERIC_SECTION_RE}){_SECTION_SEPARATOR_RE}", re.IGNORECASE),
    ),
    (
        "chapter",
        re.compile(rf"^\s*Chapter\s+(?P<number>{_NUMERIC_SECTION_RE}){_SECTION_SEPARATOR_RE}", re.IGNORECASE),
    ),
    (
        "appendix",
        re.compile(rf"^\s*Appendix\s+(?P<number>{_APPENDIX_SECTION_RE}){_SECTION_SEPARATOR_RE}", re.IGNORECASE),
    ),
    (
        "bare",
        re.compile(rf"^\s*(?P<number>{_NUMERIC_SECTION_RE}){_SECTION_SEPARATOR_RE}", re.IGNORECASE),
    ),
)


def _parse_section_prefix(title: str) -> tuple[str, str] | None:
    for prefix_kind, pattern in _SECTION_PREFIX_RES:
        match = pattern.match(title)
        if match is None:
            continue
        section_number = match.group("number")
        if prefix_kind == "appendix" and section_number[:1].isalpha():
            section_number = f"{section_number[0].upper()}{section_number[1:]}"
        return section_number, title[match.end() :].strip()
    return None


def extract_section_number(title: str) -> str | None:
    parsed = _parse_section_prefix(title)
    if parsed is None:
        return None
    return parsed[0]


def strip_section_number(title: str) -> str:
    parsed = _parse_section_prefix(title)
    if parsed is None:
        return title.strip()
    return parsed[1]


def outline_entries_to_sections(spec_version: str, entries: Iterable[OutlineEntry], page_count: int) -> list[SectionNode]:
    numbered_entries: list[tuple[int, str, int, str, str]] = []
    for level, title, page in entries:
        raw_title = str(title)
        parsed = _parse_section_prefix(raw_title)
        if parsed is None:
            continue
        section_number, stripped_title = parsed
        numbered_entries.append((int(level), raw_title, int(page), section_number, stripped_title))

    sections: list[SectionNode] = []
    level_stack: dict[int, SectionNode] = {}

    for index, (level, _title, page_start, section_number, stripped_title) in enumerate(numbered_entries):
        page_end = page_count
        for next_level, _next_title, next_page_start, _next_section_number, _next_stripped_title in numbered_entries[
            index + 1 :
        ]:
            if next_level <= level:
                page_end = max(page_start, next_page_start - 1)
                break

        stale_levels = [stack_level for stack_level in level_stack if stack_level >= level]
        for stack_level in stale_levels:
            del level_stack[stack_level]

        parent = None
        for parent_level in range(level - 1, 0, -1):
            if parent_level in level_stack:
                parent = level_stack[parent_level]
                break

        toc_path = [stripped_title] if parent is None else [*parent.toc_path, stripped_title]
        section = SectionNode(
            spec_version=spec_version,
            section_number=section_number,
            title=stripped_title,
            level=level,
            page_start=page_start,
            page_end=page_end,
            toc_path=toc_path,
            parent_id=parent.section_id if parent is not None else None,
        )
        if parent is not None:
            parent.child_ids.append(section.section_id)

        sections.append(section)
        level_stack[level] = section

    return sections


def _validate_bbox(bbox: Sequence[float]) -> tuple[float, float, float, float]:
    try:
        values = list(bbox)
    except TypeError as exc:
        raise ValueError("bbox must be a sequence of exactly 4 finite numeric values") from exc

    if len(values) != 4:
        raise ValueError(f"bbox must contain exactly 4 values; got {len(values)}")

    coords: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"bbox[{index}] must be numeric; got {type(value).__name__}")
        coord = float(value)
        if not math.isfinite(coord):
            raise ValueError(f"bbox[{index}] must be finite; got {value!r}")
        coords.append(coord)

    x0, y0, x1, y1 = coords
    if x1 < x0 or y1 < y0:
        raise ValueError(f"bbox coordinates must not be reversed; got {coords!r}")

    return x0, y0, x1, y1


def span_dict_to_text_span(text: str, page: int, bbox: Sequence[float], block: int, line: int, span: int) -> TextSpan:
    x0, y0, x1, y1 = _validate_bbox(bbox)
    return TextSpan(
        text=text,
        page=page,
        bbox=BBox(x0, y0, x1, y1),
        block=block,
        line=line,
        span=span,
    )


def crop_bbox_to_png(pdf_path: Path, page_number: int, bbox: BBox, output_path: Path, zoom: float = 2.0) -> None:
    import fitz

    doc = fitz.open(pdf_path)
    try:
        if page_number < 1 or page_number > doc.page_count:
            raise ValueError(f"page_number {page_number} is outside PDF page range 1..{doc.page_count}")

        page = doc.load_page(page_number - 1)
        page_rect = page.rect
        x0 = max(float(bbox.x0), float(page_rect.x0))
        y0 = max(float(bbox.y0), float(page_rect.y0))
        x1 = min(float(bbox.x1), float(page_rect.x1))
        y1 = min(float(bbox.y1), float(page_rect.y1))
        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"empty crop for page {page_number}: {bbox.as_list()}")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=fitz.Rect(x0, y0, x1, y1), alpha=False)
        pixmap.save(output_path)
    finally:
        doc.close()


def write_table_html(path: Path, caption: str, rows: list[list[str]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        f"  <title>{html.escape(caption, quote=True)}</title>",
        "</head>",
        "<body>",
        "<table>",
        f"  <caption>{html.escape(caption, quote=True)}</caption>",
    ]
    for row in rows:
        lines.append("  <tr>")
        for cell in row:
            lines.append(f"    <td>{html.escape(str(cell), quote=True)}</td>")
        lines.append("  </tr>")
    lines.extend(["</table>", "</body>", "</html>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


class PdfBackend:
    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)

    def open_document(self):
        import fitz

        return fitz.open(self.pdf_path)

    def extract_outline(self) -> tuple[list[OutlineEntry], int]:
        doc = self.open_document()
        try:
            entries = [(int(level), str(title), int(page)) for level, title, page in doc.get_toc(simple=True)]
            return entries, int(doc.page_count)
        finally:
            doc.close()

    def extract_text_spans(self) -> list[TextSpan]:
        doc = self.open_document()
        try:
            spans: list[TextSpan] = []
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                try:
                    # sort=True keeps downstream body/hash output deterministic when PyMuPDF supports it.
                    page_dict = page.get_text("dict", sort=True)
                except TypeError:
                    page_dict = page.get_text("dict")
                for block_index, block in enumerate(page_dict.get("blocks", [])):
                    for line_index, line in enumerate(block.get("lines", [])):
                        for span_index, span in enumerate(line.get("spans", [])):
                            raw_text = span.get("text", "")
                            if raw_text is None:
                                continue
                            text = str(raw_text).strip()
                            if not text:
                                continue
                            spans.append(
                                span_dict_to_text_span(
                                    text=text,
                                    page=page_index + 1,
                                    bbox=span["bbox"],
                                    block=block_index,
                                    line=line_index,
                                    span=span_index,
                                )
                            )
            return spans
        finally:
            doc.close()
