from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pcie_parser.models import BBox, SourceObject, TextSpan
from pcie_parser.objects import extract_object_seeds_from_list_spans, localize_object_from_spans
from pcie_parser.pdf_backend import crop_bbox_to_png, write_table_html
from pcie_parser.slug import content_hash


def span(
    text: str,
    page: int,
    bbox: BBox | None = None,
    block: int = 0,
    line: int = 0,
    span_index: int = 0,
) -> TextSpan:
    return TextSpan(
        text=text,
        page=page,
        bbox=bbox or BBox(72.0, 100.0, 400.0, 120.0),
        block=block,
        line=line,
        span=span_index,
    )


def make_object(**overrides: object) -> SourceObject:
    values = {
        "spec_version": "base-7.0",
        "object_type": "figure",
        "object_number": "4-72",
        "title": "L0s Substate Machine",
        "listed_page": 100,
        "page": None,
        "bbox": None,
        "section_id": "base-7.0:section:4.2.6",
        "listed_in": "List of Figures",
        "status": "unresolved_bbox",
    }
    values.update(overrides)
    return SourceObject(**values)


class ObjectLocalizationAssetTests(unittest.TestCase):
    def test_extract_object_seeds_from_list_spans_uses_listed_page_expected_type_id_title_and_slug(self):
        spans = [
            span("Table 4-14 Wrong Type .... 500", page=8, line=0),
            span("Figure 4-72", page=8, line=1, span_index=0),
            span("L0s Substate Machine .... 515", page=8, line=1, span_index=1),
            span("Figure 4-72 Duplicate .... 516", page=8, line=2),
            span("Equation 4-1 Wrong Type .... 517", page=8, line=3),
        ]

        objects = extract_object_seeds_from_list_spans("base-7.0", spans, "List of Figures")

        self.assertEqual(len(objects), 1)
        obj = objects[0]
        self.assertEqual(obj.object_type, "figure")
        self.assertEqual(obj.object_number, "4-72")
        self.assertEqual(obj.object_id, "base-7.0:figure:4-72")
        self.assertEqual(obj.title, "L0s Substate Machine")
        self.assertEqual(obj.listed_page, 515)
        self.assertEqual(obj.slug, "figure-4-72-l0s-substate-machine")
        self.assertEqual(obj.status, "unresolved_bbox")
        self.assertIsNone(obj.page)
        self.assertIsNone(obj.bbox)

    def test_extract_object_seeds_treats_appendix_labels_as_entry_boundaries(self):
        spans = [
            span("Figure 12-22", page=54, line=0),
            span("Example Tiers Involving Sidebands .... 1876", page=54, line=1),
            span("Figure A-1", page=54, line=2),
            span("Endpoint to Root Complex Communication Models .... 1877", page=54, line=3),
            span("Standalone notice text that is not part of the list", page=54, line=4),
        ]

        objects = extract_object_seeds_from_list_spans("base-7.0", spans, "List of Figures")

        self.assertEqual([obj.object_id for obj in objects], ["base-7.0:figure:12-22", "base-7.0:figure:A-1"])
        self.assertEqual(objects[0].title, "Example Tiers Involving Sidebands")
        self.assertEqual(objects[1].title, "Endpoint to Root Complex Communication Models")

    def test_localize_object_from_spans_uses_fallback_pages_and_expands_bbox(self):
        obj = make_object(listed_page=100)
        caption = span(
            "Figure 4-72 L0s Substate Machine",
            page=98,
            bbox=BBox(72.0, 200.0, 400.0, 220.0),
        )

        localized, warnings = localize_object_from_spans(obj, [caption], section_start=120, section_end=121)

        self.assertEqual(warnings, [])
        self.assertIs(localized, obj)
        self.assertEqual(obj.status, "resolved")
        self.assertEqual(obj.page, 98)
        self.assertEqual(obj.bbox.as_list(), [66.0, 164.0, 406.0, 256.0])
        self.assertEqual(obj.caption_hash, content_hash("Figure 4-72 L0s Substate Machine"))

    def test_unresolved_localization_sets_status_and_returns_warning(self):
        obj = make_object(listed_page=100)

        localized, warnings = localize_object_from_spans(
            obj,
            [span("Figure 4-73 Other Caption", page=100)],
            section_start=None,
            section_end=None,
        )

        self.assertIs(localized, obj)
        self.assertEqual(obj.status, "unresolved_bbox")
        self.assertIsNone(obj.page)
        self.assertIsNone(obj.bbox)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].code, "object_bbox_unresolved")
        self.assertEqual(warnings[0].object_id, "base-7.0:figure:4-72")

    def test_write_table_html_creates_basic_escaped_html_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "table.html"

            write_table_html(path, 'Receiver <Ready> & "Go"', [["A&B", "<td>", '"quote"']])

            html = path.read_text(encoding="utf-8")
        self.assertIn("<table>", html)
        self.assertIn("<caption>Receiver &lt;Ready&gt; &amp; &quot;Go&quot;</caption>", html)
        self.assertIn("<td>A&amp;B</td>", html)
        self.assertIn("<td>&lt;td&gt;</td>", html)
        self.assertIn("<td>&quot;quote&quot;</td>", html)
        self.assertNotIn("\r\n", html)

    def test_crop_bbox_to_png_writes_png_when_pymupdf_is_available(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not available")

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "source.pdf"
            output_path = Path(tmp) / "crop.png"
            doc = fitz.open()
            page = doc.new_page(width=200, height=200)
            page.insert_text((72, 72), "PCIe")
            doc.save(pdf_path)
            doc.close()

            crop_bbox_to_png(pdf_path, 1, BBox(0.0, 0.0, 100.0, 100.0), output_path)

            self.assertTrue(output_path.is_file())
            self.assertEqual(output_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
