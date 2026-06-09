# MennzLore

> Extract a deep, structured, lorebook from public-domain novels — fast, deterministic, and MCP-native.

MennzLore is an end-to-end pipeline that converts Project Gutenberg
novels into a master lorebook suitable for AI art generation, character
arc analysis, and worldbuilding dashboards. The connected AI (e.g.
Hermes, Claude Code, Codex) does the heavy lifting (3-Pass LLM
extraction); the engine handles all the deterministic plumbing
(download, split, merge, validate, render).

## What's in this repo

```
MennzLore/
├── engine/                # Deterministic Python modules (no LLM)
│   ├── split_chapters.py      # Phase 2: download + split
│   ├── phase3_global_lore.py  # Phase 3.1: write global lore
│   ├── phase3_auto_verify.py  # Phase 3.2: validate name_map
│   ├── merge_to_micro_facts.py# Phase 4: merge 3-Pass JSONs
│   ├── assemble_generic.py    # Phase 7: assemble master lorebook
│   ├── assemble_production_generic.py  # Phase 9: render cinematography
│   ├── chart_render_generic.py          # Phase 10: render map
│   └── lore_models.py        # Pydantic V2 schemas
│
├── mcp_server/            # FastMCP server exposing the engine
│   └── server.py              # 12+ MCP tools
│
├── prompts/               # Markdown prompts (one per LLM pass)
│   └── phase3_global_lore_prompt.md
│
├── references/            # V4A patches for files too large for the
│   └── 0001-fix-assemble-generic-Bug-6.md  # single-commit API
│
├── tests/                 # Unit + integration tests
│   ├── test_splitter.py
│   ├── test_xml_unwrap.py
│   ├── test_failfast.py
│   └── run_all_tests.py
│
├── docs/                  # Architecture + design docs
├── examples/              # End-to-end worked examples
├── templates/             # Templates for new project scaffolds
├── dashboard/             # World explorer web UI
│
└── README.md              # This file
```

## Quickstart

### 1. Install (one-time)

```bash
git clone https://github.com/mgprona/MennzLore.git
cd MennzLore
pip install pydantic fastmcp openai
```

### 2. Run the tests

```bash
python tests/run_all_tests.py
# Expected: 53 tests OK
```

### 3. Use the MCP server

Add to your client's MCP config (`~/.claude/mcp_servers.json` or
similar):

```json
{
  "mcpServers": {
    "mennzlore": {
      "command": "python",
      "args": ["mcp_server/server.py"]
    }
  }
}
```

### 4. Run a full pipeline

Once connected, ask the AI:

> "Use MennzLore to process Project Gutenberg #244 (A Study in Scarlet) end-to-end."

The AI will:

1. Call `acquire_by_id` to download the book
2. Call `split_into_chapters` to clean and split
3. Read clean chapters and call `extract_global_lore` to get a prompt
4. Reason over the chapters and call `save_global_lore` with the JSON
5. Call `auto_verify_names` to validate
6. (You provide 3-Pass JSONs from external LLM, then call) `merge_micro_facts`
7. Call `assemble_lorebook` to produce `output/<prefix>_master_lorebook_full.md`
8. Call `render_production` to produce `output/production/cinematography_shot_list.json`
9. Call `render_map` to produce `output/spatial/chart_map_skeleton.svg`

## The 8 MCP tools

| Tool | Phase | Purpose |
|---|---|---|
| `acquire_by_id` / `acquire_by_title` | 1 | Download a PG book, scaffold `raw/` |
| `split_into_chapters` | 2 | Strip boilerplate + bracketed annotations, split per chapter |
| `extract_global_lore` | 3.1 | Returns the prompt for the connected AI to reason over |
| `save_global_lore` | 3.1 | Persists 4 JSON files (global_lore, name_map, timeline, chapter_appearance) |
| `auto_verify_names` | 3.2 | Validates name_map vs clean files (no LLM) |
| `merge_micro_facts` | 4 | Merges 3-Pass LLM JSONs into per-chapter micro_facts |
| `assemble_lorebook` | 7 | Produces `output/<prefix>_master_lorebook_full.md` |
| `render_production` | 9 | Produces `output/production/cinematography_shot_list.json` |
| `render_map` | 10 | Produces `output/spatial/chart_map_skeleton.svg` |

## Three test novels

| Project | Author | Source | Chapters | Result |
|---|---|---|---|---|
| The Mind Master | Arthur J. Burks | PG #29416 | 14 | All 8 phases verified |
| A Princess of Mars | Edgar Rice Burroughs | PG #62 | 28 | All 8 phases verified |
| A Study in Scarlet | Arthur Conan Doyle | PG #244 | 16 | All 8 phases verified |

## Tests

```bash
# Run all 53 tests
python tests/run_all_tests.py

# Or use pytest
pip install pytest
python -m pytest tests/ -v
```

The test suite covers:
- Inline annotation stripping (Bug #1, #15)
- PART-level heading detection (Bug #15)
- Transcriber's Changes footer detection (Bug #1)
- Recursive `{"item": ...}` unwrapping (Bug #3, N-layer)
- Type coercion `string ↔ list` (Bug #5, #16)
- Fail-fast on missing inputs (Bug #6, #10)
- Idempotency of all transforms

## Stress test report

A complete stress test was run against 3 novels in 6 phases, finding
**16 bugs** (14 original + 2 discovered in the third novel). 11 were
fixed in this repo; 5 are downstream of the LLM extraction step (no
deterministic fix possible) or are server-side MCP issues. Full
details in `BUG_REPORT.md` (see the Burks project folder or
`docs/STRESS_TEST.md`).

## Contributing

Open a PR against `master`. All new code must come with unit tests
under `tests/`. Run `python tests/run_all_tests.py` before pushing.

## License

Public-domain source texts from Project Gutenberg. Code is MIT.
