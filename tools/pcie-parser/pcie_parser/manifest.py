from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcie_parser.models import ParseWarning, SectionNode, SourceObject


class Manifest:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def add(self, record: dict[str, Any]) -> None:
        self.records.append(record)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for record in self.records:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                f.write("\n")


def section_record(section: SectionNode, path: str) -> dict[str, Any]:
    return {
        "record_type": "section",
        "id": section.section_id,
        "path": path,
        "title": section.title,
        "page_start": section.page_start,
        "page_end": section.page_end,
        "object_refs": [ref.object_id for ref in section.object_refs],
        "content_hash": section.content_hash,
    }


def object_record(obj: SourceObject, path: str) -> dict[str, Any]:
    return {
        "record_type": "object",
        "id": obj.object_id,
        "object_type": obj.object_type,
        "object_number": obj.object_number,
        "title": obj.title,
        "path": path,
        "assets": obj.asset_paths,
        "page": obj.page,
        "bbox": obj.bbox.as_list() if obj.bbox else None,
        "section_id": obj.section_id,
        "content_hash": obj.content_hash,
        "status": obj.status,
    }


def warning_record(warning: ParseWarning) -> dict[str, Any]:
    return {
        "record_type": "parse_warning",
        "severity": warning.severity,
        "code": warning.code,
        "message": warning.message,
        "page": warning.page,
        "section_id": warning.section_id,
        "object_id": warning.object_id,
    }
