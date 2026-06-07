# PCIe Parser Thread Summary - 2026-06-07

## Scope

This thread implemented and reviewed a deterministic PCIe Base Specification
parser for LLM-Wiki raw sources.

Source of truth:

- PCIe Base Spec PDF Table of Contents for sections.
- List of Figures, List of Tables, and List of Equations for canonical objects
  and listed page hints.
- Parser-generated raw source Markdown under
  `D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\sources\parsed\<version>\`.

Non-goals:

- No LLM participation in parser decisions.
- No manual edits to generated parsed output.
- No LLM-Wiki ingest or frontend changes.
- No generated `wiki/` content.

## Implemented Work

The branch `pcie-parser-subagent` now contains a deterministic parser under
`tools/pcie-parser/`.

Key capabilities:

- Parse PDF outline into one `pcie_section` Markdown file per TOC section.
- Extract object seeds from object lists and write one canonical `pcie_object`
  wrapper per figure, table, or equation.
- Keep section text and object content separated.
- Replace actual object occurrences in section Markdown with object links.
- Preserve pages, bboxes, hashes, object refs, and paragraph anchors.
- Write deterministic `manifest.jsonl`.
- Render figure/equation screenshots and table HTML assets when deterministic
  extraction succeeds.
- Mark unresolved assets as `resolved_no_asset` while still using deterministic
  source/removal bboxes to prevent object internals from leaking into sections.
- Provide integration templates and Source Watch guardrails.

## Important Commits

- `35423de` - add PyMuPDF backend.
- `7f34dcb` / `e7ad895` - add and harden CLI scaffold.
- `7d25669` / `1bd49f9` - localize objects and avoid caption-only assets.
- `6bdda22` / `fa1e67a` - render section bodies and bound them by headings.
- `a352b33` - handle split headings such as `V TX` / `T TX`.
- `58b326a`, `784614a`, `569f074` - add and harden integration templates and
  README guardrails.
- `34bf6cd` - preserve paragraph anchors and unresolved object separation.

## Final Verification

Final HEAD:

```text
34bf6cd fix: preserve PCIe anchors and unresolved object separation
```

Commands and results that were run during the final verification loop:

```powershell
$env:PYTHONPATH="D:\LLMWiki\repo\.worktrees\pcie-parser-subagent\tools\pcie-parser"
py -3 -m unittest discover tools\pcie-parser\tests -v
```

Result: `88` tests passed.

```powershell
py -3 tools\pcie-parser\parse_pcie_spec.py `
  --project D:\LLMWiki\PCIe-base-spec\PCIe-base-spec `
  --pdf D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\originals\NCB-PCI_Express_Base_7.0.pdf `
  --version base-7.0
```

Result: parser completed and wrote `1533` section files.

Manifest stability was checked across repeated regenerates.

Stable manifest SHA256:

```text
74A94EBC80D495734F061A56EE3EAF96D4A0E85305D802278F270B46591F5F5C
```

Generated output counts after final verification:

- Section files: `1533`
- Manifest lines: `3775`
- Object Markdown files: `1768`
- Sections with non-empty `paragraph_anchors`: `1428`

Spot checks:

- `sec-4.2.3.4.5-ecc-bytes-in-flit.md` contains the Figure 4-54 object link.
- Figure 4-54 internal table-like rows such as `00: ff 01: 00` are absent from
  the section Markdown.
- `sec-4.2.7.6.2.3-tx-l0s.fts.md` contains the Figure 4-72 object link.
- `Rx_L0s.Entry` is absent from the Figure 4-72 link section.

Final code review re-review approved the branch with no blocking issues.

## Generated Output Location

Current PCIe 7.0 parsed raw source output:

```text
D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\sources\parsed\base-7.0
```

## Ingest Guardrails

Before enabling LLM-Wiki Source Watch for this PCIe project:

- Treat parsed Markdown wrappers under `raw/sources/parsed/<version>/` as raw
  sources.
- Exclude canonical PDFs and generated non-Markdown assets such as PNG, HTML,
  and JSON from raw-source auto-ingest.
- Keep PDFs under `raw/originals/`.
- Keep object asset files available only as linked assets.
- Avoid ingesting object internals through section-derived pages unless the
  canonical object source is explicitly cited.

## Residual Notes

- Some objects remain `resolved_no_asset` when deterministic asset extraction
  cannot produce a safe image or table asset. They still have canonical object
  wrappers and source/removal bboxes to preserve section/object separation.
- Equation extraction remains screenshot-first; OCR/LaTeX conversion is a
  future enhancement.
