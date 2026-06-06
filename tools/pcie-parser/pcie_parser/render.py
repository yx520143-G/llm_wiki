from __future__ import annotations

import json
import re
from typing import Any

from pcie_parser import PARSER_VERSION
from pcie_parser.models import ObjectRef, ParagraphAnchor, SectionNode, SourceObject


_PLAIN_SCALAR_RE = re.compile(r"^[A-Za-z0-9_./:+-]+$")


def quote_yaml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: list[str], indent: int = 0) -> str:
    prefix = " " * indent
    if not values:
        return f"{prefix}[]"
    return "\n".join(f"{prefix}- {quote_yaml(value)}" for value in values)


def label_for_object_ref(object_id: str) -> str:
    parts = object_id.rsplit(":", 2)
    if len(parts) < 3:
        return object_id
    object_type = parts[1]
    object_number = parts[2]
    label_type = {
        "figure": "Figure",
        "table": "Table",
        "equation": "Equation",
    }.get(object_type, object_type.title())
    return f"{label_type} {object_number}"


def render_section_markdown(section: SectionNode, source_pdf: str) -> str:
    body = section.body_markdown
    for ref in section.object_refs:
        placeholder = f"{{{{object:{ref.object_id}}}}}"
        body = body.replace(placeholder, f"[{label_for_object_ref(ref.object_id)}]({ref.path})")

    frontmatter = _frontmatter(
        [
            ("type", "pcie_section"),
            ("spec_version", section.spec_version),
            ("source_pdf", source_pdf),
            ("section_id", section.section_id),
            ("section_number", section.section_number),
            ("section_title", section.title),
            ("slug", section.slug),
            ("toc_path", section.toc_path),
            ("page_start", section.page_start),
            ("page_end", section.page_end),
            ("outline_level", section.level),
            ("parent_section_id", section.parent_id),
            ("child_section_ids", section.child_ids),
            ("object_refs", [_object_ref_record(ref) for ref in section.object_refs]),
            (
                "paragraph_anchors",
                [_paragraph_anchor_record(anchor) for anchor in section.paragraph_anchors],
            ),
            ("content_hash", section.content_hash),
            ("parser_version", PARSER_VERSION),
        ]
    )
    return f"{frontmatter}\n\n{body.rstrip()}\n"


def render_object_markdown(obj: SourceObject, source_pdf: str) -> str:
    frontmatter = _frontmatter(
        [
            ("type", "pcie_object"),
            ("spec_version", obj.spec_version),
            ("source_pdf", source_pdf),
            ("object_id", obj.object_id),
            ("object_type", obj.object_type),
            ("object_number", obj.object_number),
            ("object_title", obj.title),
            ("slug", obj.slug),
            ("listed_page", obj.listed_page),
            ("page", obj.page),
            ("bbox", obj.bbox.as_list() if obj.bbox else None),
            ("section_id", obj.section_id),
            ("listed_in", obj.listed_in),
            ("asset_paths", dict(obj.asset_paths)),
            ("caption_hash", obj.caption_hash),
            ("content_hash", obj.content_hash),
            ("status", obj.status),
            ("parser_version", PARSER_VERSION),
        ]
    )
    body = _object_body_markdown(obj)
    return f"{frontmatter}\n\n{body.rstrip()}\n" if body else f"{frontmatter}\n"


def _object_body_markdown(obj: SourceObject) -> str:
    lines: list[str] = []
    image_path = obj.asset_paths.get("image")
    if obj.object_type in {"figure", "equation"} and image_path:
        lines.append(f"![{obj.title}]({image_path})")
    if obj.object_type == "table":
        html_path = obj.asset_paths.get("html")
        json_path = obj.asset_paths.get("json")
        if html_path:
            lines.append(f"[HTML]({html_path})")
        if json_path:
            lines.append(f"[JSON]({json_path})")
    return "\n\n".join(lines)


def _object_ref_record(ref: ObjectRef) -> dict[str, str]:
    return {
        "object_id": ref.object_id,
        "path": ref.path,
        "occurrence": ref.occurrence,
    }


def _paragraph_anchor_record(anchor: ParagraphAnchor) -> dict[str, Any]:
    return {
        "id": anchor.id,
        "page": anchor.page,
        "bbox": anchor.bbox.as_list(),
        "hash": anchor.hash,
    }


def _frontmatter(fields: list[tuple[str, Any]]) -> str:
    lines = ["---"]
    for key, value in fields:
        lines.extend(_yaml_field(key, value))
    lines.append("---")
    return "\n".join(lines)


def _yaml_field(key: str, value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, list):
        if not value:
            return [f"{prefix}{key}: []"]
        lines = [f"{prefix}{key}:"]
        for item in value:
            lines.extend(_yaml_list_item(item, indent + 2))
        return lines
    if isinstance(value, dict):
        if not value:
            return [f"{prefix}{key}: {{}}"]
        lines = [f"{prefix}{key}:"]
        for item_key, item_value in value.items():
            lines.extend(_yaml_field(item_key, item_value, indent + 2))
        return lines
    return [f"{prefix}{key}: {_yaml_scalar(value)}"]


def _yaml_list_item(value: Any, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return [f"{prefix}- {{}}"]
        lines: list[str] = []
        first = True
        for item_key, item_value in value.items():
            field_lines = _yaml_field(item_key, item_value, indent + 2)
            if first:
                lines.append(f"{prefix}- {field_lines[0].lstrip()}")
                lines.extend(field_lines[1:])
                first = False
            else:
                lines.extend(field_lines)
        return lines
    if isinstance(value, list):
        if not value:
            return [f"{prefix}- []"]
        lines = [f"{prefix}-"]
        for item in value:
            lines.extend(_yaml_list_item(item, indent + 2))
        return lines
    return [f"{prefix}- {_yaml_scalar(value)}"]


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        if value and _PLAIN_SCALAR_RE.match(value):
            return value
        return quote_yaml(value)
    return quote_yaml(str(value))
