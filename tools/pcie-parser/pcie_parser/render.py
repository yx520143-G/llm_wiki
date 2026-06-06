from __future__ import annotations

import json
from typing import Any

from pcie_parser import PARSER_VERSION
from pcie_parser.bbox import bbox_contains, expand_bbox
from pcie_parser.models import BBox, ObjectRef, ParagraphAnchor, SectionNode, SourceObject, TextSpan


_OBJECT_BBOX_VERTICAL_MARGIN = 36.0
_OBJECT_BBOX_HORIZONTAL_MARGIN = 6.0


def quote_yaml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


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


def spans_to_section_body(spans: list[TextSpan], objects: list[SourceObject]) -> str:
    ordered_spans = sorted(spans, key=_span_order_key)
    object_entries = _section_object_entries(objects, ordered_spans)
    removed_by_object_id: dict[str, list[TextSpan]] = {entry.object_id: [] for entry in object_entries}
    body_items: list[_BodyItem] = []

    for span in ordered_spans:
        containing_entry = _containing_object_entry(span, object_entries)
        if containing_entry is not None:
            removed_by_object_id[containing_entry.object_id].append(span)
            continue
        text = _normalized_body_text(span.text)
        if text:
            body_items.append(
                _BodyItem(
                    text=text,
                    order_key=_span_order_key(span),
                    line_key=(span.page, span.block, span.line),
                )
            )

    seen_placeholders: set[str] = set()
    for entry in object_entries:
        if entry.object_id in seen_placeholders:
            continue
        seen_placeholders.add(entry.object_id)
        removed_spans = removed_by_object_id.get(entry.object_id, [])
        if removed_spans:
            first_removed = min(removed_spans, key=_span_order_key)
            order_key = _span_order_key(first_removed)
            line_key = (first_removed.page, first_removed.block, first_removed.line)
        else:
            order_key, line_key = _object_order_position(entry, ordered_spans)
        body_items.append(
            _BodyItem(
                text=f"{{{{object:{entry.object_id}}}}}",
                order_key=order_key,
                line_key=line_key,
            )
        )

    return _body_items_to_markdown(body_items)


def render_section_body_markdown(section: SectionNode) -> str:
    body = section.body_markdown
    for ref in section.object_refs:
        placeholder = f"{{{{object:{ref.object_id}}}}}"
        body = body.replace(placeholder, _section_object_link(ref))
    return body


def render_section_markdown(section: SectionNode, source_pdf: str) -> str:
    body = render_section_body_markdown(section)
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
            ("title", obj.title),
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
        lines.append(_object_asset_link(obj.title, image_path, image=True))
    if obj.object_type == "table":
        for asset_key in ("image", "html", "json"):
            asset_path = obj.asset_paths.get(asset_key)
            if not asset_path:
                continue
            if asset_key == "image":
                lines.append(_object_asset_link(obj.title, asset_path, image=True))
            else:
                lines.append(_object_asset_link(asset_key.upper(), asset_path))
    return "\n\n".join(lines)


def _section_object_link(ref: ObjectRef) -> str:
    return _markdown_link(label_for_object_ref(ref.object_id), ref.path)


def _object_asset_link(label: str, destination: str, image: bool = False) -> str:
    return _markdown_link(label, destination, image=image)


def _markdown_link(label: str, destination: str, image: bool = False) -> str:
    prefix = "!" if image else ""
    return f"{prefix}[{_markdown_label(label)}](<{_markdown_destination(destination)}>)"


