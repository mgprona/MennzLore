# MennzLore

> Extract a deep, structured lorebook from public-domain novels — fast, deterministic, and MCP-native.

MennzLore is an end-to-end pipeline that converts Project Gutenberg novels (and YouTube playlists) into a master lorebook suitable for AI art generation, character arc analysis, worldbuilding dashboards, knowledge graph querying, and semantic search. The connected AI (Hermes, Claude, Codex, Gemini, etc.) does the heavy lifting (**Adaptive 2/3-Pass** LLM extraction); the engine handles all the deterministic plumbing (download, split, merge, validate, render, graph, index).

## What's in this repo

```
MennzLore/
├── engine/                    # Deterministic Python modules (no LLM) — 28 files
│   ├── fetch_raw.py               # Phase 1: Gutenberg acquisition
│   ├── split_chapters.py          # Phase 2: split & clean
│   ├── phase3_global_lore.py      # Phase 3.1: global lore (names-only, engine candidates)
│   ├── phase3_auto_verify.py      # Phase 3.2: name verification
│   ├── merge_to_micro_facts.py    # Phase 4: adaptive 2/3-Pass merge + normalize_sa_json
│   ├── assemble_generic.py        # Phase 7: master lorebook assembly
│   ├── assemble_production_generic.py  # Phase 9: cinematography render
│   ├── chart_render_generic.py    # Phase 10: map render
│   ├── relationship_graph.py      # Phase 11: force-directed entity graph
│   ├── hybrid_notes.py            # Phase 12: per-entity hybrid notes
│   ├── entity_registry.py         # Phase 13: typed entity registry
│   ├── knowledge_graph.py         # Phase 14: SQLite FTS5 + graph query
│   ├── timeline_render.py         # Phase 15: SVG timeline visualization
│   ├── vector_rag.py              # Phase 16: semantic search (ChromaDB/TF-IDF)
│   ├── image_generator.py         # Storyboard image generation (OpenRouter)
│   ├── youtube_acquire.py         # YouTube transcript/STT acquisition
│   ├── saga_assembler.py          # Saga Mode: multi-volume assembly
│   ├── saga_config.py             # Saga configuration
│   ├── saga_rag_memory.py         # Saga cross-volume RAG
│   ├── rag_memory.py              # Local RAG memory
│   ├── lore_handoff.py            # Cross-book lore handoff
│   ├── lore_models.py             # Pydantic V2 schemas (source of truth)
│   ├── pipeline_state.py          # Pipeline state tracking
│   ├── verify_names.py            # Name cross-reference engine
│   ├── generate_schemas.py        # JSON Schema generator
│   ├── utils.py                   # Shared utilities
│   ├── translate_raw.py           # Translation support
│   └── dashboard_server.py        # World explorer web dashboard
│
├── mcp_server/                # FastMCP server exposing the engine
│   └── server.py                  # 21 MCP tools + 4 prompts + 5 resources
│
├── prompts/                   # Markdown prompts (one per LLM pass)
│   ├── pass11_architect_prompt.md  # Pass 1.1: Architect (scene structure)
│   ├── pass12_profiler_prompt.md   # Pass 1.2: Profiler (characters/items)
│   ├── pass13_chronicler_prompt.md # Pass 1.3: Chronicler (cross-chapter)
│   ├── sa_combined_prompt.md       # SA Combined (direct extraction, default for <15KB)
│   ├── sa_lore_prompt.md           # SA Lore (match against global lore)
│   └── phase3_global_lore_prompt.md# Phase 3.1: Global lore extraction
│
├── schemas/                   # JSON Schema (source of truth for LLM output)
│   ├── architect.schema.json
│   ├── profiler.schema.json
│   ├── chronicler.schema.json
│   └── micro_facts_final.schema.json
│
├── tests/                     # Unit + integration tests — 85 tests
│   ├── test_splitter.py           # 27 tests
│   ├── test_xml_unwrap.py         # 25 tests
│   ├── test_phase1_improvements.py # 6 tests
│   ├── test_phase2_improvements.py # 8 tests
│   ├── test_phase3_improvements.py # 7 tests
│   ├── test_phase3_refactoring.py  # 2 tests
│   ├── test_normalize_sa_json.py   # 5 tests
│   ├── test_chapter_summary.py     # 3 tests
│   ├── test_failfast.py           # 2 tests
│   └── run_all_tests.py
│
├── scripts/                   # Utility scripts
│   ├── smoke_test.py
│   └── compare_baseline.py        # 3-novel stress test comparison
│
├── templates/                 # Sub-agent goal templates
├── examples/                  # Worked examples
├── dashboard/                 # World explorer web UI (index.html + app.js)
├── docs/                      # Architecture + design docs
│   ├── ENGINE.md              # Engine reference (Phases 1-10)
│   ├── PIPELINE.md            # Pipeline playbook (all phases)
│   └── MCP_DESIGN.md          # MCP design decisions
│
├── install.py                 # Multi-client auto-installer (7 AI clients)
├── patch_mcp.py               # MCP server patching utility
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## v5.1 Optimization (June 2026)

**Token savings: 60-70%** across a 31-chapter stress test (3 novels). Key changes:

| Change | Impact |
|---|---|
| Adaptive 2/3-Pass routing | Chapters <15KB use SA Combined (2 calls) instead of 3-Pass (3 calls) |
| Prompt Caching (system/user split) | Static instructions cached by LLM API — saves 20-30%/call |
| CRITICAL TOOL RESTRICTIONS | Subagents blocked from filesystem browsing — saves 30-50% overhead |
| `normalize_sa_json()` in engine | Auto-fixes field name mistakes — 0% merge failures (was 25-75%) |
| Phase 3.1 names-only + engine candidates | Token reduction ~50% for global lore extraction |
| Auto-update check on MCP server start | Cached 24h, warns on stderr if new version available |

### Installer flags

```bash
python install.py --python /path/to/venv/python  # specify Python exe
python install.py --verify                        # smoke-test server startup
python install.py --upgrade                       # git pull + pip upgrade + re-register
python install.py --list                          # show all detected clients
```

## Quickstart

### 1. Install (one-time)

```bash
git clone https://github.com/mgprona/MennzLore.git
cd MennzLore
pip install -r requirements.txt
```

Or use the auto-installer, which handles deps + MCP registration for all your AI clients:

```bash
python install.py              # auto-detect installed clients
python install.py --list       # see which clients are detected
python install.py --clients hermes,claude  # specific clients
python install.py --python /path/to/venv/python --verify  # test server startup
```

Supported clients: Claude Desktop, Hermes Agent, Gemini CLI, Google Antigravity, OpenCode CLI, OpenAI Codex CLI, Continue.dev.

### 2. Run the tests

```bash
python tests/run_all_tests.py
# Expected: 85 passed

