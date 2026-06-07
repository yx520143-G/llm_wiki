import unittest

from pcie_parser.bbox import bbox_contains, bbox_intersects, expand_bbox
from pcie_parser.models import BBox
from pcie_parser.slug import ascii_slug, content_hash, normalize_text, object_slug, section_slug


class SlugAndBBoxTests(unittest.TestCase):
    def assertPathSafeSlug(self, value):
        self.assertNotIn("/", value)
        self.assertNotIn("\\", value)
        self.assertNotIn(":", value)
        self.assertNotIn(" ", value)
        self.assertNotIn("..", value)
        self.assertNotEqual(value, ".")
        self.assertNotEqual(value, "..")

    def test_normalize_text_strips_blank_lines_and_collapses_whitespace(self):
        self.assertEqual(normalize_text("  Alpha   beta \r\n\r\n Gamma\tDelta \r"), "Alpha beta\nGamma Delta")

    def test_ascii_slug_normalizes_path_unsafe_text(self):
        self.assertEqual(ascii_slug("4.2.6"), "4.2.6")
        self.assertEqual(ascii_slug("../L0s\\Substate: Machine  "), "l0s-substate-machine")
        self.assertEqual(ascii_slug("../.."), "untitled")

    def test_section_slug_keeps_number_and_title(self):
        self.assertEqual(
            section_slug("4.2.6", "L0s State"),
            "sec-4.2.6-l0s-state",
        )

    def test_section_slug_normalizes_path_unsafe_components(self):
        slug = section_slug("../4/2:6  ", "L0s\\State: Entry")

        self.assertEqual(slug, "sec-4-2-6-l0s-state-entry")
        self.assertPathSafeSlug(slug)

    def test_object_slug_keeps_type_number_and_title(self):
        self.assertEqual(
            object_slug("figure", "4-72", "L0s Substate Machine"),
            "figure-4-72-l0s-substate-machine",
        )

    def test_object_slug_normalizes_path_unsafe_components(self):
        slug = object_slug("fig/ure", "..\\4:72  ", "L0s/Substate: Machine")

        self.assertEqual(slug, "fig-ure-4-72-l0s-substate-machine")
        self.assertPathSafeSlug(slug)

    def test_content_hash_normalizes_line_endings(self):
        self.assertEqual(content_hash("a\r\nb\n"), content_hash("a\nb\n"))

    def test_content_hash_uses_sha256_prefix_and_changes_with_content(self):
        first = content_hash("alpha")
        second = content_hash("beta")

        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(len(first), len("sha256:") + 64)
        self.assertNotEqual(first, second)

    def test_bbox_contains_inner_box(self):
        outer = BBox(10.0, 10.0, 100.0, 100.0)
        inner = BBox(12.0, 12.0, 20.0, 20.0)
        self.assertTrue(bbox_contains(outer, inner))

    def test_bbox_intersects_edges_are_not_inside(self):
        a = BBox(0.0, 0.0, 10.0, 10.0)
        b = BBox(10.0, 10.0, 20.0, 20.0)
        self.assertFalse(bbox_intersects(a, b))

    def test_bbox_intersects_zero_area_boxes_are_false(self):
        normal = BBox(0.0, 0.0, 10.0, 10.0)

        self.assertFalse(bbox_intersects(BBox(5.0, 0.0, 5.0, 10.0), normal))
        self.assertFalse(bbox_intersects(BBox(0.0, 5.0, 10.0, 5.0), normal))

    def test_expand_bbox_applies_configured_margin(self):
        box = BBox(10.0, 20.0, 30.0, 40.0)
        self.assertEqual(expand_bbox(box, vertical=36.0, horizontal=6.0).as_list(), [4.0, -16.0, 36.0, 76.0])


if __name__ == "__main__":
    unittest.main()
