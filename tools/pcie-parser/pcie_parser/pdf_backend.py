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


def infer_graphic_bbox_near_caption(
    pdf_path: Path,
    page_number: int,
    caption_bbox: BBox,
    object_type: str,
) -> BBox | None:
    with PdfAssetExtractor(pdf_path) as extractor:
        return extractor.infer_graphic_bbox_near_caption(page_number, caption_bbox, object_type)


def extract_table_rows_near_caption(
    pdf_path: Path,
    page_number: int,
    caption_bbox: BBox,
) -> tuple[BBox, list[list[str]]] | None:
    with PdfAssetExtractor(pdf_path) as extractor:
        return extractor.extract_table_rows_near_caption(page_number, caption_bbox)


def table_rows_have_real_content(rows: Sequence[Sequence[object]], caption: str) -> bool:
    normalized_caption = _normalize_cell_text(caption).lower()
    non_empty = [_normalize_cell_text(cell) for row in rows for cell in row if _normalize_cell_text(cell)]
    if not non_empty:
        return False
    if len(non_empty) == 1 and non_empty[0].lower() == normalized_caption:
        return False
    if normalized_caption and all(cell.lower() == normalized_caption for cell in non_empty):
        return False
    return len(non_empty) >= 2 or len(rows) >= 2


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


def _infer_figure_bbox_from_entries(
    page_rect: object,
    drawing_bboxes: Sequence[BBox],
    text_entries: Sequence[tuple[str, BBox]],
    caption_bbox: BBox,
) -> BBox | None:
    candidates = [bbox for bbox in drawing_bboxes if _is_usable_drawing_rect(bbox, page_rect)]
    above_caption = [
        bbox
        for bbox in candidates
        if bbox.y1 <= caption_bbox.y0 + 12.0 and caption_bbox.y0 - bbox.y1 <= 520.0
    ]
    if not above_caption:
        return None

    seed = min(
        above_caption,
        key=lambda bbox: (caption_bbox.y0 - bbox.y1, abs(_center_x(bbox) - _center_x(caption_bbox))),
    )
    selected = [seed]
    changed = True
    while changed:
        changed = False
        current = _union_bboxes(selected)
        for bbox in above_caption:
            if bbox in selected:
                continue
            if _rects_related(current, bbox, max_gap=90.0):
                selected.append(bbox)
                changed = True

    content_bbox = _union_bboxes(selected)
    text_bboxes = [
        text_bbox
        for text, text_bbox in text_entries
        if text
        and text_bbox.y1 <= caption_bbox.y0 + 12.0
        and text_bbox.y0 >= content_bbox.y0 - 24.0
        and text_bbox.y1 <= content_bbox.y1 + 36.0
        and _horizontal_overlap_or_near(content_bbox, text_bbox, max_gap=36.0)
    ]
    if text_bboxes:
        content_bbox = _union_bboxes([content_bbox, *text_bboxes])

    return _expand_and_clip_bbox(_union_bboxes([content_bbox, caption_bbox]), page_rect, padding=4.0)


def _infer_equation_bbox_from_entries(
    page_rect: object,
    drawing_bboxes: Sequence[BBox],
    line_entries: Sequence[tuple[str, BBox]],
    caption_bbox: BBox,
) -> BBox | None:
    candidate_lines = [
        (line_text, line_bbox)
        for line_text, line_bbox in line_entries
        if line_bbox.y1 <= caption_bbox.y0 + 4.0 and 0.0 <= caption_bbox.y0 - line_bbox.y1 <= 120.0
    ]
    equation_lines = [
        (line_text, line_bbox)
        for line_text, line_bbox in candidate_lines
        if _looks_like_equation_text(line_text)
    ]
    if not equation_lines:
        return None

    _seed_text, seed_bbox = min(equation_lines, key=lambda item: caption_bbox.y0 - item[1].y1)
    selected = [seed_bbox]
    changed = True
    while changed:
        changed = False
        current = _union_bboxes(selected)
        for line_text, line_bbox in equation_lines:
            if line_bbox in selected:
                continue
            if _vertical_distance(current, line_bbox) <= 24.0:
                selected.append(line_bbox)
                changed = True

    usable_drawing_bboxes = [bbox for bbox in drawing_bboxes if _is_usable_drawing_rect(bbox, page_rect)]
    current = _union_bboxes(selected)
    selected.extend(
        bbox
        for bbox in usable_drawing_bboxes
        if _vertical_distance(current, bbox) <= 24.0 and _horizontal_overlap_or_near(current, bbox, max_gap=48.0)
    )
    return _expand_and_clip_bbox(_union_bboxes([*selected, caption_bbox]), page_rect, padding=4.0)


