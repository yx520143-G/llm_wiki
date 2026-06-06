import unittest
from pathlib import Path


class IntegrationDocsTests(unittest.TestCase):
    def test_templates_describe_protocol_qa_not_reading_template(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        purpose = (root / "templates" / "pcie-purpose.md").read_text(encoding="utf-8")
        schema = (root / "templates" / "pcie-schema.md").read_text(encoding="utf-8")
        combined = f"{readme}\n{schema}"
        readme_one_line = " ".join(readme.split())

        self.assertIn("cd <llm-wiki-repo-root>", readme)
        self.assertIn("py -3", readme)
        self.assertNotIn(r"python tools\pcie-parser", readme)

        self.assertIn("Source Watch", readme)
        self.assertIn("*.md", readme)
        self.assertIn("*.png", readme)
        self.assertIn("*.html", readme)
        self.assertIn("*.json", readme)
        self.assertIn("PDFs", readme)
        self.assertIn("raw-source auto-ingest", readme)
        self.assertIn("raw/originals/", readme)
        self.assertIn("PDF ingest tasks", readme)
        self.assertIn("linked asset files are not raw sources", readme_one_line)

        self.assertIn("PCIe Base Specification", purpose)
        self.assertIn("Treating LLM-generated summaries as raw source", purpose)

        self.assertIn("Raw Source Types", schema)
        self.assertIn("Generated Wiki Page Types", schema)
        self.assertIn("They are not generated wiki page types", schema)
        self.assertIn("pcie_section", schema)
        self.assertIn("pcie_object", schema)
        self.assertIn("protocol-analysis", schema)
        self.assertIn("Section Markdown may link", combined)
        self.assertIn("pcie_object", combined)
        self.assertIn("assets", combined)
        self.assertIn("Do not copy figure/table/equation internals", schema)
        self.assertIn("unless the object source is explicitly cited", schema)


if __name__ == "__main__":
    unittest.main()
