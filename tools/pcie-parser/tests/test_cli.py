import tempfile
import unittest
from pathlib import Path

from pcie_parser.cli import parse_args, version_output_dir


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


if __name__ == "__main__":
    unittest.main()
