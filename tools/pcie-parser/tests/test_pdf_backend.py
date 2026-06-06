from __future__ import annotations

import unittest

from pcie_parser.models import BBox
from pcie_parser.pdf_backend import PdfBackend, outline_entries_to_sections, span_dict_to_text_span


class FakePage:
    def __init__(self, page_dict=None, error: Exception | None = None):
        self.page_dict = page_dict or {"blocks": []}
        self.error = error
        self.calls = []

    def get_text(self, mode, **kwargs):
        self.calls.append((mode, kwargs))
        if self.error is not None:
            raise self.error
        return self.page_dict


class FakeDoc:
    def __init__(self, pages):
        self.pages = pages
        self.page_count = len(pages)
        self.closed = False

    def load_page(self, index):
        return self.pages[index]

    def close(self):
        self.closed = True


class FakeBackend(PdfBackend):
    def __init__(self, doc):
        super().__init__("fake.pdf")
        self.doc = doc

    def open_document(self):
        return self.doc


class PdfBackendTests(unittest.TestCase):
    def test_section_prefix_is_parsed_and_stripped(self):
        entries = [
            (1, "Section 4.2.6 L0s State", 100),
            (1, "Section 4.2.7. Recovery", 110),
            (1, "Section 4.2.8: Configuration", 120),
            (1, "Chapter 1. Introduction", 130),
            (1, "1.1 Scope", 140),
        ]
        sections = outline_entries_to_sections("base-7.0", entries, page_count=150)
        by_number = {section.section_number: section for section in sections}

        self.assertEqual(by_number["4.2.6"].title, "L0s State")
        self.assertEqual(by_number["4.2.7"].title, "Recovery")
        self.assertEqual(by_number["4.2.8"].title, "Configuration")
        self.assertEqual(by_number["1"].title, "Introduction")
        self.assertEqual(by_number["1.1"].title, "Scope")

    def test_outline_entries_to_sections_sets_page_end_from_next_sibling_or_parent(self):
        entries = [
            (1, "Chapter 4 Physical Layer Logical Block", 500),
            (2, "Section 4.2 Link Training and Status State Machine", 510),
            (3, "Section 4.2.1 Polling", 512),
            (3, "Section 4.2.6 L0s State", 519),
            (2, "Section 4.3 Lane Deskew", 540),
        ]
        sections = outline_entries_to_sections("base-7.0", entries, page_count=600)
        by_number = {section.section_number: section for section in sections}

        link_training = by_number["4.2"]
        self.assertEqual(link_training.page_start, 510)
        self.assertEqual(link_training.page_end, 539)

        polling = by_number["4.2.1"]
        self.assertEqual(polling.page_end, 518)

        l0s = by_number["4.2.6"]
        self.assertEqual(l0s.page_start, 519)
        self.assertEqual(l0s.page_end, 539)
        self.assertEqual(l0s.parent_id, "base-7.0:section:4.2")
        self.assertEqual(
            l0s.toc_path,
            ["Physical Layer Logical Block", "Link Training and Status State Machine", "L0s State"],
        )

        lane_deskew = by_number["4.3"]
        self.assertNotIn("L0s State", lane_deskew.toc_path)

    def test_appendix_prefix_gets_stable_number_and_title(self):
        entries = [
            (1, "Appendix A. Transaction Ordering", 700),
            (2, "Appendix A.1: Ordering Rules", 710),
        ]
        sections = outline_entries_to_sections("base-7.0", entries, page_count=720)
        by_number = {section.section_number: section for section in sections}

        self.assertEqual(by_number["A"].title, "Transaction Ordering")
        self.assertEqual(by_number["A.1"].title, "Ordering Rules")
        self.assertEqual(by_number["A.1"].parent_id, "base-7.0:section:A")

    def test_unnumbered_frontmatter_entries_are_skipped_intentionally(self):
        entries = [
            (1, "Revision History", 1),
            (1, "List of Figures", 5),
            (1, "Section 1.1 Scope", 20),
        ]
        sections = outline_entries_to_sections("base-7.0", entries, page_count=30)

        self.assertEqual([section.section_number for section in sections], ["1.1"])
        self.assertEqual(sections[0].title, "Scope")

    def test_span_dict_to_text_span_maps_bbox(self):
        span = span_dict_to_text_span(
            text="L0s",
            page=512,
            bbox=[72.0, 100.0, 100.0, 120.0],
            block=1,
            line=2,
            span=3,
        )
        self.assertEqual(span.text, "L0s")
        self.assertEqual(span.bbox, BBox(72.0, 100.0, 100.0, 120.0))

    def test_span_dict_to_text_span_rejects_invalid_bbox(self):
        cases = [
            ([1.0, 2.0, 3.0], "exactly 4"),
            ([1.0, 2.0, 3.0, 4.0, 5.0], "exactly 4"),
            ([1.0, "bad", 3.0, 4.0], "numeric"),
            ([1.0, 2.0, float("nan"), 4.0], "finite"),
            ([1.0, 2.0, float("inf"), 4.0], "finite"),
            ([5.0, 2.0, 4.0, 6.0], "not be reversed"),
            ([1.0, 8.0, 4.0, 6.0], "not be reversed"),
        ]
        for bbox, message in cases:
            with self.subTest(bbox=bbox):
                with self.assertRaisesRegex(ValueError, message):
                    span_dict_to_text_span("bad", 1, bbox, 0, 0, 0)

    def test_span_dict_to_text_span_allows_zero_area_bbox(self):
        span = span_dict_to_text_span("zero", 1, [10.0, 20.0, 10.0, 20.0], 0, 0, 0)

        self.assertEqual(span.bbox, BBox(10.0, 20.0, 10.0, 20.0))

    def test_extract_text_spans_uses_sort_skips_none_text_and_closes_doc(self):
        page = FakePage(
            {
                "blocks": [
                    {
                        "lines": [
                            {
                                "spans": [
                                    {"text": "  L0s  ", "bbox": [72.0, 100.0, 100.0, 120.0]},
                                    {"text": None, "bbox": [1.0, 2.0, 3.0, 4.0]},
                                    {"text": "   ", "bbox": [1.0, 2.0, 3.0, 4.0]},
                                ]
                            }
                        ]
                    }
                ]
            }
        )
        doc = FakeDoc([page])
        spans = FakeBackend(doc).extract_text_spans()

        self.assertTrue(doc.closed)
        self.assertEqual(page.calls, [("dict", {"sort": True})])
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].text, "L0s")
        self.assertEqual(spans[0].page, 1)
        self.assertEqual(spans[0].bbox, BBox(72.0, 100.0, 100.0, 120.0))

    def test_extract_text_spans_closes_doc_on_exception(self):
        doc = FakeDoc([FakePage(error=RuntimeError("boom"))])

        with self.assertRaisesRegex(RuntimeError, "boom"):
            FakeBackend(doc).extract_text_spans()

        self.assertTrue(doc.closed)


if __name__ == "__main__":
    unittest.main()
