import unittest

from pcie_parser.models import BBox, ObjectRef, ParagraphAnchor, SectionNode, SourceObject
from pcie_parser.render import render_object_markdown, render_section_markdown
from pcie_parser.slug import content_hash


class RenderTests(unittest.TestCase):
    def test_section_frontmatter_contains_pcie_metadata_and_placeholder(self):
        section = SectionNode(
            spec_version="base-7.0",
            section_number="4.2.6",
            title="L0s State",
            level=3,
            page_start=512,
            page_end=518,
            toc_path=["Chapter 4", "4.2.6 L0s State"],
            parent_id="base-7.0:section:4.2",
            child_ids=[],
            slug="sec-4.2.6-l0s-state",
            body_markdown="The L0s state is entered after idle conditions.\n\n{{object:base-7.0:figure:4-72}}",
            object_refs=[
                ObjectRef(
                    object_id="base-7.0:figure:4-72",
                    path="../objects/figures/figure-4-72-l0s-substate-machine.md",
                    occurrence="actual",
                )
            ],
            paragraph_anchors=[
                ParagraphAnchor("p0001", 512, BBox(72.1, 130.5, 520.8, 188.2), "sha256:abc")
            ],
            content_hash=content_hash("The L0s state is entered after idle conditions."),
        )
        markdown = render_section_markdown(section, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        self.assertIn("type: pcie_section", markdown)
        self.assertIn("section_id: base-7.0:section:4.2.6", markdown)
        self.assertIn("[Figure 4-72](../objects/figures/figure-4-72-l0s-substate-machine.md)", markdown)
        self.assertNotIn("L0s Substate Machine internal text", markdown)

    def test_object_markdown_links_image_asset(self):
        obj = SourceObject(
            spec_version="base-7.0",
            object_type="figure",
            object_number="4-72",
            title="L0s Substate Machine",
            listed_page=515,
            page=515,
            bbox=BBox(72.0, 164.0, 540.0, 612.0),
            section_id="base-7.0:section:4.2.6",
            listed_in="List of Figures",
            slug="figure-4-72-l0s-substate-machine",
            asset_paths={"image": "figure-4-72-l0s-substate-machine.png"},
            caption_hash="sha256:caption",
            content_hash="sha256:content",
        )
        markdown = render_object_markdown(obj, source_pdf="NCB-PCI_Express_Base_7.0.pdf")
        self.assertIn("type: pcie_object", markdown)
        self.assertIn("object_id: base-7.0:figure:4-72", markdown)
        self.assertIn("![L0s Substate Machine](figure-4-72-l0s-substate-machine.png)", markdown)


if __name__ == "__main__":
    unittest.main()