def _nearest_table_from_entries(
    table_entries: Sequence[tuple[BBox, list[list[str]]]],
    caption_bbox: BBox,
) -> tuple[BBox, list[list[str]]] | None:
    candidates: list[tuple[float, BBox, list[list[str]]]] = []
    for table_bbox, rows in table_entries:
        if not table_rows_have_real_content(rows, caption=""):
            continue

        distance = _vertical_distance(caption_bbox, table_bbox)
        if distance > 180.0:
            continue
        candidates.append((distance, table_bbox, rows))

    if not candidates:
        return None

    _distance, table_bbox, rows = min(candidates, key=lambda item: (item[0], item[1].y0, item[1].x0))
    return table_bbox, rows


def _table_entries_for_page(page) -> list[tuple[BBox, list[list[str]]]]:
    find_tables = getattr(page, "find_tables", None)
    if find_tables is None:
        return []

    try:
        table_finder = find_tables()
    except Exception:
        return []

    entries: list[tuple[BBox, list[list[str]]]] = []
    for table in getattr(table_finder, "tables", []):
        table_bbox = _bbox_from_rect(table.bbox)
        rows = _normalize_table_rows(table.extract())
        if table_rows_have_real_content(rows, caption=""):
            entries.append((table_bbox, rows))
    return entries


def _drawing_bboxes_for_page(page) -> list[BBox]:
    return [_bbox_from_rect(drawing["rect"]) for drawing in page.get_drawings() if "rect" in drawing]


def _page_text_entries(page) -> list[tuple[str, BBox]]:
    entries: list[tuple[str, BBox]] = []
    try:
        page_dict = page.get_text("dict", sort=True)
    except TypeError:
        page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text") or "").strip()
                if text:
                    entries.append((text, _bbox_from_rect(span["bbox"])))
    return entries


def _page_text_line_entries(page) -> list[tuple[str, BBox]]:
    entries: list[tuple[str, BBox]] = []
    try:
        page_dict = page.get_text("dict", sort=True)
    except TypeError:
        page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            line_spans: list[tuple[str, BBox]] = []
            for span in line.get("spans", []):
                text = str(span.get("text") or "").strip()
                if text:
                    line_spans.append((text, _bbox_from_rect(span["bbox"])))
            if line_spans:
                entries.append(
                    (
                        " ".join(text for text, _bbox in line_spans),
                        _union_bboxes([bbox for _text, bbox in line_spans]),
                    )
                )
    return entries


def _normalize_table_rows(rows: object) -> list[list[str]]:
    if rows is None:
        return []
    normalized_rows: list[list[str]] = []
    for row in rows:
        normalized_rows.append([_normalize_cell_text(cell) for cell in row])
    return normalized_rows


def _normalize_cell_text(cell: object) -> str:
    if cell is None:
        return ""
    return " ".join(str(cell).strip().split())


def _looks_like_equation_text(text: str) -> bool:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    if "=" in normalized:
        return True
    if re.search(r"[+\-*/÷×≤≥<>∑√]|_[A-Za-z0-9]", normalized) is not None:
        return True
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_ ()]+", normalized) and "_" in normalized)


def _bbox_from_rect(rect: object) -> BBox:
    x0, y0, x1, y1 = [float(value) for value in rect]
    return BBox(x0, y0, x1, y1)


def _union_bboxes(bboxes: Sequence[BBox]) -> BBox:
    if not bboxes:
        raise ValueError("cannot union an empty bbox sequence")
    return BBox(
        min(bbox.x0 for bbox in bboxes),
        min(bbox.y0 for bbox in bboxes),
        max(bbox.x1 for bbox in bboxes),
        max(bbox.y1 for bbox in bboxes),
    )


def _expand_and_clip_bbox(bbox: BBox, page_rect: object, padding: float) -> BBox:
    return BBox(
        max(float(page_rect.x0), bbox.x0 - padding),
        max(float(page_rect.y0), bbox.y0 - padding),
        min(float(page_rect.x1), bbox.x1 + padding),
        min(float(page_rect.y1), bbox.y1 + padding),
    )


