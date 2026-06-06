import unittest

from pcie_parser.bbox import bbox_contains, bbox_intersects, expand_bbox
from pcie_parser.models import BBox
from pcie_parser.slug import content_hash, object_slug, section_slug


class SlugAndBBoxTests(unittest.TestCase):
    def test_section_slug_keeps_number_and_title(self):
        self.assertEqual(
            section_slug("4.2.6", "L0s State"),
            "sec-4.2.6-l0s-state",
        )

    def test_object_slug_keeps_type_number_and_title(self):
        self.assertEqual(
            object_slug("figure", "4-72", "L0s Substate Machine"),
            "figure-4-72-l0s-substate-machine",
        )

    def test_content_hash_normalizes_line_endings(self):
        self.assertEqual(content_hash("a\r\nb\n"), content_hash("a\nb\n"))

    def test_bbox_contains_uses_expanded_outer_box(self):
        outer = BBox(10.0, 10.0, 100.0, 100.0)
        inner = BBox(12.0, 12.0, 20.0, 20.0)
        self.assertTrue(bbox_contains(outer, inner))

    def test_bbox_intersects_edges_are_not_inside(self):
        a = BBox(0.0, 0.0, 10.0, 10.0)
        b = BBox(10.0, 10.0, 20.0, 20.0)
        self.assertFalse(bbox_intersects(a, b))

    def test_expand_bbox_applies_configured_margin(self):
        box = BBox(10.0, 20.0, 30.0, 40.0)
        self.assertEqual(expand_bbox(box, vertical=36.0, horizontal=6.0).as_list(), [4.0, -16.0, 36.0, 76.0])


if __name__ == "__main__":
    unittest.main()
