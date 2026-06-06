import json
import tempfile
import unittest
from pathlib import Path

from pcie_parser.manifest import Manifest, section_record
from pcie_parser.models import SectionNode
from pcie_parser.writer import replace_output_dir


class ManifestWriterTests(unittest.TestCase):
    def test_manifest_writes_jsonl_in_insert_order(self):
        section = SectionNode(
            spec_version="base-7.0",
            section_number="4.2.6",
            title="L0s State",
            level=3,
            page_start=512,
            page_end=518,
            toc_path=["Chapter 4", "4.2.6 L0s State"],
            slug="sec-4.2.6-l0s-state",
            content_hash="sha256:abc",
        )
        manifest = Manifest()
        manifest.add(section_record(section, "sections/ch-04/sec-4.2.6-l0s-state.md"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.jsonl"
            manifest.write(path)
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["record_type"], "section")
        self.assertEqual(record["id"], "base-7.0:section:4.2.6")
        self.assertEqual(record["path"], "sections/ch-04/sec-4.2.6-l0s-state.md")

    def test_replace_output_dir_replaces_existing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final = root / "base-7.0"
            staged = root / "staged"
            final.mkdir()
            (final / "old.txt").write_text("old", encoding="utf-8")
            staged.mkdir()
            (staged / "new.txt").write_text("new", encoding="utf-8")
            replace_output_dir(staged, final)
            self.assertFalse((final / "old.txt").exists())
            self.assertEqual((final / "new.txt").read_text(encoding="utf-8"), "new")


if __name__ == "__main__":
    unittest.main()
