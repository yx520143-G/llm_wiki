# PCIe Parser

This tool parses PCIe Base Spec PDFs into LLM-Wiki raw sources.

Input PDFs stay in:

```text
<project>/raw/originals/
```

Parsed Markdown is written to:

```text
<project>/raw/sources/parsed/<version>/
```

Before running LLM-Wiki ingest, copy the templates in `templates/` to the PCIe
project's `purpose.md` and `schema.md` or manually align those files with the
same protocol QA rules.

## Source Watch and Ingest Guardrails

When enabling LLM-Wiki Source Watch for a PCIe project:

- Ingest only parsed Markdown wrapper files (`*.md`) under
  `raw/sources/parsed/<version>/` as raw sources.
- Exclude PDFs and generated non-Markdown assets such as `*.png`, `*.html`, and
  `*.json` from Source Watch and raw-source auto-ingest.
- Keep canonical PDF inputs under `raw/originals/`.
- Clear or avoid existing PDF ingest tasks before enabling this parsed-Markdown
  workflow, so the original PDFs are not treated as raw sources.
- Keep object asset files available as linked assets. Section Markdown may link
  to `pcie_object` wrappers and their assets, but linked asset files are not raw
  sources.

Run:

```powershell
cd <llm-wiki-repo-root>
py -3 tools\pcie-parser\parse_pcie_spec.py `
  --project D:\LLMWiki\PCIe-base-spec\PCIe-base-spec `
  --pdf D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\originals\NCB-PCI_Express_Base_7.0.pdf `
  --version base-7.0
```
