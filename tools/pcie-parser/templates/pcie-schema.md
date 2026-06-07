# Wiki Schema - PCIe Protocol QA

## Raw Source Types

Parsed raw sources under `raw/sources/parsed/<version>/` may use:

- `pcie_section`: one PDF table-of-contents entry rendered as source Markdown.
- `pcie_object`: one canonical figure, table, or equation object wrapper.

These are raw-source records. They are not generated wiki page types.

## Generated Wiki Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| concept | wiki/concepts/ | Protocol concepts and mechanisms |
| entity | wiki/entities/ | Named packets, fields, registers, timers, states, capabilities |
| source | wiki/sources/ | LLM-generated summary pages for parsed raw sources |
| query | wiki/queries/ | Open protocol questions requiring follow-up |
| comparison | wiki/comparisons/ | Version or mechanism comparisons |
| synthesis | wiki/synthesis/ | Cross-section protocol-analysis summaries |

## Citation Rules

- Cite section IDs, page numbers, and object IDs when answering protocol questions.
- Preserve distinctions between normative requirements, notes, examples, and figures/tables.
- Link generated pages back to raw `pcie_section` and `pcie_object` sources through frontmatter `sources`.
- Do not copy figure/table/equation internals into section-derived pages unless the object source is explicitly cited.
