# MennzLore

ระบบสกัด **lore** จากนิยาย/ซีรีส์ → โครงสร้างข้อมูลที่ค้นหา วัด และเรนเดอร์เป็นแผนที่ได้

> นิยาม: เปลี่ยน raw text (transcript / e-book) ให้กลายเป็น *surveyable fictional world* —
> master lorebook, character arc, timeline, foreshadowing, image prompts, และแผนที่ภูมิศาสตร์

เก็บแบบ **private repo** เพื่อเป็น single source of truth — ไม่ต้องนั่งปรับจูน engine ใหม่ทุกครั้งที่เริ่มโปรเจกต์

---

## ทำไมมี repo นี้

เดิมระบบกระจายอยู่ 3 ที่ (Hermes skill + โปรเจกต์ที่รันจริง 2 ตัว) เวอร์ชันสคริปต์ไม่ตรงกัน
ทุกครั้งที่เริ่มงานใหม่ต้องไป fork + ปรับจูนใหม่ → เสี่ยงพลาด

repo นี้ตรึง **canonical engine** ไว้ที่เดียว และแยกชัด 3 ชั้น:

| ชั้น | โฟลเดอร์ | ธรรมชาติ | อนาคต (MCP) |
|:-----|:---------|:---------|:------------|
| **Engine** | `engine/` | Python deterministic (Phase 7/9/10) | กลายเป็น MCP tools |
| **LLM core** | `prompts/` + `schemas/` | prompt + JSON Schema บังคับ structured output | MCP server โหลดไปใช้ |
| **Knowledge** | `docs/` + `templates/` | playbook + goal templates | คู่มือ + few-shot |

ข้อมูล output ของแต่ละโปรเจกต์ (`raw/`, `clean/`, `micro_facts/`, `output/`) **ไม่เก็บใน repo นี้** —
repo นี้คือ *เครื่องมือ* ไม่ใช่ *ผลลัพธ์*

---

## โครงสร้าง

```
MennzLore/
├── engine/                       # Python deterministic — canonical
│   ├── lore_models.py            # Pydantic schemas + cross-field validation (กัน hallucination)
│   ├── merge_to_micro_facts.py   # รวม 3-pass output → micro_facts/*.json
│   ├── assemble_generic.py       # Phase 7 — ประกอบ master_lorebook_full.md
│   ├── assemble_production_generic.py  # Phase 9 — image prompts + shot list
│   └── chart_render_generic.py   # Phase 10 — แผนที่ SVG + route network
├── prompts/                      # แกน LLM (Phase 1-6)
│   ├── pass11_architect_prompt.md    # ฉาก + เหตุการณ์หลัก
│   ├── pass12_profiler_prompt.md     # ตัวละคร + พฤติกรรม + ไอเทม + บทสนทนา
│   ├── pass13_chronicler_prompt.md   # เชื่อมข้ามตอน + lore discoveries
│   ├── pass2_sliding_window_prompt.md
│   ├── sa_combined_prompt.md
│   └── sa_lore_prompt.md
├── schemas/                      # JSON Schema (gen จาก lore_models) — สำหรับ Structured Outputs API
│   ├── architect.schema.json
│   ├── profiler.schema.json
│   ├── chronicler.schema.json
│   └── micro_facts_final.schema.json
├── templates/                    # goal templates สำหรับ delegate_task (sub-agent)
├── examples/                     # ตัวอย่าง output จริง (1 ตอน) เป็น reference
└── docs/
    ├── PIPELINE.md               # playbook ทีละ phase (Phase 1-10)
    ├── ENGINE.md                 # CLI reference ของ engine scripts
    └── MCP_DESIGN.md             # แผนแปลง pipeline → MCP server
```

---

## Quick Start

```bash
pip install -r requirements.txt
```

รัน pipeline ตามลำดับ — ดู [`docs/PIPELINE.md`](docs/PIPELINE.md) สำหรับรายละเอียดแต่ละ phase

Engine scripts ทุกตัวรับ `<project_dir> [prefix]` แบบเดียวกัน:

```bash
python engine/assemble_generic.py            <project_dir> [prefix]   # Phase 7
python engine/assemble_production_generic.py <project_dir> [prefix]   # Phase 9
python engine/chart_render_generic.py        <project_dir> [prefix]   # Phase 10
```

ดู [`docs/ENGINE.md`](docs/ENGINE.md) สำหรับ input/output ของแต่ละสคริปต์

---

## ปลายทาง: MCP Server

ระบบนี้มี LLM เป็นแกนหลัก — เป้าหมายคือห่อทุก phase เป็น **MCP tools** เพื่อให้ LLM client ตัวไหนก็เรียกได้
ดูแผนเต็มที่ [`docs/MCP_DESIGN.md`](docs/MCP_DESIGN.md)

---

*Maintained by @mgprona — private*
