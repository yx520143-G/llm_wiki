# PCIe Base Spec Parser Design

Date: 2026-06-06
Status: Approved design, revised after external review, awaiting implementation plan

## Scope

Build a deterministic PCIe Base Spec parser as a repository tool under
`tools/pcie-parser/`. The parser reads PCIe Base Spec PDFs from an LLM Wiki
project's `raw/originals/` directory and writes normalized raw-source Markdown
under `raw/sources/parsed/<version>/`.

The parsed Markdown is the only source layer that LLM Wiki should ingest for
these specs. The original PDFs remain immutable provenance artifacts and should
not be ingested by LLM Wiki directly.

## Source Of Truth

- PDF outline / table of contents defines section boundaries.
- PDF List of Figures, List of Tables, and List of Equations seed the object
  registry with object number, title, and listed page.
- PyMuPDF is used as a layout provider for text spans, bounding boxes, images,
  drawings, and table-like regions.
- The parser, not PyMuPDF Markdown or pymupdf4llm Markdown, renders the final
  section and object Markdown.

## Non-Goals

- Do not call an LLM during parsing.
- Do not use pymupdf4llm Markdown as a source of truth.
- Do not write parser output into `wiki/`.
- Do not perform corpus-wide object deduplication in the first version.
- Do not OCR equations or produce LaTeX in the first version.
- Do not build embedding rerank or semantic retrieval in this parser phase.
- Do not generate a semantic version-diff corpus in the first version. The
  `base-7.0-vs-6.4` output is a parsed form of the official comparison PDF, not
  a parser-created section/object diff.

## Output Layout

The parser writes one version-local corpus per spec version:

```text
raw/sources/parsed/
  base-7.0/
    manifest.jsonl
    sections/
      ch-04-physical-layer-logical-block/
        sec-4.2.6-l0s-state.md
        sec-4.2.6.1-l0s-entry.md
    objects/
      figures/
        figure-4-72-l0s-substate-machine.md
        figure-4-72-l0s-substate-machine.png
      tables/
        table-4-14-l0s-timing-parameters.md
        table-4-14-l0s-timing-parameters.html
        table-4-14-l0s-timing-parameters.json
      equations/
        equation-4-3-replay-timer-limit.md
        equation-4-3-replay-timer-limit.png
  base-6.4/
  base-7.0-vs-6.4/
```

`base-7.0`, `base-6.4`, and `base-7.0-vs-6.4` are version boundaries and object
canonicalization boundaries. `base-7.0-vs-6.4` represents the official
comparison PDF (`CB-PCI_Express_Base_7.0-vs-6.4.pdf`) parsed as its own source
corpus. It does not require a `diff` manifest record type in v0.1.

## Section Contract

Each PDF outline entry produces one section Markdown file. Parent entries are
also emitted. A parent section file contains only its own intro text and child
links; it does not merge child section bodies.

Section Markdown contains:

- Section frontmatter.
- The section's own normalized text.
- Paragraph anchors with page, bbox, and hash metadata.
- Object placeholder links at actual object occurrence positions.
- Links to canonical object files for repeated references.

Section Markdown must not contain internal figure, table, or equation content.
Text spans inside registered object bounding boxes are subtracted before
section rendering.

Object placeholders and bbox subtraction follow these rules:

- Inline prose references such as "see Figure 4-72" remain in section text.
- Actual object occurrence locations get one placeholder link to the canonical
  object file.
- Figure/table/equation captions belong to the object, not to the section body.
- Table notes and figure footnotes belong to the object when they are adjacent
  to the object bbox and visually tied to the caption or object body.
- Bbox subtraction uses an object bbox expanded by a configurable caption and
  note margin. The default expansion is 36 pt vertically and 6 pt horizontally.
  The expansion may include captions and notes, but must not consume normal
  paragraphs that merely contain inline references.
- If a bbox overlaps unexpected section text, the object registry still wins:
  subtract the object spans from section text and emit a `parse_warning`.

Example section frontmatter:

```yaml
---
type: pcie_section
spec_version: base-7.0
source_pdf: NCB-PCI_Express_Base_7.0.pdf
section_id: base-7.0:section:4.2.6
section_number: "4.2.6"
section_title: "L0s State"
slug: sec-4.2.6-l0s-state
toc_path:
  - "Chapter 4 Physical Layer Logical Block"
  - "4.2 Link Training and Status State Machine"
  - "4.2.6 L0s State"
page_start: 512
page_end: 518
outline_level: 3
parent_section_id: base-7.0:section:4.2
child_section_ids: []
object_refs:
  - base-7.0:figure:4-72
paragraph_anchors:
  - id: p0001
    page: 512
    bbox: [72.1, 130.5, 520.8, 188.2]
    hash: sha256:example
content_hash: sha256:example
parser_version: pcie-parser-0.1
---
```