def _is_usable_drawing_rect(bbox: BBox, page_rect: object) -> bool:
    width = bbox.x1 - bbox.x0
    height = bbox.y1 - bbox.y0
    page_width = float(page_rect.width)
    page_height = float(page_rect.height)
    if width <= 1.0 or height <= 1.0:
        return False
    if width >= page_width * 0.95 and height >= page_height * 0.90:
        return False
    if bbox.y0 < float(page_rect.y0) + 24.0 or bbox.y1 > float(page_rect.y1) - 24.0:
        return False
    return True


def _center_x(bbox: BBox) -> float:
    return (bbox.x0 + bbox.x1) / 2.0


def _vertical_distance(a: BBox, b: BBox) -> float:
    if a.y1 < b.y0:
        return b.y0 - a.y1
    if b.y1 < a.y0:
        return a.y0 - b.y1
    return 0.0


def _horizontal_overlap_or_near(a: BBox, b: BBox, max_gap: float) -> bool:
    if min(a.x1, b.x1) >= max(a.x0, b.x0):
        return True
    return min(abs(a.x1 - b.x0), abs(b.x1 - a.x0)) <= max_gap


def _rects_related(a: BBox, b: BBox, max_gap: float) -> bool:
    return _vertical_distance(a, b) <= max_gap and _horizontal_overlap_or_near(a, b, max_gap=max_gap)


class PdfAssetExtractor:
    def __init__(self, pdf_path: Path):
        import fitz

        self.doc = fitz.open(pdf_path)
        self._pages: dict[int, object] = {}
        self._drawing_bboxes: dict[int, list[BBox]] = {}
        self._text_entries: dict[int, list[tuple[str, BBox]]] = {}
        self._text_line_entries: dict[int, list[tuple[str, BBox]]] = {}
        self._table_entries: dict[int, list[tuple[BBox, list[list[str]]]]] = {}

    def __enter__(self) -> "PdfAssetExtractor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        self.doc.close()

    def infer_graphic_bbox_near_caption(
        self,
        page_number: int,
        caption_bbox: BBox,
        object_type: str,
    ) -> BBox | None:
        page = self._page(page_number)
        if object_type == "equation":
            return _infer_equation_bbox_from_entries(
                page.rect,
                self._drawing_bboxes_for_page(page_number),
                self._text_line_entries_for_page(page_number),
                caption_bbox,
            )
        if object_type == "figure":
            return _infer_figure_bbox_from_entries(
                page.rect,
                self._drawing_bboxes_for_page(page_number),
                self._text_entries_for_page(page_number),
                caption_bbox,
            )
        return None

    def extract_table_rows_near_caption(
        self,
        page_number: int,
        caption_bbox: BBox,
    ) -> tuple[BBox, list[list[str]]] | None:
        self._page(page_number)
        return _nearest_table_from_entries(self._table_entries_for_page(page_number), caption_bbox)

    def _page(self, page_number: int):
        if page_number < 1 or page_number > self.doc.page_count:
            raise ValueError(f"page_number {page_number} is outside PDF page range 1..{self.doc.page_count}")
        if page_number not in self._pages:
            self._pages[page_number] = self.doc.load_page(page_number - 1)
        return self._pages[page_number]

    def _drawing_bboxes_for_page(self, page_number: int) -> list[BBox]:
        if page_number not in self._drawing_bboxes:
            self._drawing_bboxes[page_number] = _drawing_bboxes_for_page(self._page(page_number))
        return self._drawing_bboxes[page_number]

    def _text_entries_for_page(self, page_number: int) -> list[tuple[str, BBox]]:
        if page_number not in self._text_entries:
            self._text_entries[page_number] = _page_text_entries(self._page(page_number))
        return self._text_entries[page_number]

    def _text_line_entries_for_page(self, page_number: int) -> list[tuple[str, BBox]]:
        if page_number not in self._text_line_entries:
            self._text_line_entries[page_number] = _page_text_line_entries(self._page(page_number))
        return self._text_line_entries[page_number]

    def _table_entries_for_page(self, page_number: int) -> list[tuple[BBox, list[list[str]]]]:
        if page_number not in self._table_entries:
            self._table_entries[page_number] = _table_entries_for_page(self._page(page_number))
        return self._table_entries[page_number]


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