# Or use pytest
pip install pytest
python -m pytest tests/ -v
```

The test suite covers: inline annotation stripping (Bug #1, #15), PART-level heading detection, footnote formatting, recursive `{"item": ...}` unwrapping (N-layer), type coercion, fail-fast on missing inputs, idempotency of all transforms, and Phase 1-3 regression guards.

### 3. Run a full pipeline

Once the MCP server is connected to your AI client, ask:

> "Use MennzLore to process Project Gutenberg #244 (A Study in Scarlet) end-to-end."

The AI will:

1. Call `acquire_by_id` → download the book
2. Call `split_into_chapters` → clean and split into episodes
3. Call `extract_global_lore` prompt + reason over chapters + `save_global_lore`
4. Call `auto_verify_names` → validate character names
5. Run **Adaptive 2/3-Pass** LLM analysis per chapter
   - Small chapters (<15KB): SA Combined (2 calls)
   - Large chapters (>=15KB): Architect → Profiler → Chronicler (3 calls)
6. Call `merge_micro_facts` per chapter
7. Call `run_full_pipeline` → runs all engine phases (5-14):
   - Production render (cinematography + image prompts)
   - Map render (SVG locations + routes)
   - Relationship graph
   - Hybrid notes
   - Entity registry
   - Knowledge graph
   - Timeline
   - Semantic index
   - **ASSEMBLE master lorebook** (final step)

## The 24 MCP Tools

### Core Pipeline (Phases 1-14)

| Tool | Phase | |
|---|---|---|
| `acquire_by_id` | 1 | Download a PG book by Gutenberg ID |
| `acquire_by_title` | 1 | Download by title + author (via gutendex) |
| `split_into_chapters` | 2 | Strip boilerplate + split per chapter |
| `save_global_lore` | 3 | Persist 4 JSONs (connected AI path, no API key) |
| `run_global_lore` | 3 | API fallback — uses OPENAI_API_KEY |
| `auto_verify_names` | 3 | Validate name_map vs clean texts (no LLM) |
| `verify_character_names` | 3 | Cross-reference names against raw/clean files |
| `merge_micro_facts` | 5 | Adaptive merge (2-Pass or 3-Pass) + normalize_sa_json |
| `run_full_pipeline` | 5-14 | **Run all engine phases in one go** |
| `assemble_lorebook_tool` | 14 | Master lorebook Markdown (final assembly) |
| `render_production_tool` | 6 | Cinematography + visual style bible |
| `render_map_tool` | 7 | SVG map with location geography |
| `open_dashboard_tool` | — | Launch world explorer at localhost:8000 |
| `query_past_lore_tool` | — | Local RAG: search past episodes' micro_facts |

### Extended Pipeline (Phases 8-13)

| Tool | Phase | |
|---|---|---|
| `render_relationships_tool` | 8 | Force-directed entity relationship graph (SVG, GEXF, JSON) |
| `generate_hybrid_notes_tool` | 9 | Per-entity hybrid notes [CONTEXT][FACTS][BEHAVIOR][GAPS][EVIDENCE] |
| `build_entity_registry_tool` | 10 | Typed entity registry (6 types, 9 relation types) |
| `query_knowledge_graph` | 11 | FTS5 + graph query: stats, search, entity, path, neighbors |
| `render_timeline_tool` | 12 | SVG timeline with character heatmap + location tracking |
| `query_lore_semantic_tool` | 13 | Semantic search (ChromaDB / TF-IDF fallback) |

### Storyboard & Media

| Tool | |
|---|---|
| `generate_storyboard_tool` | Image generation via OpenRouter (Gemini 2.5 Flash) |
| `analyze_youtube_playlist` | Scan YouTube playlist for subtitle availability |
| `run_youtube_acquisition` | Full YouTube transcript/STT (Whisper via OpenRouter) |

### Saga Mode

| Tool | |
|---|---|
| `run_saga_assembly` | Multi-volume saga lorebook + cross-volume consistency audit |
| `query_saga_rag` | Cross-volume semantic search |

### MCP Resources & Prompts

**5 Resources:** `schema://architect`, `schema://profiler`, `schema://chronicler`, `schema://micro_facts_final`, `example://micro_facts`

