import unittest
from pathlib import Path


class IntegrationDocsTests(unittest.TestCase):
    def test_templates_describe_protocol_qa_not_reading_template(self):
        root = Path(__file__).resolve().parents[1]
        purpose = (root / "templates" / "pcie-purpose.md").read_text(encoding="utf-8")
        schema = (root / "templates" / "pcie-schema.md").read_text(encoding="utf-8")
        self.assertIn("PCIe Base Specification", purpose)
        self.assertIn("pcie_section", schema)
        self.assertIn("pcie_object", schema)
        self.assertIn("protocol-analysis", schema)


if __name__ == "__main__":
    unittest.main()
