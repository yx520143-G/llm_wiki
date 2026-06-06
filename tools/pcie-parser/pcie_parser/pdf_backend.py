from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

from pcie_parser.models import BBox, SectionNode, TextSpan


OutlineEntry = tuple[int, str, int]

_SECTION_PREFIX_RE = re.compile(r"^\s*(?:Chapter\s+)?(?P<number>\d+(?:\.\d+)*)(?:[\s.:;-]+|$)", re.IGNORECASE)


def extract_section_number(title: str) -> str | None:
    match = _SECTION_PREFIX_RE.match(title)
    if match is None:
        return None
    return match.group("number")


def strip_section_number(title: str) -> str:
    match = _SECTION_PREFIX_RE.match(title)
    if match is None:
        return title.strip()
    return title[match.end() :].strip()


def outline_entries_to_sections(spec_version: str, entries: Iterable[OutlineEntry], page_count: int) -> list[SectionNode]:
    numbered_entries: list[tuple[int, str, int, str, str]] = []
    for level, title, page in entries:
        section_number = extract_section_number(title)
        if section_number is None:
            continue
        numbered_entries.append((int(level), str(title), int(page), section_number, strip_section_number(title)))

    sections: list[SectionNode] = []
    level_stack: dict[int, SectionNode] = {}

    for index, (level, _title, page_start, section_number, stripped_title) in enumerate(numbered_entries):
        if index + 1 < len(numbered_entries):
            page_end = max(page_start, numbered_entries[index + 1][2] - 1)
        else:
            page_end = page_count

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


def span_dict_to_text_span(text: str, page: int, bbox: Sequence[float], block: int, line: int, span: int) -> TextSpan:
    return TextSpan(
        text=text,
        page=page,
        bbox=BBox(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
        block=block,
        line=line,
        span=span,
    )


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
                page_dict = page.get_text("dict")
                for block_index, block in enumerate(page_dict.get("blocks", [])):
                    for line_index, line in enumerate(block.get("lines", [])):
                        for span_index, span in enumerate(line.get("spans", [])):
                            text = str(span.get("text", "")).strip()
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
