import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pcie_parser.cli import main, parse_args, validate_version, version_output_dir
from pcie_parser.slug import content_hash


def make_temp_project(test_case: unittest.TestCase) -> tuple[Path, Path]:
    tmp = tempfile.TemporaryDirectory()
    test_case.addCleanup(tmp.cleanup)
    project_root = Path(tmp.name) / "project"
    originals_dir = project_root / "raw" / "originals"
    originals_dir.mkdir(parents=True)
    pdf_path = originals_dir / "spec.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    return project_root, pdf_path


def main_args(project_root: Path, pdf_path: Path, version: str = "base-7.0") -> list[str]:
    return [
        "--project",
        str(project_root),
        "--pdf",
        str(pdf_path),
        "--version",
        version,
    ]


def write_existing_final(project_root: Path, version: str = "base-7.0") -> Path:
    final_dir = version_output_dir(project_root, version)
    final_dir.mkdir(parents=True)
    (final_dir / "old.txt").write_text("old", encoding="utf-8")
    return final_dir


class CliTests(unittest.TestCase):
    def test_parse_args_accepts_project_pdf_and_version(self):
        args = parse_args(
            [
                "--project",
                r"D:\LLMWiki\PCIe-base-spec\PCIe-base-spec",
                "--pdf",
                r"D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\originals\NCB-PCI_Express_Base_7.0.pdf",
                "--version",
                "base-7.0",
            ]
        )
        self.assertEqual(args.version, "base-7.0")

    def test_version_output_dir_is_raw_sources_parsed_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                version_output_dir(root, "base-7.0"),
                root / "raw" / "sources" / "parsed" / "base-7.0",
            )

    def test_validate_version_accepts_practical_version_names(self):
        for version in ("base-7.0", "base-6.4", "base-7.0-vs-6.4"):
            with self.subTest(version=version):
                self.assertEqual(validate_version(version), version)

    def test_main_writes_sections_and_manifest(self):
        project_root, pdf_path = make_temp_project(self)
        outline_entries = [(1, "Section 1. Scope", 1)]

        with mock.patch("pcie_parser.cli.PdfBackend") as backend_class:
            backend_class.return_value.extract_outline.return_value = (outline_entries, 10)

            result = main(main_args(project_root, pdf_path))

        self.assertEqual(result, 0)
        backend_class.assert_called_once_with(pdf_path.resolve())
        final_dir = version_output_dir(project_root, "base-7.0")
        section_path = final_dir / "sections" / "sec-1-scope.md"
        manifest_path = final_dir / "manifest.jsonl"
        self.assertTrue(section_path.is_file())
        self.assertTrue(manifest_path.is_file())

        manifest_lines = manifest_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(manifest_lines), 1)
        record = json.loads(manifest_lines[0])
        self.assertEqual(record["record_type"], "section")
        self.assertEqual(record["id"], "base-7.0:section:1")
        self.assertEqual(record["path"], "sections/sec-1-scope.md")
        self.assertEqual(record["content_hash"], content_hash(""))

    def test_main_rejects_invalid_version_before_output_mutation(self):
        invalid_versions = ["", " ", ".", "..", "../base-7.0", r"base\7.0", str(Path.cwd())]

        for version in invalid_versions:
            with self.subTest(version=version):
                project_root, pdf_path = make_temp_project(self)
                parsed_root = project_root / "raw" / "sources" / "parsed"
                parsed_root.mkdir(parents=True)
                sentinel = parsed_root / "keep.txt"
                sentinel.write_text("keep", encoding="utf-8")

                with mock.patch("pcie_parser.cli.PdfBackend") as backend_class:
                    with self.assertRaisesRegex(SystemExit, "Version"):
                        main(main_args(project_root, pdf_path, version))

                backend_class.assert_not_called()
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
                self.assertEqual([path.name for path in parsed_root.iterdir()], ["keep.txt"])

    def test_main_rejects_missing_project(self):
        project_root, pdf_path = make_temp_project(self)
        missing_project = project_root.parent / "missing"

        with mock.patch("pcie_parser.cli.PdfBackend") as backend_class:
            with self.assertRaisesRegex(SystemExit, "Project root"):
                main(main_args(missing_project, pdf_path))

        backend_class.assert_not_called()

    def test_main_rejects_pdf_outside_raw_originals(self):
        project_root, _pdf_path = make_temp_project(self)
        outside_pdf = project_root.parent / "outside.pdf"
        outside_pdf.write_bytes(b"%PDF-1.4\n")

        with mock.patch("pcie_parser.cli.PdfBackend") as backend_class:
            with self.assertRaisesRegex(SystemExit, "raw/originals"):
                main(main_args(project_root, outside_pdf))

        backend_class.assert_not_called()

    def test_main_rejects_absent_outline_and_leaves_final_output_untouched(self):
        project_root, pdf_path = make_temp_project(self)
        final_dir = write_existing_final(project_root)

        with mock.patch("pcie_parser.cli.PdfBackend") as backend_class:
            backend_class.return_value.extract_outline.return_value = ([], 10)
            with self.assertRaisesRegex(SystemExit, "outline"):
                main(main_args(project_root, pdf_path))

        self.assertEqual((final_dir / "old.txt").read_text(encoding="utf-8"), "old")
        self.assertFalse((final_dir / "manifest.jsonl").exists())
        self.assert_no_staged_dirs(project_root)

    def test_main_rejects_empty_sections_and_leaves_final_output_untouched(self):
        project_root, pdf_path = make_temp_project(self)
        final_dir = write_existing_final(project_root)

        with mock.patch("pcie_parser.cli.PdfBackend") as backend_class:
            backend_class.return_value.extract_outline.return_value = ([(1, "Revision History", 1)], 10)
            with mock.patch("pcie_parser.cli.outline_entries_to_sections", return_value=[]):
                with self.assertRaisesRegex(SystemExit, "no numbered sections"):
                    main(main_args(project_root, pdf_path))

        self.assertEqual((final_dir / "old.txt").read_text(encoding="utf-8"), "old")
        self.assertFalse((final_dir / "manifest.jsonl").exists())
        self.assert_no_staged_dirs(project_root)

    def test_main_rejects_duplicate_slug_and_leaves_final_output_untouched(self):
        project_root, pdf_path = make_temp_project(self)
        final_dir = write_existing_final(project_root)
        outline_entries = [
            (1, "Section 1. Scope", 1),
            (1, "Section 1. Scope", 2),
        ]

        with mock.patch("pcie_parser.cli.PdfBackend") as backend_class:
            backend_class.return_value.extract_outline.return_value = (outline_entries, 10)
            with self.assertRaisesRegex(SystemExit, "Duplicate section slug"):
                main(main_args(project_root, pdf_path))

        self.assertEqual((final_dir / "old.txt").read_text(encoding="utf-8"), "old")
        self.assertFalse((final_dir / "sections" / "sec-1-scope.md").exists())
        self.assert_no_staged_dirs(project_root)

    def test_main_cleans_staging_dir_after_failure(self):
        project_root, pdf_path = make_temp_project(self)
        outline_entries = [
            (1, "Section 1. Scope", 1),
            (1, "Section 1. Scope", 2),
        ]

        with mock.patch("pcie_parser.cli.PdfBackend") as backend_class:
            backend_class.return_value.extract_outline.return_value = (outline_entries, 10)
            with self.assertRaisesRegex(SystemExit, "Duplicate section slug"):
                main(main_args(project_root, pdf_path))

        self.assert_no_staged_dirs(project_root)

    def assert_no_staged_dirs(self, project_root: Path) -> None:
        parsed_root = project_root / "raw" / "sources" / "parsed"
        if not parsed_root.exists():
            return
        staged_dirs = list(parsed_root.glob(".base-7.0.*.staged"))
        self.assertEqual(staged_dirs, [])


if __name__ == "__main__":
    unittest.main()
