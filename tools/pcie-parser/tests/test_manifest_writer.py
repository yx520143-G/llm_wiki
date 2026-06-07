import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pcie_parser.manifest import Manifest, object_record, section_record
from pcie_parser.models import SectionNode, SourceObject
from pcie_parser.writer import assert_inside_project, replace_output_dir


class ManifestWriterTests(unittest.TestCase):
    def test_manifest_writes_compact_sorted_utf8_jsonl(self):
        section = SectionNode(
            spec_version="base-7.0",
            section_number="4.2.6",
            title="L0s 状态",
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
            raw = path.read_bytes()
        self.assertEqual(len(lines), 1)
        self.assertEqual(
            lines[0],
            '{"content_hash":"sha256:abc","id":"base-7.0:section:4.2.6",'
            '"object_refs":[],"page_end":518,"page_start":512,'
            '"path":"sections/ch-04/sec-4.2.6-l0s-state.md",'
            '"record_type":"section","title":"L0s 状态"}',
        )
        self.assertIn("状态".encode("utf-8"), raw)
        self.assertNotIn(b"\\u72b6", raw)
        record = json.loads(lines[0])
        self.assertEqual(record["record_type"], "section")
        self.assertEqual(record["id"], "base-7.0:section:4.2.6")
        self.assertEqual(record["path"], "sections/ch-04/sec-4.2.6-l0s-state.md")

    def test_manifest_preserves_record_insertion_order(self):
        manifest = Manifest()
        manifest.add({"record_type": "second-sort-key", "id": "first"})
        manifest.add({"record_type": "first-sort-key", "id": "second"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.jsonl"
            manifest.write(path)
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines,
            [
                '{"id":"first","record_type":"second-sort-key"}',
                '{"id":"second","record_type":"first-sort-key"}',
            ],
        )
        self.assertEqual([json.loads(line)["id"] for line in lines], ["first", "second"])

    def test_object_record_snapshots_asset_paths(self):
        obj = SourceObject(
            spec_version="base-7.0",
            object_type="figure",
            object_number="4-1",
            title="Flow",
            listed_page=12,
            page=13,
            bbox=None,
            section_id="base-7.0:section:4.2.6",
            listed_in="figures",
            asset_paths={"image": "assets/figure-4-1.png"},
        )
        record = object_record(obj, "objects/figure-4-1.md")
        obj.asset_paths["image"] = "assets/mutated.png"
        obj.asset_paths["text"] = "assets/figure-4-1.txt"
        self.assertEqual(record["assets"], {"image": "assets/figure-4-1.png"})

    def test_assert_inside_project_allows_child_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            assert_inside_project(root, root / "out")

    def test_assert_inside_project_rejects_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "inside project root"):
                assert_inside_project(root, root)

    def test_assert_inside_project_rejects_sibling_prefix_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "project"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "inside project root"):
                assert_inside_project(root, parent / "project-other" / "out")

    def test_assert_inside_project_rejects_dotdot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "inside project root"):
                assert_inside_project(root, root / ".." / "out")

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

    def test_replace_output_dir_rejects_final_file_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final = root / "base-7.0"
            staged = root / "staged"
            final.write_text("final-file", encoding="utf-8")
            staged.mkdir()
            (staged / "new.txt").write_text("new", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Final output"):
                replace_output_dir(staged, final)
            self.assertTrue(staged.is_dir())
            self.assertEqual((staged / "new.txt").read_text(encoding="utf-8"), "new")
            self.assertTrue(final.is_file())
            self.assertEqual(final.read_text(encoding="utf-8"), "final-file")
            self.assertFalse((root / "base-7.0.bak").exists())

    def test_replace_output_dir_rejects_backup_file_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final = root / "base-7.0"
            staged = root / "staged"
            backup = root / "base-7.0.bak"
            final.mkdir()
            (final / "old.txt").write_text("old", encoding="utf-8")
            staged.mkdir()
            (staged / "new.txt").write_text("new", encoding="utf-8")
            backup.write_text("backup-file", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Backup output"):
                replace_output_dir(staged, final)
            self.assertEqual((final / "old.txt").read_text(encoding="utf-8"), "old")
            self.assertEqual((staged / "new.txt").read_text(encoding="utf-8"), "new")
            self.assertEqual(backup.read_text(encoding="utf-8"), "backup-file")

    def test_replace_output_dir_rolls_back_when_staged_rename_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final = root / "base-7.0"
            staged = root / "staged"
            backup = root / "base-7.0.bak"
            final.mkdir()
            (final / "old.txt").write_text("old", encoding="utf-8")
            staged.mkdir()
            (staged / "new.txt").write_text("new", encoding="utf-8")
            original_rename = type(staged).rename

            def fail_staged_rename(self, target):
                if self == staged:
                    raise OSError("staged rename failed")
                return original_rename(self, target)

            with mock.patch.object(type(staged), "rename", fail_staged_rename):
                with self.assertRaisesRegex(OSError, "staged rename failed"):
                    replace_output_dir(staged, final)
            self.assertEqual((final / "old.txt").read_text(encoding="utf-8"), "old")
            self.assertTrue(staged.is_dir())
            self.assertEqual((staged / "new.txt").read_text(encoding="utf-8"), "new")
            self.assertFalse(backup.exists())


if __name__ == "__main__":
    unittest.main()