## Object Contract

Each figure, table, and equation has one canonical object file per spec version.
Repeated references in section text link to that canonical object file.

Object file names include both number and title slug:

- `figure-4-72-l0s-substate-machine.md`
- `table-4-14-l0s-timing-parameters.md`
- `equation-4-3-replay-timer-limit.md`

The stable ID does not depend on the title slug:

- `base-7.0:figure:4-72`
- `base-7.0:table:4-14`
- `base-7.0:equation:4-3`

Figure objects store a screenshot plus an object Markdown wrapper. Equation
objects store a screenshot plus an object Markdown wrapper. Table objects store
an object Markdown wrapper plus `html` and `json` assets when extraction
succeeds. If structured JSON cannot be produced, the parser keeps the HTML or a
screenshot fallback and writes a parse warning.

Object number extraction is deterministic:

- Figure numbers match `Figure <chapter>-<number>` or `Fig. <chapter>-<number>`.
- Table numbers match `Table <chapter>-<number>`.
- Equation numbers come from the List of Equations when present. If a listed
  equation has no explicit visible number, the parser assigns a stable
  section-local object number such as `4.2.6-e0001`.
- The original caption/title text is preserved in frontmatter even when the
  filename slug is normalized.

Example object frontmatter:

```yaml
---
type: pcie_object
spec_version: base-7.0
source_pdf: NCB-PCI_Express_Base_7.0.pdf
object_id: base-7.0:figure:4-72
object_type: figure
object_number: "4-72"
title: "L0s Substate Machine"
slug: figure-4-72-l0s-substate-machine
listed_page: 515
page: 515
section_id: base-7.0:section:4.2.6
bbox: [72.0, 164.0, 540.0, 612.0]
asset_paths:
  image: figure-4-72-l0s-substate-machine.png
caption_hash: sha256:example
content_hash: sha256:example
listed_in: "List of Figures"
parser_version: pcie-parser-0.1
---
```

## Manifest Contract

`manifest.jsonl` is a first-class output. Tools should prefer reading the
manifest instead of scanning Markdown bodies.

Record types:

- `document`
- `section`
- `object`
- `asset`
- `parse_warning`

Example section record:

```json
{"record_type":"section","id":"base-7.0:section:4.2.6","path":"sections/ch-04-physical-layer-logical-block/sec-4.2.6-l0s-state.md","title":"L0s State","page_start":512,"page_end":518,"object_refs":["base-7.0:figure:4-72"],"content_hash":"sha256:example"}
```

Object records include `object_type`, `object_number`, `title`, `path`, `assets`,
`page`, `bbox`, `section_id`, and stable hashes. Warning records include
`severity`, `code`, `message`, and the related `page`, `section_id`, or
`object_id`.

Table JSON uses this minimum schema. It must preserve merged cells and source
locations; consumers should treat it as structured extraction output rather
than a normalized relational table:

```json
{
  "schema_version": "pcie-table-json-0.1",
  "table_id": "base-7.0:table:4-14",
  "caption": "L0s Timing Parameters",
  "page_start": 515,
  "page_end": 516,
  "bbox": [72.0, 160.0, 540.0, 620.0],
  "headers": [
    [
      {"text": "Parameter", "rowspan": 1, "colspan": 1, "page": 515, "bbox": [72.0, 160.0, 160.0, 180.0], "hash": "sha256:example"}
    ]
  ],
  "rows": [
    [
      {"text": "tCOH", "rowspan": 1, "colspan": 1, "page": 515, "bbox": [72.0, 182.0, 160.0, 202.0], "hash": "sha256:example"}
    ]
  ],
  "notes": [
    {"text": "Note 1: example", "page": 516, "bbox": [72.0, 600.0, 540.0, 620.0], "hash": "sha256:example"}
  ],
  "source_html": "table-4-14-l0s-timing-parameters.html"
}
```

## Parser Pipeline

1. Discover documents from configured PDF paths and version mappings. Compute
   PDF file hashes and emit document records.
2. Extract PDF outline entries and build a section tree.
3. Extract List of Figures, List of Tables, and List of Equations into a
   version-local object seed registry.
4. Extract layout spans, bboxes, images, drawings, and table-like regions with
   PyMuPDF.
5. Localize objects using the object registry:
   - Search the listed page first.
   - If not found, search `listed_page - 2` through `listed_page + 2`.
   - If still not found, search only the page range of the section associated
     with the object list entry or nearest outline context.
   - If still not found, emit an unresolved-object warning and do not perform
     unrestricted whole-document guessing.
