# MCP Server Design (แผนอนาคต)

เป้าหมาย: ห่อ pipeline เป็น **MCP server** เพื่อให้ LLM client ใดก็เรียกได้ ไม่ต้องนั่งปรับจูน prompt/script ใหม่ทุกครั้ง

> หลักการ: phase ที่เป็น **deterministic** → MCP `tool`, แกน **LLM** → MCP `prompt` + `resource` (schema)

---

## ทำไม MCP เหมาะกับระบบนี้

ระบบนี้ LLM เป็นแกนหลักอยู่แล้ว — phase 2,3,4 คือการให้โมเดลอ่าน text แล้วคืน structured JSON
MCP ออกแบบมาเพื่อสิ่งนี้พอดี:
- **Tools** = ฟังก์ชัน deterministic ที่ LLM สั่งรัน (merge, assemble, render)
- **Prompts** = prompt template ที่ server จัดให้ (architect/profiler/chronicler)
- **Resources** = JSON Schema + ตัวอย่าง ที่ LLM ดึงไปบังคับ output

---

## Mapping: Phase → MCP primitive

| Phase | ประเภท | MCP primitive | ชื่อที่เสนอ |
|:------|:-------|:--------------|:-----------|
| 2 Clean | LLM | prompt | `clean_text` |
| 3.1 Global Lore | LLM | prompt + resource | `extract_global_lore` |
| 3.2 Auto-Verify | Engine | tool | `verify_names` |
| 4-P1 Architect | LLM | prompt + resource(schema) | `analyze_architect` |
| 4-P1 Profiler | LLM | prompt + resource(schema) | `analyze_profiler` |
| 4-P1 Chronicler | LLM | prompt + resource(schema) | `analyze_chronicler` |
| 4 Merge | Engine | tool | `merge_micro_facts` |
| 4-P2 Synthesis | LLM | prompt | `synthesize_window` |
| 7 Assemble | Engine | tool | `assemble_lorebook` |
| 9 Production | Engine | tool | `render_production` |
| 10 Spatial | Engine | tool | `render_map` |

---

## Tool signatures (ร่าง)

Engine tools ห่อ CLI ที่มีอยู่ได้ตรงๆ (ทุกตัวรับ `project_dir` + `prefix` อยู่แล้ว):

```python
@server.tool()
def merge_micro_facts(prefix: str, ep_num: int, base_dir: str) -> dict:
    """รวม 3-pass output → micro_facts/<prefix>_EP<nnn>_micro_facts.json (validated)"""

@server.tool()
def assemble_lorebook(project_dir: str, prefix: str = "") -> dict:
    """Phase 7 → output/<prefix>_master_lorebook_full.md"""

@server.tool()
def render_production(project_dir: str, prefix: str = "") -> dict:
    """Phase 9 → output/production/* (image prompts, shot list, style bible)"""

@server.tool()
def render_map(project_dir: str, prefix: str = "") -> dict:
    """Phase 10 → output/spatial/* (geography, routes, SVG map)"""

@server.tool()
def verify_names(project_dir: str, prefix: str = "") -> dict:
    """Phase 3.2 → cross-ref name_map กับ raw text, คืนชื่อที่หาย"""
```

Resources เสิร์ฟ schema + ตัวอย่างจาก repo:

```
resource: schema://architect      → schemas/architect.schema.json
resource: schema://profiler       → schemas/profiler.schema.json
resource: schema://chronicler     → schemas/chronicler.schema.json
resource: schema://micro_facts    → schemas/micro_facts_final.schema.json
resource: example://micro_facts   → examples/example_micro_facts.json
```

Prompts เสิร์ฟจาก `prompts/` พร้อม placeholder fill:

```
prompt: analyze_architect(chapter_text)               → prompts/pass11_architect_prompt.md
prompt: analyze_profiler(chapter_text, scene_list)    → prompts/pass12_profiler_prompt.md
prompt: analyze_chronicler(architect_json, profiler_json, global_lore_excerpt)
```

---

## โครงสร้างที่จะเพิ่มเมื่อทำ MCP

```
MennzLore/
├── engine/          # มีอยู่แล้ว — tool ห่อ CLI พวกนี้
├── prompts/         # มีอยู่แล้ว — เสิร์ฟเป็น MCP prompts
├── schemas/         # มีอยู่แล้ว — เสิร์ฟเป็น MCP resources
└── mcp/             # ← เพิ่มทีหลัง
    ├── server.py    # FastMCP / mcp SDK entry
    ├── tools.py     # ห่อ engine/*.py
    ├── prompts.py   # โหลด + fill prompts/*.md
    └── resources.py # เสิร์ฟ schemas/ + examples/
```

---

## ลำดับการพัฒนาที่แนะนำ

1. แยก engine scripts ให้มี `main()` ที่เรียกเป็นฟังก์ชันได้ (ตอนนี้บางตัว logic อยู่ใน `if __name__`)
2. เขียน `mcp/tools.py` ห่อ 5 engine functions
3. เพิ่ม `mcp/resources.py` เสิร์ฟ schemas + examples
4. เพิ่ม `mcp/prompts.py` เสิร์ฟ prompt templates พร้อม fill
5. ทดสอบกับ MCP client (Claude Desktop / Cursor / custom)

> Engine ถูกออกแบบให้ project-agnostic แล้ว ดังนั้นการห่อเป็น tool แทบไม่ต้องแก้ logic เดิม
