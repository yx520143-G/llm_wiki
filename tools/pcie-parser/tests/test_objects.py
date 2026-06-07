import unittest

from pcie_parser.models import BBox, SourceObject, TableCell
from pcie_parser.objects import (
    fallback_pages,
    parse_object_heading,
    table_json_payload,
)


class ObjectRuleTests(unittest.TestCase):
    def test_parse_figure_heading(self):
        parsed = parse_object_heading("Figure 4-72 L0s Substate Machine")
        self.assertEqual(parsed, ("figure", "4-72", "L0s Substate Machine"))

    def test_parse_table_heading(self):
        parsed = parse_object_heading("Table 4-14 L0s Timing Parameters")
        self.assertEqual(parsed, ("table", "4-14", "L0s Timing Parameters"))

    def test_parse_common_list_entry_object_headings(self):
        self.assertEqual(
            parse_object_heading("  fIg.\t4-72   L0s   Substate\nMachine  "),
            ("figure", "4-72", "L0s Substate Machine"),
        )
        self.assertEqual(
            parse_object_heading("Equation 4-1 Title"),
            ("equation", "4-1", "Title"),
        )
        self.assertEqual(
            parse_object_heading("Equation (4-1) Title"),
            ("equation", "4-1", "Title"),
        )
        self.assertEqual(
            parse_object_heading("Table 4-14: L0s Timing Parameters .... 515"),
            ("table", "4-14", "L0s Timing Parameters"),
        )
        self.assertEqual(
            parse_object_heading("Table 4-14. L0s Timing Parameters ... 515"),
            ("table", "4-14", "L0s Timing Parameters"),
        )
        self.assertIsNone(parse_object_heading("This is not an object heading"))

    def test_fallback_pages_use_listed_page_then_window_then_section_range(self):
        pages = fallback_pages(listed_page=100, section_start=95, section_end=110)
        self.assertEqual(pages[:5], [100, 98, 99, 101, 102])
        self.assertIn(95, pages)
        self.assertIn(110, pages)

    def test_fallback_pages_omit_nonpositive_listed_page(self):
        pages = fallback_pages(listed_page=0, section_start=None, section_end=None)
        self.assertEqual(pages, [1, 2])

    def test_fallback_pages_omit_nonpositive_section_pages(self):
        pages = fallback_pages(listed_page=2, section_start=-2, section_end=3)
        self.assertNotIn(0, pages)
        self.assertNotIn(-1, pages)
        self.assertNotIn(-2, pages)
        self.assertEqual(pages, [2, 1, 3, 4])

    def test_fallback_pages_remove_overlapping_window_and_section_duplicates(self):
        pages = fallback_pages(listed_page=5, section_start=4, section_end=7)
        self.assertEqual(pages, [5, 3, 4, 6, 7])

    def test_table_json_payload_preserves_cell_bbox_hash_and_html_link(self):
        obj = SourceObject(
            spec_version="base-7.0",
            object_type="table",
            object_number="4-14",
            title="L0s Timing Parameters",
            listed_page=515,
            page=515,
            bbox=BBox(72.0, 160.0, 540.0, 620.0),
            section_id="base-7.0:section:4.2.6",
            listed_in="List of Tables",
        )
        header = TableCell("Parameter", 1, 1, 515, BBox(72.0, 160.0, 160.0, 180.0), "sha256:header")
        row_cell = TableCell("tCOH", 2, 3, 516, BBox(72.0, 181.0, 160.0, 204.0), "sha256:row")
        note = TableCell("Values are implementation specific.", 1, 1, 516, BBox(72.0, 580.0, 540.0, 600.0), "sha256:note")
        headers = [[header]]
        rows = [[row_cell]]
        notes = [note]
        payload = table_json_payload(
            obj,
            headers=headers,
            rows=rows,
            notes=notes,
            source_html="table-4-14-l0s-timing-parameters.html",
        )
        headers.append([TableCell("Mutated", 1, 1, 999, BBox(1.0, 2.0, 3.0, 4.0), "sha256:mutated-header")])
        rows[0][0] = TableCell("Mutated", 1, 1, 999, BBox(1.0, 2.0, 3.0, 4.0), "sha256:mutated-row")
        notes.clear()

        self.assertEqual(payload["schema_version"], "pcie-table-json-0.1")
        self.assertEqual(payload["table_id"], "base-7.0:table:4-14")
        self.assertEqual(payload["caption"], "L0s Timing Parameters")
        self.assertEqual(payload["page_start"], 515)
        self.assertEqual(payload["page_end"], 516)
        self.assertEqual(payload["bbox"], [72.0, 160.0, 540.0, 620.0])
        self.assertEqual(payload["source_html"], "table-4-14-l0s-timing-parameters.html")
        self.assertEqual(payload["headers"][0][0]["bbox"], [72.0, 160.0, 160.0, 180.0])
        self.assertEqual(len(payload["headers"]), 1)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0][0]["hash"], "sha256:row")
        self.assertEqual(payload["rows"][0][0]["page"], 516)
        self.assertEqual(payload["rows"][0][0]["rowspan"], 2)
        self.assertEqual(payload["rows"][0][0]["colspan"], 3)
        self.assertEqual(
            payload["notes"],
            [
                {
                    "text": "Values are implementation specific.",
                    "rowspan": 1,
                    "colspan": 1,
                    "page": 516,
                    "bbox": [72.0, 580.0, 540.0, 600.0],
                    "hash": "sha256:note",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
