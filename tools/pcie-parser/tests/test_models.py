import unittest

from pcie_parser.models import BBox, ObjectRef, ParagraphAnchor, SectionNode, SourceObject


class ModelTests(unittest.TestCase):
    def test_section_id_uses_version_and_number(self):
        section = SectionNode(
            spec_version="base-7.0",
            section_number="4.2.6",
            title="L0s State",
            level=3,
            page_start=512,
            page_end=518,
            toc_path=["Chapter 4 Physical Layer Logical Block", "4.2.6 L0s State"],
            parent_id="base-7.0:section:4.2",
        )
        self.assertEqual(section.section_id, "base-7.0:section:4.2.6")

    def test_object_id_uses_version_type_and_number(self):
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
        )
        self.assertEqual(obj.object_id, "base-7.0:figure:4-72")

    def test_paragraph_anchor_keeps_page_bbox_and_hash(self):
        anchor = ParagraphAnchor(
            id="p0001",
            page=512,
            bbox=BBox(72.1, 130.5, 520.8, 188.2),
            hash="sha256:abc",
        )
        self.assertEqual(anchor.page, 512)
        self.assertEqual(anchor.bbox.as_list(), [72.1, 130.5, 520.8, 188.2])
        self.assertEqual(anchor.hash, "sha256:abc")

    def test_object_ref_records_occurrence_kind(self):
        ref = ObjectRef(
            object_id="base-7.0:figure:4-72",
            path="../objects/figures/figure-4-72-l0s-substate-machine.md",
            occurrence="actual",
        )
        self.assertEqual(ref.occurrence, "actual")

    def test_model_refs_are_exported_from_package(self):
        from pcie_parser import ObjectRef as ExportedObjectRef
        from pcie_parser import ParagraphAnchor as ExportedParagraphAnchor

        self.assertIs(ExportedObjectRef, ObjectRef)
        self.assertIs(ExportedParagraphAnchor, ParagraphAnchor)


if __name__ == "__main__":
    unittest.main()
