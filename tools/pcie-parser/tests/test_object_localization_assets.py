from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pcie_parser import cli
from pcie_parser.manifest import Manifest
from pcie_parser.models import BBox, ObjectRef, SectionNode, SourceObject, TextSpan
from pcie_parser.objects import extract_object_seeds_from_list_spans, localize_object_from_spans
from pcie_parser.pdf_backend import (
    crop_bbox_to_png,
    extract_table_rows_near_caption,
    infer_graphic_bbox_near_caption,
    table_rows_have_real_content,
    write_table_html,
)
from pcie_parser.render import render_section_body_markdown, spans_to_section_body
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

    def test_table_rows_have_real_content_rejects_empty_and_title_only_rows(self):
        self.assertFalse(table_rows_have_real_content([], "PCIe Signaling Characteristics"))
        self.assertFalse(
            table_rows_have_real_content(
                [["PCIe Signaling Characteristics"]],
                "PCIe Signaling Characteristics",
            )
        )
        self.assertFalse(table_rows_have_real_content([[None, ""]], "PCIe Signaling Characteristics"))
        self.assertTrue(
            table_rows_have_real_content(
                [["Signal", "Rate"], ["Gen1", "2.5 GT/s"]],
                "PCIe Signaling Characteristics",
            )
        )

    def test_cli_does_not_write_title_only_table_html_asset(self):
        caption = span(
            "Table 1-1 PCIe Signaling Characteristics",
            page=1,
            bbox=BBox(40.0, 40.0, 240.0, 55.0),
        )
        obj = make_object(
            object_type="table",
            object_number="1-1",
            title="PCIe Signaling Characteristics",
            listed_page=1,
            page=1,
            bbox=caption.bbox,
            listed_in="List of Tables",
            slug="table-1-1-pcie-signaling-characteristics",
            caption_hash=content_hash(caption.text),
            status="resolved",
        )

        class FakePdfAssetExtractor:
            def __init__(self, _pdf_path: Path):
                pass

            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return None

            def close(self):
                return None

            def infer_graphic_bbox_near_caption(self, _page_number: int, _caption_bbox: BBox, _object_type: str):
                return None

            def extract_table_rows_near_caption(self, _page_number: int, _caption_bbox: BBox):
                return BBox(40.0, 70.0, 240.0, 120.0), [[obj.title]]

        original_extractor = cli.PdfAssetExtractor
        try:
            cli.PdfAssetExtractor = FakePdfAssetExtractor
            with tempfile.TemporaryDirectory() as tmp:
                staged = Path(tmp)
                (staged / "objects" / "tables").mkdir(parents=True)
                manifest = Manifest()
                warnings = []

                cli._write_objects_and_assets(staged, Path("source.pdf"), [caption], [obj], warnings, manifest)

                html_path = staged / "objects" / "tables" / "table-1-1-pcie-signaling-characteristics.html"
                self.assertFalse(html_path.exists())
                self.assertNotIn("html", obj.asset_paths)
                self.assertEqual(obj.status, "resolved_no_asset")
                self.assertEqual([warning.code for warning in warnings], ["object_asset_unresolved"])
        finally:
            cli.PdfAssetExtractor = original_extractor

    def test_unresolved_figure_asset_uses_source_bbox_to_remove_internal_section_rows(self):
        caption = span(
            "Figure 4-54 FEC Table: i to alpha i",
            page=459,
            bbox=BBox(240.0, 660.0, 360.0, 675.0),
            block=4,
        )
        internal_row = span(
            "00: ff 01: 00 02: 01",
            page=459,
            bbox=BBox(148.0, 290.0, 446.0, 300.0),
            block=3,
        )
        obj = make_object(
            object_type="figure",
            object_number="4-54",
            title="FEC Table: i to alpha i",
            listed_page=459,
            page=459,
            bbox=BBox(234.0, 624.0, 366.0, 711.0),
            listed_in="List of Figures",
            slug="figure-4-54-fec-table-i-to-alpha-i",
            section_id="base-7.0:section:4.2.3.4.5",
            caption_hash=content_hash(caption.text),
            status="resolved",
        )

        class FakePdfAssetExtractor:
            def __init__(self, _pdf_path: Path):
                pass

            def close(self):
                return None

            def infer_graphic_bbox_near_caption(self, _page_number: int, _caption_bbox: BBox, _object_type: str):
                return None

            def extract_table_rows_near_caption(self, _page_number: int, _caption_bbox: BBox):
                return None

        original_extractor = cli.PdfAssetExtractor
        try:
            cli.PdfAssetExtractor = FakePdfAssetExtractor
            with tempfile.TemporaryDirectory() as tmp:
                staged = Path(tmp)
                (staged / "objects" / "figures").mkdir(parents=True)
                manifest = Manifest()
                warnings = []

                object_paths = cli._write_objects_and_assets(
                    staged,
                    Path("source.pdf"),
                    [internal_row, caption],
                    [obj],
                    warnings,
                    manifest,
                )

                section = SectionNode(
                    spec_version="base-7.0",
                    section_number="4.2.3.4.5",
                    title="ECC Bytes in Flit",
                    level=5,
                    page_start=459,
                    page_end=459,
                    toc_path=["ECC Bytes in Flit"],
                    object_refs=[
                        ObjectRef(
                            object_id=obj.object_id,
                            path=cli.relative_object_path_from_section(object_paths[obj.object_id]),
                            occurrence="actual",
                        )
                    ],
                )
                section.body_markdown = spans_to_section_body(
                    [
                        internal_row,
                        caption,
                        span(
                            "Visible paragraph after figure.",
                            page=459,
                            bbox=BBox(72.0, 720.0, 260.0, 735.0),
                            block=5,
                        ),
                    ],
                    [obj],
                )
                emitted_body = render_section_body_markdown(section)

                self.assertEqual(obj.status, "resolved_no_asset")
                self.assertEqual(obj.asset_paths, {})
                self.assertEqual([warning.code for warning in warnings], ["object_asset_unresolved"])
                self.assertIn("[Figure 4-54](<../objects/figures/figure-4-54-fec-table-i-to-alpha-i.md>)", emitted_body)
                self.assertNotIn("00: ff 01: 00", emitted_body)
                self.assertIn("Visible paragraph after figure.", emitted_body)
        finally:
            cli.PdfAssetExtractor = original_extractor

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

    def test_infer_figure_bbox_extends_beyond_caption_to_drawn_content(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not available")

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "figure.pdf"
            doc = fitz.open()
            page = doc.new_page(width=300, height=300)
            page.draw_rect(fitz.Rect(80, 60, 220, 150))
            page.insert_text((105, 105), "State A")
            page.insert_text((72, 205), "Figure 4-72 L0s Substate Machine")
            doc.save(pdf_path)
            doc.close()

            caption_bbox = BBox(72.0, 190.0, 250.0, 212.0)
            inferred = infer_graphic_bbox_near_caption(pdf_path, 1, caption_bbox, "figure")

            self.assertIsNotNone(inferred)
            assert inferred is not None
            self.assertLess(inferred.y0, caption_bbox.y0 - 40.0)
            self.assertLessEqual(inferred.x0, 80.0)
            self.assertGreaterEqual(inferred.x1, 220.0)

    def test_infer_equation_bbox_extends_beyond_caption_to_formula_line(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not available")

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "equation.pdf"
            doc = fitz.open()
            page = doc.new_page(width=300, height=240)
            page.insert_text((70, 85), "CREDITS_CONSUMED = PAYLOAD_SIZE / CREDIT_SIZE")
            page.insert_text((72, 132), "Equation 2-1 CREDITS_CONSUMED")
            page.insert_text((72, 170), "This explanatory paragraph follows the caption.")
            doc.save(pdf_path)
            doc.close()

            caption_bbox = BBox(72.0, 118.0, 245.0, 140.0)
            inferred = infer_graphic_bbox_near_caption(pdf_path, 1, caption_bbox, "equation")

            self.assertIsNotNone(inferred)
            assert inferred is not None
            self.assertLess(inferred.y0, caption_bbox.y0 - 20.0)
            self.assertLess(inferred.y1, 150.0)

    def test_extract_table_rows_near_caption_uses_real_pymupdf_table_rows_when_available(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is not available")

        if not hasattr(fitz.Page, "find_tables"):
            self.skipTest("PyMuPDF table detection is not available")

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "table.pdf"
            doc = fitz.open()
            page = doc.new_page(width=320, height=260)
            page.insert_text((50, 50), "Table 1-1 PCIe Signaling Characteristics")
            for y in (80, 110, 140):
                page.draw_line((50, y), (260, y))
            for x in (50, 150, 260):
                page.draw_line((x, 80), (x, 140))
            page.insert_text((65, 100), "Signal")
            page.insert_text((170, 100), "Rate")
            page.insert_text((65, 130), "Gen1")
            page.insert_text((170, 130), "2.5 GT/s")
            doc.save(pdf_path)
            doc.close()

            extracted = extract_table_rows_near_caption(pdf_path, 1, BBox(50.0, 35.0, 260.0, 60.0))

            if extracted is None:
                self.skipTest("PyMuPDF did not detect the synthetic table")
            table_bbox, rows = extracted
            self.assertLess(table_bbox.y0, 90.0)
            flattened = [cell for row in rows for cell in row]
            self.assertIn("Signal", flattened)
            self.assertIn("2.5 GT/s", flattened)


if __name__ == "__main__":
    unittest.main()
