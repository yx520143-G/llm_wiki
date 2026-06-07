from __future__ import annotations

import re
from typing import Any

from pcie_parser.bbox import expand_bbox
from pcie_parser.models import ParseWarning, SourceObject, TableCell, TextSpan
from pcie_parser.slug import content_hash, object_slug


OBJECT_NUMBER_RE = r"(?:[A-Za-z]|[0-9]+)(?:[-.][0-9]+[A-Za-z]?)*"
OBJECT_HEADING_RE = re.compile(
    r"^(Figure|Fig\.|Table|Equation)\s+"
    rf"\(?({OBJECT_NUMBER_RE})\)?"
    r"(?:\s*[:.]|\s+)"
    r"(.+)$",
    re.IGNORECASE,
)
OBJECT_LABEL_RE = re.compile(
    r"^(Figure|Fig\.|Table|Equation)\s+"
    rf"\(?({OBJECT_NUMBER_RE})\)?\.?$",
    re.IGNORECASE,
)
DOTTED_LEADER_PAGE_RE = re.compile(r"\s*(?:\. ?){3,}\s*[0-9]+\s*$")
LISTED_PAGE_RE = re.compile(r"(?:\. ?){3,}\s*(?P<page>[0-9]+)\s*$")
LISTED_IN_OBJECT_TYPES = {
    "List of Figures": "figure",
    "List of Tables": "table",
    "List of Equations": "equation",
}


def parse_object_heading(text: str) -> tuple[str, str, str] | None:
    normalized = " ".join(text.strip().split())
    match = OBJECT_HEADING_RE.match(normalized)
    if not match:
        return None
    kind, number, title = match.groups()
    lowered = kind.lower()
    object_type = "figure" if lowered in {"figure", "fig."} else lowered
    cleaned_title = DOTTED_LEADER_PAGE_RE.sub("", title).strip()
    return object_type, number, cleaned_title


def extract_object_seeds_from_list_spans(
    spec_version: str,
    spans: list[TextSpan],
    listed_in: str,
) -> list[SourceObject]:
    try:
        expected_type = LISTED_IN_OBJECT_TYPES[listed_in]
    except KeyError as exc:
        raise ValueError(f"Unsupported object list: {listed_in}") from exc

    objects: list[SourceObject] = []
    seen_ids: set[str] = set()
    line_entries = _line_entries_from_spans(spans)
    index = 0
    while index < len(line_entries):
        text, anchor_span = line_entries[index]
        parsed = parse_object_heading(text)
        if parsed is not None:
            object_type, object_number, title = parsed
            index += 1
        else:
            label = parse_object_label(text)
            if label is None:
                index += 1
                continue

            object_type, object_number = label
            title_lines: list[str] = []
            next_index = index + 1
            while next_index < len(line_entries):
                next_text, _next_span = line_entries[next_index]
                if parse_object_label(next_text) is not None or parse_object_heading(next_text) is not None:
                    break
                if not _is_list_noise_line(next_text, listed_in):
                    title_lines.append(next_text)
                    if LISTED_PAGE_RE.search(" ".join(next_text.strip().split())) is not None:
                        next_index += 1
                        break
                next_index += 1
            if not title_lines:
                index = next_index
                continue

            title_text = " ".join(title_lines)
            title = DOTTED_LEADER_PAGE_RE.sub("", title_text).strip()
            text = f"{text} {title_text}"
            index = next_index

        if object_type != expected_type:
            continue

        obj = SourceObject(
            spec_version=spec_version,
            object_type=object_type,
            object_number=object_number,
            title=title,
            listed_page=_listed_page_from_text(text, fallback_page=anchor_span.page),
            page=None,
            bbox=None,
            section_id=None,
            listed_in=listed_in,
            slug=object_slug(object_type, object_number, title),
            status="unresolved_bbox",
        )
        if obj.object_id in seen_ids:
            continue
        seen_ids.add(obj.object_id)
        objects.append(obj)
    return objects


def parse_object_label(text: str) -> tuple[str, str] | None:
    normalized = " ".join(text.strip().split())
    match = OBJECT_LABEL_RE.match(normalized)
    if not match:
        return None
    kind, number = match.groups()
    lowered = kind.lower()
    object_type = "figure" if lowered in {"figure", "fig."} else lowered
    return object_type, number


def localize_object_from_spans(
    obj: SourceObject,
    spans: list[TextSpan],
    section_start: int | None,
    section_end: int | None,
) -> tuple[SourceObject, list[ParseWarning]]:
    pages = set(fallback_pages(obj.listed_page, section_start, section_end))
    for span in sorted(spans, key=_span_order_key):
        if span.page not in pages:
            continue
        if not _span_matches_object_caption(obj, span):
            continue

        obj.page = span.page
        obj.bbox = expand_bbox(span.bbox, vertical=36.0, horizontal=6.0)
        obj.caption_hash = content_hash(span.text)
        obj.status = "resolved"
        return obj, []

    obj.page = None
    obj.bbox = None
    obj.status = "unresolved_bbox"
    return obj, [
        ParseWarning(
            severity="warning",
            code="object_bbox_unresolved",
            message=f"Could not resolve bounding box for {obj.object_id}",
            page=obj.listed_page,
            section_id=obj.section_id,
            object_id=obj.object_id,
        )
    ]