6. Render object assets and object Markdown wrappers.
7. Render section Markdown after subtracting registered object bboxes from the
   section text span set.
8. Emit manifest records and stability hashes.

## Error Handling

Hard failures:

- PDF cannot be opened.
- PDF outline is absent or unusable.
- Output path escapes the target project.
- Version mapping is missing for an input PDF.

Recoverable warnings:

- A section has no body text.
- An object registry entry cannot be localized to a bbox.
- A table cannot be converted to structured JSON.
- An object spans multiple pages and cannot be merged cleanly.
- A slug collision requires a stable hash suffix.
- An object bbox overlaps an unexpected section range.
- An object is listed on one page but localized on a nearby fallback page.

Recoverable warnings are emitted as `parse_warning` manifest records. The parser
should keep producing the rest of the corpus.

## Determinism Rules

- IDs derive from `spec_version`, record type, section number, and object number.
- Slugs derive from normalized titles and receive stable hash suffixes only on
  collision.
- Content hashes derive from normalized text, normalized HTML/JSON, and image
  bytes.
- Manifest output order is deterministic: document records, sections by outline
  order, objects by type and number, assets, warnings.
- The parser writes to a temporary output directory and replaces the version
  output only after a successful run. On Windows, directory replacement should
  be implemented as a guarded swap with backup cleanup because `os.replace`
  cannot atomically replace a non-empty directory in the same way on every
  platform.
- The parser does not read network resources and does not invoke LLMs.

## LLM Wiki Integration

LLM Wiki should ingest parsed Markdown, not the PDFs. Parser frontmatter types
such as `pcie_section` and `pcie_object` describe raw-source records. They do
not have to match generated wiki page types directly.

Before ingesting parsed PCIe sources, update the PCIe project `purpose.md` and
`schema.md` away from the current reading-template language. The schema should
tell LLM Wiki that raw sources may be `pcie_section` and `pcie_object` records,
and that generated wiki pages should be protocol-analysis pages such as
concepts, mechanisms, packet formats, state machines, registers, fields,
queries, and comparisons.

Recommended Source Watch settings for this project:

- Include only Markdown wrapper files for automatic ingest.
- Exclude PDF, PNG, HTML, and JSON assets from automatic ingest.
- Keep original PDFs in `raw/originals/`.
- Keep parsed Markdown under `raw/sources/parsed/<version>/`.

Agents and future tooling can read table HTML/JSON and screenshots directly by
following links from object Markdown or `manifest.jsonl`. LLM Wiki should not
ingest those assets as standalone source files.

Before enabling this parser workflow, cancel or clear existing PDF ingest tasks
for the PCIe project so the default PDF pipeline does not generate competing
source summaries.

## Verification Commands

Generate one version:

```powershell
cd D:\LLMWiki\repo
python tools\pcie-parser\parse_pcie_spec.py `
  --project D:\LLMWiki\PCIe-base-spec\PCIe-base-spec `
  --pdf D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\originals\NCB-PCI_Express_Base_7.0.pdf `
  --version base-7.0
```

Check deterministic manifest output:

```powershell
python tools\pcie-parser\parse_pcie_spec.py ... --version base-7.0
Copy-Item D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\sources\parsed\base-7.0\manifest.jsonl $env:TEMP\manifest-1.jsonl
python tools\pcie-parser\parse_pcie_spec.py ... --version base-7.0
Compare-Object `
  (Get-Content $env:TEMP\manifest-1.jsonl) `
  (Get-Content D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\sources\parsed\base-7.0\manifest.jsonl)
```

Spot-check object text subtraction:

```powershell
rg -n "L0s Substate Machine|Figure 4-72" D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\sources\parsed\base-7.0\sections
rg -n "L0s Substate Machine" D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\sources\parsed\base-7.0\objects
```

If `rg` is unavailable, use PowerShell:

```powershell
Get-ChildItem D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\sources\parsed\base-7.0\sections -Recurse -File |
  Select-String -Pattern "L0s Substate Machine|Figure 4-72"
Get-ChildItem D:\LLMWiki\PCIe-base-spec\PCIe-base-spec\raw\sources\parsed\base-7.0\objects -Recurse -File |
  Select-String -Pattern "L0s Substate Machine"
```

Expected result: section files contain only placeholder or link text for the
registered object; object files contain the canonical wrapper and asset links.

If LLM Wiki source watch or ingest behavior is changed during implementation,
run focused frontend tests around `source-watch-config`, `project-file-sync`, and
`ingest` in addition to the parser tests.
