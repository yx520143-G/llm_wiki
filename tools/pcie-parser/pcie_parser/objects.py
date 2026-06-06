from __future__ import annotations

import re
from typing import Any

from pcie_parser.models import SourceObject, TableCell


OBJECT_HEADING_RE = re.compile(r"^(Figure|Fig\.|Table|Equation)\s+([0-9]+[-.][0-9A-Za-z.]+)\s+(.+)$", re.IGNORECASE)


def parse_object_heading(text: str) -> tuple[str, str, str] | None:
    normalized = " ".join(text.strip().split())
    match = OBJECT_HEADING_RE.match(normalized)
    if not match:
        return None
    kind, number, title = match.groups()
    lowered = kind.lower()
    object_type = "figure" if lowered in {"figure", "fig."} else lowered
    return object_type, number, title.strip()


def fallback_pages(listed_page: int, section_start: int | None, section_end: int | None) -> list[int]:
    pages: list[int] = [listed_page]
    for page in range(listed_page - 2, listed_page + 3):
        if page > 0 and page not in pages:
            pages.append(page)
    if section_start is not None and section_end is not None:
        for page in range(section_start, section_end + 1):
            if page > 0 and page not in pages:
                pages.append(page)
    return pages


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
