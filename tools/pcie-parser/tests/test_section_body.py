import unittest

from pcie_parser.cli import build_section_span_boundaries, relative_object_path_from_section, select_section_body_spans
from pcie_parser.models import BBox, ObjectRef, SectionNode, SourceObject, TextSpan
from pcie_parser.render import render_section_body_markdown, render_section_markdown, spans_to_section_body
from pcie_parser.slug import content_hash


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


def make_section(section_number: str, title: str, level: int = 4, **overrides: object) -> SectionNode:
    values = {
        "spec_version": "base-7.0",
        "section_number": section_number,
        "title": title,
        "level": level,
        "page_start": 515,
        "page_end": 515,
        "toc_path": [title],
    }
    values.update(overrides)
    return SectionNode(**values)


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

    def test_section_body_spans_exclude_same_page_adjacent_sections(self):
        sections = [
            make_section("4.2.6.5", "Prior State"),
            make_section("4.2.6.6", "L0s Overview"),
            make_section("4.2.6.7", "Next State"),
        ]
        spans = [
            span("4.2.6.5 Prior State", line=0),
            span("prior body", line=1),
            span("4.2.6.6 L0s Overview", line=2),
            span("current body", line=3),
            span("Figure 4-72 belongs here", line=4),
            span("4.2.6.7 Next State", line=5),
            span("next body", line=6),
        ]

        boundaries = build_section_span_boundaries(sections, spans)
        body_spans = select_section_body_spans(sections[1], spans, boundaries)
        body = spans_to_section_body(body_spans, [])

        self.assertIn("4.2.6.6 L0s Overview", body)
        self.assertIn("current body", body)
        self.assertIn("Figure 4-72 belongs here", body)
        self.assertNotIn("4.2.6.5", body)
        self.assertNotIn("prior body", body)
        self.assertNotIn("4.2.6.7", body)
        self.assertNotIn("next body", body)

    def test_parent_section_stops_before_first_child_heading(self):
        parent = make_section("4.2.6", "L0s", level=3, page_end=516)
        child = make_section("4.2.6.1", "Entry", level=4, parent_id=parent.section_id, page_start=515, page_end=516)
        parent.child_ids = [child.section_id]
        sections = [parent, child]
        spans = [
            span("4.2.6 L0s", line=0),
            span("parent intro only", line=1),
            span("4.2.6.1 Entry", line=2),
            span("child body", line=3),
        ]

        boundaries = build_section_span_boundaries(sections, spans)
        body_spans = select_section_body_spans(parent, spans, boundaries)
        body = spans_to_section_body(body_spans, [])

        self.assertIn("4.2.6 L0s", body)
        self.assertIn("parent intro only", body)
        self.assertNotIn("4.2.6.1 Entry", body)
        self.assertNotIn("child body", body)

    def test_content_hash_matches_emitted_body_with_object_links(self):
        section = make_section("4.2.6.6", "L0s Overview")
        section.slug = "sec-4.2.6.6-l0s-overview"
        section.body_markdown = "See {{object:base-7.0:figure:4-72}}."
        section.object_refs = [
            ObjectRef(
                object_id="base-7.0:figure:4-72",
                path="../objects/figures/figure-4-72-l0s-substate-machine.md",
                occurrence="actual",
            )
        ]
        section.content_hash = content_hash(render_section_body_markdown(section))

        markdown = render_section_markdown(section, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        emitted_body = markdown.split("---\n\n", 1)[1]

        self.assertEqual(section.content_hash, content_hash(emitted_body))
        self.assertIn("[Figure 4-72](<../objects/figures/figure-4-72-l0s-substate-machine.md>)", emitted_body)


if __name__ == "__main__":
    unittest.main()
