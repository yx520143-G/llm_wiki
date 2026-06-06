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

Run:

```powershell
cd D:\LLMWiki\repo
py -3 tools\pcie-parser\parse_pcie_spec.py `
  --project D:\LLMWiki\PCIe-base-spec\PCIe-base-spec `
  --pdf D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\originals\NCB-PCI_Express_Base_7.0.pdf `
  --version base-7.0
```