**4 Prompts (system/user split for prompt caching):** `extract_global_lore`, `analyze_chronicler`, `sa_combined`, `sa_lore`

## Verified Test Novels

| Project | Author | Source | Chapters | Phases Verified |
|---|---|---|---|---|
| Alice's Adventures in Wonderland | Lewis Carroll | PG #11 | 12 | 1-16 (v5.1 stress test) |
| Through the Looking-Glass | Lewis Carroll | PG #12 | 12 | 1-16 (v5.1 stress test) |
| The Call of the Wild | Jack London | PG #215 | 7 | 1-16 (v5.1 stress test) |
| The Mind Master | Arthur J. Burks | PG #29416 | 14 | 1-16 |
| A Princess of Mars | Edgar Rice Burroughs | PG #62 | 28 | 1-16 |
| A Study in Scarlet | Arthur Conan Doyle | PG #244 | 16 | 1-16 |

**v5.1 stress test:** 31/31 chapters merged with 0 validation errors, 0 hallucinations. Token consumption reduced 60-70% vs v5.0.

## Bug History

A complete stress test against 3 novels identified **19 bugs** (16 original + 3 from the Doyle probe). 14 are fixed in this repo; the remaining are downstream LLM-extraction issues or MCP protocol quirks. Full details in the `mennzlore-pipeline-testing` skill's `references/bug-catalog.md`.

Key fixes shipped:
- N-layer `{"item": ...}` array unwrapping
- PART-level heading false-chapter detection
- Footnote `[Footnote N: ...]` regex handling
- `sys.exit()` → proper exception raising in engine
- Pydantic list-of-list corruption in `save_global_lore`
- `merge_to_micro_facts` wrong output path

## Contributing

Open a PR against `master`. Rules:
- All new code must come with unit tests under `tests/`
- Run `python -m pytest tests/ -v` before pushing
- CI runs on push via `.github/workflows/test.yml`

## License

Public-domain source texts from Project Gutenberg. Code is MIT.