def object_prefixes(obj: SourceObject) -> list[str]:
    if obj.object_type == "figure":
        return [f"Figure {obj.object_number}", f"Fig. {obj.object_number}"]
    if obj.object_type == "table":
        return [f"Table {obj.object_number}"]
    if obj.object_type == "equation":
        return [
            f"Equation {obj.object_number}",
            f"Equation ({obj.object_number})",
            f"({obj.object_number})",
        ]
    return [f"{obj.object_type.title()} {obj.object_number}"]


def fallback_pages(listed_page: int, section_start: int | None, section_end: int | None) -> list[int]:
    pages: list[int] = []
    seen: set[int] = set()

    def add_page(page: int) -> None:
        if page > 0 and page not in seen:
            pages.append(page)
            seen.add(page)

    add_page(listed_page)
    for page in range(listed_page - 2, listed_page + 3):
        add_page(page)
    if section_start is not None and section_end is not None:
        for page in range(section_start, section_end + 1):
            add_page(page)
    return pages


def _listed_page_from_text(text: str, fallback_page: int) -> int:
    normalized = " ".join(text.strip().split())
    match = LISTED_PAGE_RE.search(normalized)
    if match is None:
        return fallback_page
    return int(match.group("page"))


def _span_matches_object_caption(obj: SourceObject, span: TextSpan) -> bool:
    parsed = parse_object_heading(span.text)
    if parsed is not None:
        object_type, object_number, _title = parsed
        if object_type == obj.object_type and object_number == obj.object_number:
            return True

    normalized = " ".join(span.text.strip().split()).lower()
    for prefix in object_prefixes(obj):
        lowered_prefix = prefix.lower()
        if normalized == lowered_prefix:
            return True
        if any(normalized.startswith(f"{lowered_prefix}{delimiter}") for delimiter in (" ", ":", ".")):
            return True
    return False


def _span_order_key(span: TextSpan) -> tuple[int, int, int, int, float, float, str]:
    return (span.page, span.block, span.line, span.span, span.bbox.y0, span.bbox.x0, span.text)


def _line_entries_from_spans(spans: list[TextSpan]) -> list[tuple[str, TextSpan]]:
    entries: list[tuple[str, TextSpan]] = []
    current_key: tuple[int, int, int] | None = None
    current_spans: list[TextSpan] = []
    for span in sorted(spans, key=_span_order_key):
        key = (span.page, span.block, span.line)
        if current_key is not None and key != current_key:
            entries.append(_line_entry_from_spans(current_spans))
            current_spans = []
        current_key = key
        current_spans.append(span)
    if current_spans:
        entries.append(_line_entry_from_spans(current_spans))
    return entries


def _line_entry_from_spans(spans: list[TextSpan]) -> tuple[str, TextSpan]:
    return " ".join(span.text for span in spans), spans[0]


def _is_list_noise_line(text: str, listed_in: str) -> bool:
    normalized = " ".join(text.strip().split())
    lowered = normalized.lower()
    return (
        lowered == listed_in.lower()
        or lowered.startswith("7.0-1.0-pub")
        or re.fullmatch(r"page\s+[0-9]+", lowered) is not None
    )


def table_json_payload(
    obj: SourceObject,
    headers: list[list[TableCell]],
    rows: list[list[TableCell]],
    notes: list[TableCell],
    source_html: str,
) -> dict[str, Any]:
    all_cells = [cell for row in headers for cell in row] + [cell for row in rows for cell in row] + list(notes)
    all_pages = [cell.page for cell in all_cells]
    return {
        "schema_version": "pcie-table-json-0.1",
        "table_id": obj.object_id,
        "caption": obj.title,
        "page_start": min(all_pages) if all_pages else obj.page,
        "page_end": max(all_pages) if all_pages else obj.page,
        "bbox": obj.bbox.as_list() if obj.bbox else None,
        "headers": [[cell_json(cell) for cell in row] for row in headers],
        "rows": [[cell_json(cell) for cell in row] for row in rows],
        "notes": [cell_json(cell) for cell in notes],
        "source_html": source_html,
    }


def cell_json(cell: TableCell) -> dict[str, Any]:
    return {
        "text": cell.text,
        "rowspan": cell.rowspan,
        "colspan": cell.colspan,
        "page": cell.page,
        "bbox": cell.bbox.as_list(),
        "hash": cell.hash,
    }
