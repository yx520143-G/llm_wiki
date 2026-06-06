from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Sequence

from pcie_parser.manifest import Manifest, object_record, section_record, warning_record
from pcie_parser.models import ParseWarning, SectionNode, SourceObject, TextSpan
from pcie_parser.objects import extract_object_seeds_from_list_spans, localize_object_from_spans
from pcie_parser.pdf_backend import PdfBackend, crop_bbox_to_png, outline_entries_to_sections, write_table_html
from pcie_parser.render import render_object_markdown, render_section_markdown
from pcie_parser.slug import content_hash, section_slug
from pcie_parser.writer import assert_inside_project, replace_output_dir


_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
OBJECT_LIST_TITLES = ("List of Figures", "List of Tables", "List of Equations")
OBJECT_SUBDIRS = {
    "figure": "figures",
    "table": "tables",
    "equation": "equations",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse a PCIe Base Specification PDF into LLM Wiki sources.")
    parser.add_argument("--project", required=True, help="LLM Wiki project root.")
    parser.add_argument("--pdf", required=True, help="PCIe Base Specification PDF path.")
    parser.add_argument("--version", required=True, help="Parsed output version, for example base-7.0.")
    return parser.parse_args(argv)


def validate_version(version: str) -> str:
    if not version or version.strip() != version:
        raise ValueError("Version must be a non-empty safe directory name")
    if version in {".", ".."}:
        raise ValueError("Version must not be '.' or '..'")
    if Path(version).is_absolute() or "/" in version or "\\" in version:
        raise ValueError("Version must be a single directory name without path separators")
    if _VERSION_RE.fullmatch(version) is None:
        raise ValueError("Version must contain only letters, digits, dots, underscores, and hyphens")
    return version


def version_output_dir(project_root: Path, version: str) -> Path:
    version = validate_version(version)
    return project_root / "raw" / "sources" / "parsed" / version


def find_section_for_page(sections: list[SectionNode], page: int) -> SectionNode | None:
    candidates = [section for section in sections if section.page_start <= page <= section.page_end]
    if not candidates:
        return None
    return max(candidates, key=lambda section: (section.level, section.page_start, -section.page_end))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        version = validate_version(args.version)
        project_root = _validated_project_root(Path(args.project))
        pdf_path = _validated_pdf_path(Path(args.pdf), project_root)
        final_dir = _validated_final_dir(project_root, version)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    backend = PdfBackend(pdf_path)
    outline_entries, page_count = backend.extract_outline()
    if not outline_entries:
        raise SystemExit("PDF outline is absent or unusable")

    sections = outline_entries_to_sections(version, outline_entries, page_count)
    if not sections:
        raise SystemExit("PDF outline produced no numbered sections")

    spans = backend.extract_text_spans()
    objects, object_warnings = _extract_and_localize_objects(version, spans, outline_entries, page_count, sections)

    staged = _make_staged_dir(final_dir)
    try:
        manifest = Manifest()
        sections_dir = staged / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        objects_root = staged / "objects"
        for subdir in OBJECT_SUBDIRS.values():
            (objects_root / subdir).mkdir(parents=True, exist_ok=True)

        _write_objects_and_assets(staged, pdf_path, objects, object_warnings, manifest)

        seen_slugs: dict[str, str] = {}

        for section in sections:
            section.body_markdown = ""
            section.content_hash = content_hash(section.body_markdown)
            section.slug = section_slug(section.section_number, section.title)
            previous_section_id = seen_slugs.get(section.slug)
            if previous_section_id is not None:
                raise SystemExit(
                    f"Duplicate section slug {section.slug!r} for "
                    f"{previous_section_id!r} and {section.section_id!r}"
                )
            seen_slugs[section.slug] = section.section_id

            relative_path = Path("sections") / f"{section.slug}.md"
            output_path = staged / relative_path
            output_path.write_text(
                render_section_markdown(section, source_pdf=pdf_path.name),
                encoding="utf-8",
                newline="\n",
            )
            manifest.add(section_record(section, relative_path.as_posix()))

        manifest.write(staged / "manifest.jsonl")
        replace_output_dir(staged, final_dir)
        print(f"Wrote {len(sections)} section files to {final_dir}")
        return 0
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def _extract_and_localize_objects(
    spec_version: str,
    spans: list[TextSpan],
    outline_entries: list[tuple[int, str, int]],
    page_count: int,
    sections: list[SectionNode],
) -> tuple[list[SourceObject], list[ParseWarning]]:
    objects: list[SourceObject] = []
    warnings: list[ParseWarning] = []
    seen_ids: dict[str, str] = {}

    for listed_in in OBJECT_LIST_TITLES:
        list_spans = _spans_for_outline_title(spans, outline_entries, page_count, listed_in)
        for obj in extract_object_seeds_from_list_spans(spec_version, list_spans, listed_in):
            previous_list = seen_ids.get(obj.object_id)
            if previous_list is not None:
                raise SystemExit(
                    f"Duplicate object id {obj.object_id!r} from {previous_list!r} and {listed_in!r}"
                )
            seen_ids[obj.object_id] = listed_in

            section = find_section_for_page(sections, obj.listed_page)
            section_start: int | None = None
            section_end: int | None = None
            if section is not None:
                obj.section_id = section.section_id
                section_start = section.page_start
                section_end = section.page_end

            localized, localization_warnings = localize_object_from_spans(
                obj,
                spans,
                section_start=section_start,
                section_end=section_end,
            )
            objects.append(localized)
            warnings.extend(localization_warnings)

    return objects, warnings


def _spans_for_outline_title(
    spans: list[TextSpan],
    outline_entries: list[tuple[int, str, int]],
    page_count: int,
    title: str,
) -> list[TextSpan]:
    ranges = _outline_page_ranges_for_title(outline_entries, page_count, title)
    return [span for span in spans if any(start <= span.page <= end for start, end in ranges)]


def _outline_page_ranges_for_title(
    outline_entries: list[tuple[int, str, int]],
    page_count: int,
    title: str,
) -> list[tuple[int, int]]:
    normalized_title = _normalize_outline_title(title)
    entries = [(int(level), str(entry_title), int(page)) for level, entry_title, page in outline_entries]
    ranges: list[tuple[int, int]] = []
    for index, (level, entry_title, start_page) in enumerate(entries):
        if _normalize_outline_title(entry_title) != normalized_title:
            continue

        end_page = page_count
        for next_level, _next_title, next_page in entries[index + 1 :]:
            if next_level <= level:
                end_page = max(start_page, next_page - 1)
                break
        ranges.append((start_page, end_page))
    return ranges


def _normalize_outline_title(title: str) -> str:
    return " ".join(title.strip().split()).lower()


def _write_objects_and_assets(
    staged: Path,
    pdf_path: Path,
    objects: list[SourceObject],
    warnings: list[ParseWarning],
    manifest: Manifest,
) -> None:
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()

    for obj in objects:
        if obj.object_id in seen_ids:
            raise SystemExit(f"Duplicate object id {obj.object_id!r}")
        seen_ids.add(obj.object_id)

        subdir = OBJECT_SUBDIRS[obj.object_type]
        object_relative_path = Path("objects") / subdir / f"{obj.slug}.md"
        _ensure_unique_output_path(object_relative_path, seen_paths, "object")

        if obj.object_type in {"figure", "equation"} and obj.page is not None and obj.bbox is not None:
            image_name = f"{obj.slug}.png"
            image_relative_path = object_relative_path.parent / image_name
            _ensure_unique_output_path(image_relative_path, seen_paths, "asset")
            crop_bbox_to_png(pdf_path, obj.page, obj.bbox, staged / image_relative_path)
            obj.asset_paths["image"] = image_name
        elif obj.object_type == "table":
            html_name = f"{obj.slug}.html"
            html_relative_path = object_relative_path.parent / html_name
            _ensure_unique_output_path(html_relative_path, seen_paths, "asset")
            write_table_html(staged / html_relative_path, obj.title, [[obj.title]])
            obj.asset_paths["html"] = html_name

        obj.content_hash = _object_content_hash(obj)
        output_path = staged / object_relative_path
        output_path.write_text(
            render_object_markdown(obj, source_pdf=pdf_path.name),
            encoding="utf-8",
            newline="\n",
        )
        manifest.add(object_record(obj, object_relative_path.as_posix()))

    for warning in warnings:
        manifest.add(warning_record(warning))


def _ensure_unique_output_path(path: Path, seen_paths: set[str], kind: str) -> None:
    normalized = path.as_posix()
    if normalized in seen_paths:
        raise SystemExit(f"Duplicate {kind} output path {normalized!r}")
    seen_paths.add(normalized)


def _object_content_hash(obj: SourceObject) -> str:
    payload = {
        "object_id": obj.object_id,
        "object_type": obj.object_type,
        "object_number": obj.object_number,
        "title": obj.title,
        "listed_page": obj.listed_page,
        "page": obj.page,
        "bbox": obj.bbox.as_list() if obj.bbox else None,
        "section_id": obj.section_id,
        "listed_in": obj.listed_in,
        "asset_paths": dict(sorted(obj.asset_paths.items())),
        "caption_hash": obj.caption_hash,
        "status": obj.status,
    }
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _validated_project_root(project_root: Path) -> Path:
    resolved = project_root.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"Project root must exist and be a directory: {resolved}")
    return resolved


def _validated_pdf_path(pdf_path: Path, project_root: Path) -> Path:
    resolved = pdf_path.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"PDF path must exist and be a file: {resolved}")

    originals_dir = (project_root / "raw" / "originals").resolve()
    if originals_dir not in resolved.parents:
        raise ValueError(f"PDF path must be under project raw/originals: {resolved}")
    return resolved


def _validated_final_dir(project_root: Path, version: str) -> Path:
    parsed_root = (project_root / "raw" / "sources" / "parsed").resolve()
    final_dir = version_output_dir(project_root, version)
    resolved_final_dir = final_dir.resolve()
    if final_dir.parent.resolve() != parsed_root or resolved_final_dir.parent != parsed_root:
        raise ValueError(f"Final output must be under project raw/sources/parsed: {resolved_final_dir}")
    assert_inside_project(project_root, resolved_final_dir)
    return final_dir


def _make_staged_dir(final_dir: Path) -> Path:
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".{final_dir.name}.", suffix=".staged", dir=final_dir.parent))
