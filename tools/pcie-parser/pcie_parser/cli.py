from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from typing import Sequence

from pcie_parser.manifest import Manifest, section_record
from pcie_parser.pdf_backend import PdfBackend, outline_entries_to_sections
from pcie_parser.render import render_section_markdown
from pcie_parser.slug import content_hash, section_slug
from pcie_parser.writer import assert_inside_project, replace_output_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse a PCIe Base Specification PDF into LLM Wiki sources.")
    parser.add_argument("--project", required=True, help="LLM Wiki project root.")
    parser.add_argument("--pdf", required=True, help="PCIe Base Specification PDF path.")
    parser.add_argument("--version", required=True, help="Parsed output version, for example base-7.0.")
    return parser.parse_args(argv)


def version_output_dir(project_root: Path, version: str) -> Path:
    return project_root / "raw" / "sources" / "parsed" / version


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project)
    pdf_path = Path(args.pdf)
    final_dir = version_output_dir(project_root, args.version)
    assert_inside_project(project_root, final_dir)

    outline_entries, page_count = PdfBackend(pdf_path).extract_outline()
    if not outline_entries:
        raise SystemExit("PDF outline is absent or unusable")

    sections = outline_entries_to_sections(args.version, outline_entries, page_count)
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
                raise ValueError(
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


def _make_staged_dir(final_dir: Path) -> Path:
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".{final_dir.name}.", suffix=".staged", dir=final_dir.parent))
