# MennzLore

> Extract a deep, structured lorebook from public-domain novels — fast, deterministic, and MCP-native.
>
> *สกัดข้อมูลนิยาย public-domain ออกมาเป็น lorebook มีโครงสร้าง — เร็ว, ใช้โค้ดล้วน ๆ, และทำงานผ่าน MCP*

MennzLore is an end-to-end pipeline that converts Project Gutenberg novels (and YouTube playlists) into a master lorebook suitable for AI art generation, character arc analysis, worldbuilding dashboards, knowledge graph querying, and semantic search. The connected AI (Hermes, Claude, Codex, Gemini, etc.) does the heavy lifting (**Adaptive 2/3-Pass** LLM extraction); the engine handles all the deterministic plumbing (download, split, merge, validate, render, graph, index).

*MennzLore คือระบบไปป์ไลน์ครบวงจรที่แปลงนิยายจาก Project Gutenberg (และ YouTube playlist) ให้กลายเป็น lorebook ฉบับสมบูรณ์ เอาไปใช้สร้างรูป AI, วิเคราะห์เส้นเรื่องตัวละคร, สร้างแดชบอร์ดโลก, ค้นหาผ่าน knowledge graph, และ semantic search ได้ AI ที่เชื่อมต่ออยู่ (Hermes, Claude, Gemini ฯลฯ) ทำหน้าที่คิดวิเคราะห์ (**Adaptive 2/3-Pass** LLM) ส่วน engine จัดการงานที่ไม่ต้องคิด (ดาวน์โหลด, แยกบท, รวมข้อมูล, ตรวจสอบ, เรนเดอร์, สร้างกราฟ, ทำ index)*

## What's in this repo <small>*มีอะไรใน repo นี้บ้าง*</small>

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

## v5.1 Optimization (June 2026) <small>*การปรับปรุง v5.1 (มิถุนายน 2569)*</small>

**Token savings: 60-70%** across a 31-chapter stress test (3 novels). Key changes:
*ประหยัด Token ได้ 60-70% จากการทดสอบ 31 บท (3 เรื่อง):*

| Change | Impact |
|---|---|
| Adaptive 2/3-Pass routing | บทสั้น <15KB → ใช้ SA Combined (2 calls) แทน 3-Pass (3 calls) |
| Prompt Caching (system/user split) | แยกส่วน system (static) กับ user (dynamic) → LLM API แคช system part ได้ ประหยัด 20-30%/call |
| CRITICAL TOOL RESTRICTIONS | ห้าม subagent browse filesystem → ลด overhead 30-50% |
| `normalize_sa_json()` in engine | แก้ field name ผิดให้อัตโนมัติ → merge fail 0% (จากเดิม 25-75%) |
| Phase 3.1 names-only + engine candidates | ลด token global lore ~50% |
| Auto-update check on MCP server start | เช็คเวอร์ชันใหม่ทุก 24 ชม. อัตโนมัติ — แจ้งเตือนผ่าน stderr |

### Installer flags

```bash
python install.py --python /path/to/venv/python  # specify Python exe
python install.py --verify                        # smoke-test server startup
python install.py --upgrade                       # git pull + pip upgrade + re-register
python install.py --list                          # show all detected clients
```

## Quickstart <small>*เริ่มต้นใช้งาน*</small>

### 1. Install (one-time) <small>*ติดตั้ง (ครั้งเดียว)*</small>

```bash
git clone https://github.com/mgprona/MennzLore.git
cd MennzLore
pip install -r requirements.txt
```

Or use the auto-installer, which handles deps + MCP registration for all your AI clients:
*หรือใช้ตัวติดตั้งอัตโนมัติ — จัดการทั้ง deps + ลงทะเบียน MCP ให้ทุก AI client:*

```bash
python install.py              # auto-detect installed clients
python install.py --list       # ดู client ที่ตรวจพบ
python install.py --clients hermes,claude  # ระบุ client เอง
python install.py --python /path/to/venv/python --verify  # ทดสอบ server startup
```

Supported clients: Claude Desktop, Hermes Agent, Gemini CLI, Google Antigravity, OpenCode CLI, OpenAI Codex CLI, Continue.dev.

### 2. Run the tests <small>*รันเทสต์*</small>

```bash
python tests/run_all_tests.py
# Expected: 85 passed

# หรือใช้ pytest
pip install pytest
python -m pytest tests/ -v
```

The test suite covers: inline annotation stripping, PART-level heading detection, footnote formatting, recursive `{"item": ...}` unwrapping, type coercion, fail-fast on missing inputs, idempotency, and Phase 1-3 regression guards.

### 3. Run a full pipeline <small>*รันไปป์ไลน์เต็ม (14 ขั้นตอน)*</small>

Once the MCP server is connected to your AI client, ask:
*เมื่อ MCP server เชื่อมต่อกับ AI client แล้ว — สั่งว่า:*

> "Use MennzLore to process Project Gutenberg #244 (A Study in Scarlet) end-to-end."

The AI will: *AI จะทำงานตามนี้:*

1. `acquire_by_id` → ดาวน์โหลดหนังสือ
2. `split_into_chapters` → ล้าง markup + แยกบท
3. `extract_global_lore` prompt → AI อ่านทุกบท + สกัดข้อมูลโลก, ชื่อตัวละคร, timeline
4. `auto_verify_names` → ตรวจสอบชื่อตัวละคร
5. **Adaptive 2/3-Pass** LLM วิเคราะห์ทีละบท
   - บทสั้น (<15KB): SA Combined (2 calls)
   - บทยาว (>=15KB): Architect → Profiler → Chronicler (3 calls)