def _markdown_label(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _markdown_destination(value: str) -> str:
    return (
        value.replace("\r\n", "%0A")
        .replace("\r", "%0A")
        .replace("\n", "%0A")
        .replace("\\", "\\\\")
        .replace("<", "\\<")
        .replace(">", "\\>")
    )


def _object_ref_record(ref: ObjectRef) -> dict[str, str]:
    return {
        "object_id": ref.object_id,
        "path": ref.path,
        "occurrence": ref.occurrence,
    }


class _ObjectEntry:
    def __init__(self, object_id: str, page: int, bbox: BBox, expanded_bbox: BBox) -> None:
        self.object_id = object_id
        self.page = page
        self.bbox = bbox
        self.expanded_bbox = expanded_bbox


class _BodyItem:
    def __init__(
        self,
        text: str,
        order_key: tuple[int, int, int, float, float, float, str],
        line_key: tuple[int, int, int],
    ) -> None:
        self.text = text
        self.order_key = order_key
        self.line_key = line_key


def _section_object_entries(objects: list[SourceObject], spans: list[TextSpan]) -> list[_ObjectEntry]:
    entries: list[_ObjectEntry] = []
    seen_object_ids: set[str] = set()
    for obj in objects:
        if obj.object_id in seen_object_ids or obj.page is None or obj.bbox is None:
            continue
        seen_object_ids.add(obj.object_id)
        entries.append(
            _ObjectEntry(
                object_id=obj.object_id,
                page=obj.page,
                bbox=obj.bbox,
                expanded_bbox=expand_bbox(
                    obj.bbox,
                    vertical=_OBJECT_BBOX_VERTICAL_MARGIN,
                    horizontal=_OBJECT_BBOX_HORIZONTAL_MARGIN,
                ),
            )
        )
    return sorted(entries, key=lambda entry: _visual_object_key(entry, spans))


def _containing_object_entry(span: TextSpan, object_entries: list[_ObjectEntry]) -> _ObjectEntry | None:
    candidates = [
        entry
        for entry in object_entries
        if entry.page == span.page and bbox_contains(entry.expanded_bbox, span.bbox)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda entry: (entry.page, entry.bbox.y0, entry.bbox.x0, entry.object_id))


def _object_order_position(
    entry: _ObjectEntry,
    ordered_spans: list[TextSpan],
) -> tuple[tuple[int, int, int, float, float, float, str], tuple[int, int, int]]:
    same_page_spans = [span for span in ordered_spans if span.page == entry.page]
    later_spans = [
        span
        for span in same_page_spans
        if (span.bbox.y0, span.bbox.x0, span.bbox.y1, span.bbox.x1)
        >= (entry.bbox.y0, entry.bbox.x0, entry.bbox.y1, entry.bbox.x1)
    ]
    if later_spans:
        anchor = min(later_spans, key=lambda span: (span.bbox.y0, span.bbox.x0, _span_order_key(span)))
        key = _span_order_key(anchor)
        return (
            (key[0], key[1], key[2], key[3] - 0.5, entry.bbox.y0, entry.bbox.x0, entry.object_id),
            (anchor.page, anchor.block, anchor.line),
        )
    if same_page_spans:
        anchor = max(same_page_spans, key=_span_order_key)
        key = _span_order_key(anchor)
        return (
            (entry.page, key[1] + 1, 0, 0.0, entry.bbox.y0, entry.bbox.x0, entry.object_id),
            (entry.page, key[1] + 1, 0),
        )
    return (
        (entry.page, 0, 0, 0.0, entry.bbox.y0, entry.bbox.x0, entry.object_id),
        (entry.page, 0, 0),
    )


def _visual_object_key(entry: _ObjectEntry, spans: list[TextSpan]) -> tuple[int, int, int, float, float, float, str]:
    order_key, _line_key = _object_order_position(entry, spans)
    return order_key


def _body_items_to_markdown(items: list[_BodyItem]) -> str:
    if not items:
        return ""

    lines: list[tuple[tuple[int, int, int], list[_BodyItem]]] = []
    current_line_key: tuple[int, int, int] | None = None
    current_items: list[_BodyItem] = []
    for item in sorted(items, key=lambda body_item: body_item.order_key):
        if current_line_key is not None and item.line_key != current_line_key:
            lines.append((current_line_key, current_items))
            current_items = []
        current_line_key = item.line_key
        current_items.append(item)
    if current_line_key is not None:
        lines.append((current_line_key, current_items))

    body_lines: list[str] = []
    previous_line_key: tuple[int, int, int] | None = None
    for line_key, line_items in lines:
        if previous_line_key is not None:
            previous_page, previous_block, _previous_line = previous_line_key
            page, block, _line = line_key
            if page != previous_page or block != previous_block:
                body_lines.append("")
        body_lines.append(" ".join(item.text for item in sorted(line_items, key=lambda body_item: body_item.order_key)))
        previous_line_key = line_key
    return "\n".join(body_lines).rstrip()


def _span_order_key(span: TextSpan) -> tuple[int, int, int, float, float, float, str]:
    return (span.page, span.block, span.line, float(span.span), span.bbox.y0, span.bbox.x0, span.text)


def _normalized_body_text(text: str) -> str:
    return " ".join(text.strip().split())


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
        for item_key, item_value in _sorted_dict_items(value):
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
        for item_key, item_value in _sorted_dict_items(value):
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
        return quote_yaml(value)
    return quote_yaml(str(value))


def _sorted_dict_items(value: dict[Any, Any]) -> list[tuple[Any, Any]]:
    return sorted(value.items(), key=lambda item: str(item[0]))
