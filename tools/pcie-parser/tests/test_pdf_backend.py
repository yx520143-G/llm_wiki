import unittest

from pcie_parser.models import BBox
from pcie_parser.pdf_backend import outline_entries_to_sections, span_dict_to_text_span


class PdfBackendTests(unittest.TestCase):
    def test_outline_entries_to_sections_sets_page_end_from_next_entry(self):
        entries = [
            (1, "Chapter 4 Physical Layer Logical Block", 500),
            (2, "4.2 Link Training and Status State Machine", 510),
            (3, "4.2.6 L0s State", 512),
            (3, "4.2.7 Recovery", 519),
        ]
        sections = outline_entries_to_sections("base-7.0", entries, page_count=600)
        l0s = [section for section in sections if section.section_number == "4.2.6"][0]
        self.assertEqual(l0s.page_start, 512)
        self.assertEqual(l0s.page_end, 518)
        self.assertEqual(l0s.parent_id, "base-7.0:section:4.2")
        self.assertEqual(l0s.toc_path, ["Physical Layer Logical Block", "Link Training and Status State Machine", "L0s State"])
        recovery = [section for section in sections if section.section_number == "4.2.7"][0]
        self.assertNotIn("L0s State", recovery.toc_path)

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


if __name__ == "__main__":
    unittest.main()
