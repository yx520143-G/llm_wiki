from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path
from typing import Sequence

from pcie_parser.manifest import Manifest, section_record
from pcie_parser.pdf_backend import PdfBackend, outline_entries_to_sections
from pcie_parser.render import render_section_markdown
from pcie_parser.slug import content_hash, section_slug
from pcie_parser.writer import assert_inside_project, replace_output_dir


_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


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


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        version = validate_version(args.version)
        project_root = _validated_project_root(Path(args.project))
        pdf_path = _validated_pdf_path(Path(args.pdf), project_root)
        final_dir = _validated_final_dir(project_root, version)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    outline_entries, page_count = PdfBackend(pdf_path).extract_outline()
    if not outline_entries:
        raise SystemExit("PDF outline is absent or unusable")

    sections = outline_entries_to_sections(version, outline_entries, page_count)
    if not sections:
        raise SystemExit("PDF outline produced no numbered sections")

    staged = _make_staged_dir(final_dir)
    try:
        manifest = Manifest()
        sections_dir = staged / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
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
