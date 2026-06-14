# MennzLore

> สกัดข้อมูลนิยาย public-domain ออกมาเป็น lorebook มีโครงสร้าง — เร็ว, ใช้โค้ดล้วน ๆ, และทำงานผ่าน MCP
>
> *Extract a deep, structured lorebook from novels — fast, deterministic, and MCP-native.*

MennzLore แปลงนิยายจาก Project Gutenberg (และไฟล์ EPUB / YouTube playlist) ให้กลายเป็น master lorebook ฉบับสมบูรณ์ เอาไปใช้สร้างรูป AI, วิเคราะห์เส้นเรื่อง, สร้างแดชบอร์ดโลก, ค้นหาผ่าน knowledge graph, และ semantic search ได้

AI ที่เชื่อมต่ออยู่ (Claude, Hermes, Gemini, Codex ฯลฯ) ทำหน้าที่คิดวิเคราะห์ผ่าน **Adaptive 2/3-Pass LLM** — engine จัดการงาน deterministic ทั้งหมด (ดาวน์โหลด, แยกบท, รวมข้อมูล, ตรวจสอบ, เรนเดอร์, สร้างกราฟ, ทำ index)

---

## สารบัญ

- [ติดตั้ง](#ติดตั้ง-ครั้งเดียว)
- [เริ่มใช้งาน](#เริ่มใช้งาน)
- [Pipeline 14 Phase](#pipeline-ครบ-14-phase)
- [MCP Tools (26 รายการ)](#mcp-tools-26-รายการ)
- [Adaptive 2/3-Pass](#adaptive-23-pass-v52)
- [Troubleshooting](#troubleshooting)
- [โครงสร้าง repo](#โครงสร้าง-repo)
- [ทดสอบ](#ทดสอบ)
- [นิยายที่ผ่านการทดสอบแล้ว](#นิยายที่ผ่านการทดสอบแล้ว)
- [License](#license)

---

## ติดตั้ง (ครั้งเดียว)

```bash
git clone https://github.com/mgprona/MennzLore.git
cd MennzLore
pip install -r requirements.txt
python install.py          # ลงทะเบียน MCP กับทุก AI client ที่ตรวจพบ
python install.py --verify # ทดสอบ server startup
```

ตัวเลือก installer:

```bash
python install.py --clients hermes,claude  # ระบุ client เอง
python install.py --list                   # ดู client ที่ตรวจพบ
python install.py --upgrade                # git pull + pip upgrade + re-register
python install.py --python /path/to/venv/python
```

รองรับ: Claude Desktop, Hermes Agent, Gemini CLI, Google Antigravity, OpenCode, OpenAI Codex, Continue.dev

---

## เริ่มใช้งาน

หลัง MCP server เชื่อมต่อแล้ว สั่ง AI ตรงๆ เลย:

> "ใช้ MennzLore รัน pipeline เต็มรูปแบบสำหรับ Project Gutenberg #244 (A Study in Scarlet)"

AI จะทำงานตามลำดับ:

1. `acquire_by_id` / `acquire_by_title` / `acquire_epub` — ดึงข้อมูล
2. `split_into_chapters` — แยกบท + ล้าง markup
3. prompt `extract_global_lore` → `save_global_lore` — สกัด name map + chapter appearance
4. **Adaptive 2/3-Pass** ทีละบท:
   - บทสั้น (<15 KB): prompt `sa_combined` → `sa_lore` (2 calls)
   - บทยาว (≥15 KB): prompt `analyze_architect` → `analyze_profiler` → `analyze_chronicler` (3 calls)
5. `merge_micro_facts` ต่อบท — normalize + Pydantic validation
6. `run_full_pipeline` — รัน engine phases 5–14 ทีเดียว → **master lorebook**

---

## Pipeline ครบ 14 Phase

| Phase | ชื่อ | ประเภท | Output |
|:------|:-----|:-------|:-------|
| 1 | Acquire | Engine | `raw/<prefix>_full.txt` |
| 2 | Split & Clean | Engine | `clean/<prefix>_EP###.txt` |
| 3 | Global Lore + Names | **LLM** | `verification/<prefix>_global_lore.json`, `name_map.json` |
| 3.2 | Auto-Verify Names | Engine | `verification/<prefix>_name_verification.json` |
| 4 | Micro-Facts (2/3-Pass) | **LLM** | `micro_facts/<prefix>_EP###_micro_facts.json` |
| 5 | Merge & Validate | Engine | Pydantic validation + normalize_sa_json |
| 6 | Production Render | Engine | `output/production/` — shot list, image prompts, style bible |
| 7 | Map Render | Engine | `output/spatial/` — SVG map + routes |
| 8 | Relationship Graph | Engine | `output/entities/` — force-directed SVG, GEXF, JSON |
| 9 | Hybrid Notes | Engine | per-entity [CONTEXT][FACTS][BEHAVIOR][GAPS][EVIDENCE] |
| 10 | Entity Registry | Engine | typed classification (6 ประเภท, 9 แบบความสัมพันธ์) |
| 11 | Knowledge Graph | Engine | SQLite FTS5 + graph query |
| 12 | Timeline | Engine | SVG timeline + character heatmap |
| 13 | Semantic Index | Engine | ChromaDB / TF-IDF vector search |
| 14 | **Assemble Lorebook** | Engine | `output/<prefix>_master_lorebook_full.md` — **FINAL** |

---

## MCP Tools (26 รายการ)

### Core Pipeline

| Tool | Phase | หน้าที่ |
|------|:-----:|---------|
| `acquire_by_id` | 1 | ดาวน์โหลดจาก Gutenberg ID |
| `acquire_by_title` | 1 | ดาวน์โหลดจากชื่อเรื่อง + ผู้แต่ง |
| `acquire_epub` | 1 | นำเข้าไฟล์ .epub ในเครื่อง |
| `split_into_chapters` | 2 | แยกบท + ล้าง markup |
| `save_global_lore` | 3 | บันทึก name map + chapter appearance (MCP-native, ไม่ต้อง API key) |
| `auto_verify_names` | 3 | ตรวจสอบชื่อตัวละครกับข้อความ (ไม่ใช้ LLM) |
| `merge_micro_facts` | 5 | รวม + normalize + validate ต่อบท |
| `run_full_pipeline` | 5–14 | **รัน engine phases ทั้งหมดในคำสั่งเดียว** |
| `assemble_lorebook_tool` | 14 | ประกอบ master lorebook (ขั้นตอนสุดท้าย) |

### Extended Pipeline

| Tool | Phase | หน้าที่ |
|------|:-----:|---------|
| `render_production_tool` | 6 | shot list + image prompts + visual style bible |
| `render_map_tool` | 7 | แผนที่ SVG + routes |
| `render_relationships_tool` | 8 | กราฟความสัมพันธ์ entity |
| `generate_hybrid_notes_tool` | 9 | per-entity hybrid notes |
| `build_entity_registry_tool` | 10 | ทะเบียน entity แยกประเภท |
| `query_knowledge_graph` | 11 | FTS5 + graph query (stats/search/entity/path/neighbors) |
| `render_timeline_tool` | 12 | SVG timeline + character heatmap |
| `query_lore_semantic_tool` | 13 | semantic search (ChromaDB / TF-IDF) |

### Media & Utilities

| Tool | หน้าที่ |
|------|---------|
| `generate_storyboard_tool` | สร้างภาพผ่าน OpenRouter |
| `analyze_youtube_playlist` | สแกน YouTube playlist ว่ามี subtitle หรือไม่ |
| `run_youtube_acquisition` | ดึง transcript/STT จาก YouTube (Whisper) |
| `open_dashboard_tool` | เปิด world explorer dashboard ที่ localhost:8000 |
| `query_past_lore_tool` | RAG ค้นหาข้อมูลจากตอนก่อนหน้า |
| `run_saga_assembly` | ประกอบ saga lorebook หลายเล่ม |
| `query_saga_rag` | ค้นหาข้ามเล่มผ่าน semantic search |

### MCP Prompts (6 รายการ — ครบทุก pass)

| Prompt | ใช้ที่ | หน้าที่ |
|--------|--------|---------|
| `extract_global_lore` | Phase 3 | อ่านทุกบท → name map + chapter appearance |
| `analyze_architect` | Phase 4 Pass 1.1 | scenes + key plot points (ใส่ `_source_hash` อัตโนมัติ) |
| `analyze_profiler` | Phase 4 Pass 1.2 | characters, behaviors, items, dialogue (inject scene list จาก architect JSON อัตโนมัติ) |
| `analyze_chronicler` | Phase 4 Pass 1.3 | cross-chapter connections + lore discoveries |
| `sa_combined` | Phase 4 2-Pass | extraction ครบในคำสั่งเดียว (บทสั้น <15 KB) |
| `sa_lore` | Phase 4 2-Pass | lore matching กับ global context |

### MCP Resources (5 รายการ)

`schema://architect` · `schema://profiler` · `schema://chronicler` · `schema://micro_facts_final` · `example://micro_facts`

---

## Adaptive 2/3-Pass (v5.2)

ประหยัด token 60–70% เมื่อเทียบกับ v5.0 (single-pass เต็มบท):

| บทขนาด | Mode | LLM Calls | Prompts |
|:-------:|:----:|:---------:|---------|
| < 15 KB | 2-Pass | 2 | `sa_combined` → `sa_lore` |
| ≥ 15 KB | 3-Pass | 3 | `analyze_architect` → `analyze_profiler` → `analyze_chronicler` |

Engine รันหลัง LLM ทุกครั้ง:
- `normalize_sa_json()` — แก้ field name ผิด ~20 รูปแบบอัตโนมัติ
- `self_correct_micro_facts()` — heal scene ID references
- `MicroFactsFinal @model_validator` — ตรวจ hallucinated scene refs ทุกตัว
- Source verification — ตรวจ `_source_hash` ว่า AI อ่านบทจริง ไม่ได้สร้างข้อมูลปลอม

---

## Troubleshooting

### MCP tools ไม่ขึ้นในรายการ

```bash
hermes mcp test mennzlore   # ทดสอบว่า server ตอบสนองหรือไม่
```
- `Connected` แต่ tools ยังไม่เห็น → ต้อง `/restart` session (discovery เกิดขึ้นตอน startup เท่านั้น)
- `Connection failed: Input should be a valid list` → config.yaml ของ Hermes ใช้ YAML string แทน list (`'[C:/...]'` → `[C:/...]`)

### run_full_pipeline timeout

ถ้า project มี 12+ บท, 60+ scenes → MCP timeout 600s ได้ ให้รันแยก phase แทน:
```python
# รันทีละ phase ผ่าน Python โดยตรง
from engine.assemble_generic import assemble_lorebook
assemble_lorebook("/path/to/project", "prefix")
```

### ตรวจสอบ output quality หลัง pipeline

| Phase | เช็คไฟล์ | ผ่าน |
|-------|---------|------|
| 6 | `scene_image_prompts.json` | > 0 items |
| 6 | `visual_style_bible.json` | > 0 keys |
| 7 | `location_geography.json` | มี entries |
| 8 | `relationship_data.json` | nodes > 10, edges > 0 |
| 11 | `knowledge_graph.db` | ไฟล์ > 10KB |
| 14 | `master_lorebook_full.md` | ไฟล์ > 10KB |

### MCP server restart (เฉพาะ code change เท่านั้น)

ถ้าแก้ engine/*.py แล้วไม่อยาก `/restart` ทั้ง session:
```bash
# หา process ID ของ MCP server
wmic process where "name='python.exe' and commandline like '%server%'" get processid
# kill + start ใหม่ แล้ว MCP จะ reconnect อัตโนมัติ
```

> **หมายเหตุ:** กรณี config change ยังต้อง `/restart` อยู่

---

## โครงสร้าง repo

```
MennzLore/
├── engine/          # 29 deterministic Python modules (ไม่มี LLM)
├── mcp_server/      # FastMCP server — 26 tools + 6 prompts + 5 resources
├── prompts/         # Markdown prompt templates (1 ไฟล์ต่อ LLM pass)
├── schemas/         # JSON Schema (Pydantic V2 source of truth)
├── templates/       # Sub-agent goal templates
├── tests/           # 85 unit/integration tests
├── scripts/         # smoke_test.py, compare_baseline.py
├── examples/        # ตัวอย่าง micro_facts + lorebook index
├── dashboard/       # World explorer web UI
├── docs/            # ENGINE.md, PIPELINE.md, MCP_DESIGN.md
├── install.py       # Multi-client auto-installer
└── requirements.txt
```

---

## ทดสอบ

```bash
python tests/run_all_tests.py   # 85 tests, คาดว่าผ่านทั้งหมด
```

ครอบคลุม: chapter splitting, XML array unwrapping, normalize_sa_json, evidence tracing, fail-fast, phase 1–3 regression guards

---

## นิยายที่ผ่านการทดสอบแล้ว

| นิยาย | ผู้แต่ง | Gutenberg ID | บท | ผล |
|-------|---------|:------------:|:--:|:--:|
| Alice's Adventures in Wonderland | Lewis Carroll | #11 | 12 | ✅ |
| Through the Looking-Glass | Lewis Carroll | #12 | 12 | ✅ |
| The Time Machine | H.G. Wells | #35 | 12 | ✅ |
| Strange Case of Dr Jekyll & Mr Hyde | R.L. Stevenson | #42 | 6 | ✅ |
| A Princess of Mars | E.R. Burroughs | #62 | 28 | ✅ |
| A Study in Scarlet | A.C. Doyle | #244 | 16 | ✅ |
| The Call of the Wild | Jack London | #215 | 7 | ✅ |
| The Mind Master | A.J. Burks | #29416 | 14 | ✅ |

**v5.2 stress test:** 8 นิยาย, 107 บท — 0 validation error, 0 hallucination, 100% engine phase pass

---

## License

ข้อความต้นฉบับจาก Project Gutenberg เป็น public domain · โค้ดเป็น MIT