import json
import subprocess
import unittest
from pathlib import Path

from pcie_parser.models import BBox, ObjectRef, ParagraphAnchor, SectionNode, SourceObject
from pcie_parser.render import render_object_markdown, render_section_markdown
from pcie_parser.slug import content_hash


REPO_ROOT = Path(__file__).resolve().parents[3]


def split_frontmatter(markdown: str) -> tuple[str, str]:
    marker = "---\n"
    if not markdown.startswith(marker):
        raise AssertionError("markdown does not start with frontmatter")
    end = markdown.find("\n---", len(marker))
    if end < 0:
        raise AssertionError("markdown does not close frontmatter")
    frontmatter = markdown[len(marker) : end]
    body = markdown[end + len("\n---") :]
    if body.startswith("\n\n"):
        body = body[2:]
    elif body.startswith("\n"):
        body = body[1:]
    return frontmatter, body


def load_with_js_yaml(frontmatter: str) -> dict[str, object] | None:
    script = (
        "const yaml = require('js-yaml');"
        "const fs = require('fs');"
        "const input = fs.readFileSync(0, 'utf8');"
        "process.stdout.write(JSON.stringify(yaml.load(input)));"
    )
    try:
        result = subprocess.run(
            ["node", "-e", script],
            input=frontmatter,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return json.loads(result.stdout)


def make_section(**overrides: object) -> SectionNode:
    values = {
        "spec_version": "base-7.0",
        "section_number": "4.2.6",
        "title": "L0s State",
        "level": 3,
        "page_start": 512,
        "page_end": 518,
        "toc_path": ["Chapter 4", "4.2.6 L0s State"],
        "parent_id": "base-7.0:section:4.2",
        "child_ids": [],
        "slug": "sec-4.2.6-l0s-state",
        "body_markdown": "The L0s state is entered after idle conditions.",
        "object_refs": [],
        "paragraph_anchors": [
            ParagraphAnchor("p0001", 512, BBox(72.1, 130.5, 520.8, 188.2), "sha256:abc")
        ],
        "content_hash": content_hash("The L0s state is entered after idle conditions."),
    }
    values.update(overrides)
    return SectionNode(**values)


def make_object(**overrides: object) -> SourceObject:
    values = {
        "spec_version": "base-7.0",
        "object_type": "figure",
        "object_number": "4-72",
        "title": "L0s Substate Machine",
        "listed_page": 515,
        "page": 515,
        "bbox": BBox(72.0, 164.0, 540.0, 612.0),
        "section_id": "base-7.0:section:4.2.6",
        "listed_in": "List of Figures",
        "slug": "figure-4-72-l0s-substate-machine",
        "asset_paths": {"image": "figure-4-72-l0s-substate-machine.png"},
        "caption_hash": "sha256:caption",
        "content_hash": "sha256:content",
    }
    values.update(overrides)
    return SourceObject(**values)


class RenderTests(unittest.TestCase):
    def test_section_frontmatter_contains_pcie_metadata_and_placeholder(self):
        fake_object = make_object(title="L0s Substate Machine internal text")
        section = make_section(
            body_markdown=(
                "The L0s state is entered after idle conditions.\n\n"
                "{{object:base-7.0:figure:4-72}}"
            ),
            object_refs=[
                ObjectRef(
                    object_id="base-7.0:figure:4-72",
                    path="../objects/figures/figure-4-72-l0s-substate-machine.md",
                    occurrence="actual",
                )
            ],
        )

        markdown = render_section_markdown(section, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        frontmatter, body = split_frontmatter(markdown)

        self.assertIn('type: "pcie_section"', frontmatter)
        self.assertIn('section_id: "base-7.0:section:4.2.6"', frontmatter)
        self.assertIn(
            "[Figure 4-72](<../objects/figures/figure-4-72-l0s-substate-machine.md>)",
            body,
        )
        self.assertNotIn(fake_object.title, markdown)

    def test_object_markdown_links_image_asset_and_uses_title_frontmatter(self):
        obj = make_object()

        markdown = render_object_markdown(obj, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        frontmatter, body = split_frontmatter(markdown)

        self.assertIn('type: "pcie_object"', frontmatter)
        self.assertIn('object_id: "base-7.0:figure:4-72"', frontmatter)
        self.assertIn('title: "L0s Substate Machine"', frontmatter)
        self.assertNotIn("object_title:", frontmatter)
        self.assertEqual(
            "![L0s Substate Machine](<figure-4-72-l0s-substate-machine.png>)\n",
            body,
        )

    def test_numeric_strings_are_quoted_and_parse_as_strings_when_js_yaml_is_available(self):
        tricky_title = 'Receiver: "Ready" 状态'
        section = make_section(section_number="1", title=tricky_title)
        obj = make_object(object_number="1", title=tricky_title)

        section_frontmatter, _ = split_frontmatter(
            render_section_markdown(section, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        )
        object_frontmatter, _ = split_frontmatter(
            render_object_markdown(obj, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        )

        self.assertIn('section_number: "1"', section_frontmatter)
        self.assertIn('section_title: "Receiver: \\"Ready\\" 状态"', section_frontmatter)
        self.assertIn('object_number: "1"', object_frontmatter)
        self.assertIn('title: "Receiver: \\"Ready\\" 状态"', object_frontmatter)

        parsed_section = load_with_js_yaml(section_frontmatter)
        parsed_object = load_with_js_yaml(object_frontmatter)
        if parsed_section is not None and parsed_object is not None:
            self.assertEqual("1", parsed_section["section_number"])
            self.assertIsInstance(parsed_section["section_number"], str)
            self.assertEqual(tricky_title, parsed_section["section_title"])
            self.assertEqual("1", parsed_object["object_number"])
            self.assertIsInstance(parsed_object["object_number"], str)
            self.assertEqual(tricky_title, parsed_object["title"])

    def test_section_body_replaces_multiple_repeated_refs_and_keeps_unknown_placeholders(self):
        section = make_section(
            body_markdown=(
                "First {{object:base-7.0:figure:1}} and {{object:base-7.0:table:2}}.\n"
                "Repeat {{object:base-7.0:figure:1}}.\n"
                "Unknown {{object:base-7.0:figure:999}}."
            ),
            object_refs=[
                ObjectRef(
                    object_id="base-7.0:figure:1",
                    path="../objects/figures/figure 1 (draft).md",
                    occurrence="actual",
                ),
                ObjectRef(
                    object_id="base-7.0:table:2",
                    path="../objects/tables/table-2.md",
                    occurrence="reference",
                ),
            ],
        )

        _, body = split_frontmatter(
            render_section_markdown(section, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        )

        self.assertEqual(
            "First [Figure 1](<../objects/figures/figure 1 (draft).md>) "
            "and [Table 2](<../objects/tables/table-2.md>).\n"
            "Repeat [Figure 1](<../objects/figures/figure 1 (draft).md>).\n"
            "Unknown {{object:base-7.0:figure:999}}.\n",
            body,
        )

    def test_table_body_renders_image_html_json_in_stable_order(self):
        obj = make_object(
            object_type="table",
            object_number="4-12",
            title="Timing Table",
            listed_in="List of Tables",
            slug="table-4-12-timing-table",
            asset_paths={
                "json": "tables/table-4-12.json",
                "image": "tables/table-4-12.png",
                "html": "tables/table-4-12.html",
            },
        )

        _, body = split_frontmatter(
            render_object_markdown(obj, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        )

        self.assertEqual(
            "![Timing Table](<tables/table-4-12.png>)\n\n"
            "[HTML](<tables/table-4-12.html>)\n\n"
            "[JSON](<tables/table-4-12.json>)\n",
            body,
        )

    def test_asset_paths_frontmatter_order_is_stable(self):
        asset_paths_a = {
            "json": "tables/table-4-12.json",
            "image": "tables/table-4-12.png",
            "html": "tables/table-4-12.html",
        }
        asset_paths_b = {
            "image": "tables/table-4-12.png",
            "html": "tables/table-4-12.html",
            "json": "tables/table-4-12.json",
        }
        obj_a = make_object(object_type="table", object_number="4-12", asset_paths=asset_paths_a)
        obj_b = make_object(object_type="table", object_number="4-12", asset_paths=asset_paths_b)

        frontmatter_a, _ = split_frontmatter(
            render_object_markdown(obj_a, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        )
        frontmatter_b, _ = split_frontmatter(
            render_object_markdown(obj_b, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        )

        self.assertEqual(frontmatter_a, frontmatter_b)
        lines = frontmatter_a.splitlines()
        asset_paths_index = lines.index("asset_paths:")
        self.assertEqual(
            [
                '  html: "tables/table-4-12.html"',
                '  image: "tables/table-4-12.png"',
                '  json: "tables/table-4-12.json"',
            ],
            lines[asset_paths_index + 1 : asset_paths_index + 4],
        )

    def test_markdown_escapes_labels_and_angle_destinations(self):
        obj = make_object(
            title="Receiver [A] \\ State\nLine",
            asset_paths={"image": "assets/path <draft>\\file (1).png"},
        )

        _, body = split_frontmatter(
            render_object_markdown(obj, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        )

        self.assertEqual(
            "![Receiver \\[A\\] \\\\ State Line]"
            "(<assets/path \\<draft\\>\\\\file (1).png>)\n",
            body,
        )


if __name__ == "__main__":
    unittest.main()