6. `merge_micro_facts` → รวมข้อมูล + normalize_sa_json
7. `run_full_pipeline` → รันทุก engine phase (5-14) รวดเดียว:
   - Production render (shot list + image prompts)
   - Map render (แผนที่ SVG)
   - Relationship graph
   - Hybrid notes
   - Entity registry
   - Knowledge graph
   - Timeline
   - Semantic index
   - **ASSEMBLE master lorebook** (ขั้นตอนสุดท้าย — ประกอบ lorebook ฉบับสมบูรณ์)

## The 24 MCP Tools

### Core Pipeline (Phases 1-14)

| Tool | Phase | |
|---|---|---|
| `acquire_by_id` | 1 | ดาวน์โหลดหนังสือจาก Gutenberg ID |
| `acquire_by_title` | 1 | ดาวน์โหลดจากชื่อเรื่อง + ชื่อผู้แต่ง |
| `split_into_chapters` | 2 | ล้าง markup + แยกเป็นบท ๆ |
| `save_global_lore` | 3 | บันทึกข้อมูลโลก — ใช้ AI ที่เชื่อมต่ออยู่ ไม่ต้องใช้ API key |
| `run_global_lore` | 3 | สำรอง — เรียกผ่าน OPENAI_API_KEY |
| `auto_verify_names` | 3 | ตรวจสอบชื่อตัวละครกับข้อความ (ไม่ใช้ LLM) |
| `verify_character_names` | 3 | เทียบชื่อกับไฟล์ raw/clean |
| `merge_micro_facts` | 5 | รวมข้อมูล + normalize_sa_json แก้ field name ให้อัตโนมัติ |
| `run_full_pipeline` | 5-14 | **รันทุก engine phase 5-14 ในคำสั่งเดียว** |
| `assemble_lorebook_tool` | 14 | ประกอบ lorebook ฉบับสมบูรณ์ (ขั้นตอนสุดท้าย) |
| `render_production_tool` | 6 | สร้าง shot list, image prompts, visual style bible |
| `render_map_tool` | 7 | สร้างแผนที่ SVG + routes |
| `open_dashboard_tool` | — | เปิด world explorer ที่ localhost:8000 |
| `query_past_lore_tool` | — | RAG ค้นหาข้อมูลจากตอนก่อนหน้า |

### Extended Pipeline (Phases 8-13)

| Tool | Phase | |
|---|---|---|
| `render_relationships_tool` | 8 | กราฟความสัมพันธ์ entity (SVG, GEXF, JSON) |
| `generate_hybrid_notes_tool` | 9 | โน้ตต่อ entity [CONTEXT][FACTS][BEHAVIOR][GAPS][EVIDENCE] |
| `build_entity_registry_tool` | 10 | ทะเบียน entity แยกประเภท (6 ประเภท, 9 แบบความสัมพันธ์) |
| `query_knowledge_graph` | 11 | ค้นหาผ่าน FTS5 + graph query |
| `render_timeline_tool` | 12 | SVG timeline + heatmap ตัวละคร + tracking สถานที่ |
| `query_lore_semantic_tool` | 13 | ค้นหาเชิงความหมาย (ChromaDB / TF-IDF fallback) |

### Storyboard & Media <small>*สร้างภาพ + มีเดีย*</small>

| Tool | |
|---|---|
| `generate_storyboard_tool` | สร้างภาพผ่าน OpenRouter (Gemini 2.5 Flash) |
| `analyze_youtube_playlist` | สแกน playlist YouTube ว่ามี subtitle หรือไม่ |
| `run_youtube_acquisition` | ดึง transcript/STT จาก YouTube (Whisper ผ่าน OpenRouter) |

### Saga Mode <small>*โหมดหลายเล่ม*</small>

| Tool | |
|---|---|
| `run_saga_assembly` | ประกอบ saga lorebook หลายเล่ม + ตรวจสอบความสอดคล้องข้ามเล่ม |
| `query_saga_rag` | ค้นหาข้ามเล่มผ่าน semantic search |

### MCP Resources & Prompts <small>*รีซอร์สและพรอมปต์*</small>

**5 Resources:** `schema://architect`, `schema://profiler`, `schema://chronicler`, `schema://micro_facts_final`, `example://micro_facts`

**4 Prompts (system/user split for prompt caching):** `extract_global_lore`, `analyze_chronicler`, `sa_combined`, `sa_lore`

## Verified Test Novels <small>*นิยายที่ทดสอบแล้ว*</small>

| Project | Author | Source | Chapters | Phases Verified |
|---|---|---|---|---|
| Alice's Adventures in Wonderland | Lewis Carroll | PG #11 | 12 | ทดสอบ v5.1 ครบ 1-14 |
| Through the Looking-Glass | Lewis Carroll | PG #12 | 12 | ทดสอบ v5.1 ครบ 1-14 |
| The Call of the Wild | Jack London | PG #215 | 7 | ทดสอบ v5.1 ครบ 1-14 |
| The Mind Master | Arthur J. Burks | PG #29416 | 14 | ผ่าน 1-14 |
| A Princess of Mars | Edgar Rice Burroughs | PG #62 | 28 | ผ่าน 1-14 |
| A Study in Scarlet | Arthur Conan Doyle | PG #244 | 16 | ผ่าน 1-14 |

**v5.1 stress test:** 31/31 chapters merged with 0 validation errors, 0 hallucinations. Token consumption reduced 60-70% vs v5.0.
*ทดสอบ v5.1: 31/31 บท merge สำเร็จ — 0 validation error, 0 hallucination กิน token ลดลง 60-70% เทียบกับ v5.0*

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

## License <small>*สัญญาอนุญาต*</small>

Public-domain source texts from Project Gutenberg. Code is MIT.
*ข้อความต้นฉบับจาก Project Gutenberg เป็น public domain โค้ดเป็น MIT*
