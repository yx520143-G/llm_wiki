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

    def test_fallback_pages_use_listed_page_then_window_then_section_range(self):
        pages = fallback_pages(listed_page=100, section_start=95, section_end=110)
        self.assertEqual(pages[:5], [100, 98, 99, 101, 102])
        self.assertIn(95, pages)
        self.assertIn(110, pages)

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
        row_cell = TableCell("tCOH", 1, 1, 516, BBox(72.0, 160.0, 160.0, 180.0), "sha256:row")
        payload = table_json_payload(
            obj,
            headers=[[header]],
            rows=[[row_cell]],
            notes=[],
            source_html="table-4-14-l0s-timing-parameters.html",
        )
        self.assertEqual(payload["schema_version"], "pcie-table-json-0.1")
        self.assertEqual(payload["table_id"], "base-7.0:table:4-14")
        self.assertEqual(payload["page_start"], 515)
        self.assertEqual(payload["page_end"], 516)
        self.assertEqual(payload["headers"][0][0]["bbox"], [72.0, 160.0, 160.0, 180.0])


if __name__ == "__main__":
    unittest.main()
