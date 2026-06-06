import unittest

from pcie_parser.cli import relative_object_path_from_section
from pcie_parser.models import BBox, SourceObject, TextSpan
from pcie_parser.render import spans_to_section_body


def span(
    text: str,
    page: int = 515,
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
        "listed_page": 515,
        "page": 515,
        "bbox": BBox(90.0, 160.0, 300.0, 220.0),
        "section_id": "base-7.0:section:4.2.6",
        "listed_in": "List of Figures",
        "slug": "figure-4-72-l0s-substate-machine",
    }
    values.update(overrides)
    return SourceObject(**values)


class SectionBodyTests(unittest.TestCase):
    def test_spans_inside_object_bbox_are_removed_and_placeholder_keeps_surrounding_text(self):
        spans = [
            span("The L0s state is entered after idle conditions.", bbox=BBox(72.0, 100.0, 420.0, 120.0)),
            span("See Figure 4-72 for the state machine.", bbox=BBox(72.0, 130.0, 410.0, 150.0), line=1),
            span("Rx_L0s.Entry", bbox=BBox(110.0, 170.0, 180.0, 185.0), block=1, line=0),
            span("Tx_L0s.Idle", bbox=BBox(190.0, 190.0, 260.0, 205.0), block=1, line=1),
            span("Text after the figure remains.", bbox=BBox(72.0, 260.0, 300.0, 280.0), block=2),
        ]

        body = spans_to_section_body(spans, [make_object()])

        self.assertIn("The L0s state is entered after idle conditions.", body)
        self.assertIn("See Figure 4-72 for the state machine.", body)
        self.assertIn("Text after the figure remains.", body)
        self.assertIn("{{object:base-7.0:figure:4-72}}", body)
        self.assertNotIn("Rx_L0s.Entry", body)
        self.assertNotIn("Tx_L0s.Idle", body)

    def test_placeholder_is_deduplicated_when_multiple_spans_fall_inside_one_object(self):
        spans = [
            span("Before", bbox=BBox(72.0, 100.0, 120.0, 120.0)),
            span("Rx_L0s.Entry", bbox=BBox(110.0, 170.0, 180.0, 185.0), block=1, line=0),
            span("Rx_L0s.Idle", bbox=BBox(115.0, 190.0, 185.0, 205.0), block=1, line=1),
            span("After", bbox=BBox(72.0, 260.0, 120.0, 280.0), block=2),
        ]

        body = spans_to_section_body(spans, [make_object()])

        self.assertEqual(body.count("{{object:base-7.0:figure:4-72}}"), 1)

    def test_spans_outside_object_bbox_on_same_page_remain(self):
        spans = [
            span("Left margin note survives.", bbox=BBox(20.0, 170.0, 70.0, 185.0)),
            span("Rx_L0s.Entry", bbox=BBox(110.0, 170.0, 180.0, 185.0), span_index=1),
            span("Right paragraph survives.", bbox=BBox(320.0, 170.0, 500.0, 185.0), span_index=2),
        ]

        body = spans_to_section_body(spans, [make_object()])

        self.assertIn("Left margin note survives.", body)
        self.assertIn("Right paragraph survives.", body)
        self.assertNotIn("Rx_L0s.Entry", body)

    def test_relative_object_path_from_section_uses_parent_and_forward_slashes(self):
        self.assertEqual(
            relative_object_path_from_section(r"objects\figures\figure-4-72-l0s-substate-machine.md"),
            "../objects/figures/figure-4-72-l0s-substate-machine.md",
        )


if __name__ == "__main__":
    unittest.main()
