# Pipeline Playbook (Phase 1-10)

ลำดับการทำงานเต็ม — **รันให้จบทุก phase เสมอ** อย่าหยุดที่ Phase 7

แต่ละ phase ระบุว่าเป็นงานของ **LLM** (ต้องใช้โมเดลคิด) หรือ **Engine** (สคริปต์ deterministic)

---

## ภาพรวม

```
raw text → Clean → Global Lore → 3-Pass Analysis → Merge → Validate → Assemble → Production → Map
```

| Phase | ชื่อ | ประเภท | Output |
|:------|:-----|:-------|:-------|
| 1 | Acquire | **Engine** | `raw/<prefix>_full.txt`, `verification/<prefix>_source.json` |
| 2 | Split & Clean | **Engine** | `clean/<prefix>_EP###.txt`, `verification/<prefix>_chapters.json` |
| 3.1 | Global Lore + Name Map | LLM (full book) | `verification/global_lore.json`, `name_map.json`, `timeline_framework.json`, `chapter_appearance.json` |
| 3.2 | Auto-Verify | Engine | report ชื่อที่หาย (cross-ref กับ raw) |
| 3.3 | Chapter Data Fallback | Engine | timeline + appearance (ถ้า LLM พลาด) |
| 4-P1 | Micro-Facts (3-Pass) | LLM (ต่อตอน) | `micro_facts/*.json` |
| 4-P2 | Sliding Window Synthesis | LLM (5 ตอน/batch) | `analysis/pass2/batch_*.json` |
| 5-6 | Validate + Foreshadow Linking | LLM/Engine | verification flags |
| 7 | Assemble | **Engine** | `output/master_lorebook_full.md` |
| 8 | Finalize | Engine | stats, metadata |
| 9 | Production Render | **Engine** | image prompts, shot list, visual style bible |
| 10 | Spatial Render | **Engine** | แผนที่ SVG, route network, geography |

---

## Phase 1 — Acquire (Engine)

```bash
python engine/fetch_raw.py "<title>" "<author>" [base_dir]
```

1. ค้นหาหนังสือจาก **gutendex** (Gutenberg API) ด้วย title + author
2. ดึงจาก **PG-19** (`train/validation/test/<id>.txt`) ก่อน — เฉพาะเล่มก่อนปี 1919
3. ถ้าไม่มีใน PG-19 → fallback ดึงจาก **Project Gutenberg** (`text/plain` URL จาก formats)
4. สร้างโครงโปรเจกต์อัตโนมัติ: prefix = `<title-slug>-<author-last>`, เขียน `raw/<prefix>_full.txt`
5. บันทึก provenance → `verification/<prefix>_source.json`

> การแบ่งตอน → `clean/<prefix>_EP###.txt` อยู่ใน **Phase 2** ไม่ใช่ Phase 1

---

## Phase 2 — Split & Clean (Engine)

```bash
python engine/split_chapters.py <project_dir> [prefix]
```

1. strip Gutenberg boilerplate (`*** START/END OF THE PROJECT GUTENBERG EBOOK ***`)
2. detect chapter headings (`Chapter N`, Roman numerals) — ต้องมี blank line บน-ล่าง
3. แบ่งตอน → `clean/<prefix>_EP###.txt` (3 หลัก, zero-padded)
4. collapse blank lines เกิน 2 บรรทัด
5. เขียน manifest → `verification/<prefix>_chapters.json`

> EP numbering เริ่มที่ EP001 เสมอ ทุก phase ปลายน้ำใช้ format นี้

---

## Phase 4 — 3-Pass Analysis (หัวใจ LLM)

แต่ละตอนผ่าน 3 pass เรียงกัน โดย output ของ pass ก่อนหน้าเป็น input ของ pass ถัดไป
ทุก entry ผูกกับ `scene_id` เพื่อให้ตรวจสอบย้อนได้ (กัน hallucination)

| Pass | บทบาท | Prompt | Schema | จับอะไร |
|:-----|:------|:-------|:-------|:--------|
| 1.1 | **Architect** | `prompts/pass11_architect_prompt.md` | `schemas/architect.schema.json` | ฉาก (`scene_details`) + เหตุการณ์หลัก (`key_plot_points`) |
| 1.2 | **Profiler** | `prompts/pass12_profiler_prompt.md` | `schemas/profiler.schema.json` | ตัวละคร, พฤติกรรม, ไอเทม, บทสนทนา |
| 1.3 | **Chronicler** | `prompts/pass13_chronicler_prompt.md` | `schemas/chronicler.schema.json` | เชื่อมข้ามตอน + lore discoveries |

**Merge:** รวม 3 pass → `micro_facts/<prefix>_EPxxx_micro_facts.json`

```bash
python engine/merge_to_micro_facts.py <prefix> <ep_num> [base_dir]
```

`MicroFactsFinal` มี `@model_validator` ตรวจว่า `in_scene_id` ทุกตัวอ้างถึงฉากที่มีจริง —
ถ้า LLM hallucinate scene reference จะ raise error ทันที (ดู `engine/lore_models.py`)

### กฎสำคัญของ prompt (อย่าแก้)
- **ชื่อตัวละคร = ชื่อล้วน** ห้ามมีวงเล็บ `(mentioned)`, `(deceased)`, `(alias)`
- ใช้ชื่อ field ตรงเป๊ะ: `key_plot_points` (ไม่ใช่ `events`), `scene_details` (ไม่ใช่ `scenes`)
- ไม่มี `null` — array ว่างใช้ `[]`

---

## Phase 4-P2 — Sliding Window Synthesis

วิเคราะห์ทีละ batch (5 ตอน) เพื่อจับ character arc + foreshadowing ข้ามตอน
Prompt: `prompts/pass2_sliding_window_prompt.md` → output `analysis/pass2/batch_*.json`

---

## โครงไดเรกทอรีของ "โปรเจกต์" (ไม่ใช่ของ repo นี้)

แต่ละนิยายที่รันสร้างโฟลเดอร์แยก เช่น `voodoo-planet-qa/`:

```
<project>/
├── raw/            # Phase 1 — ข้อความดิบ
├── clean/          # Phase 2 — ทำความสะอาดแล้ว
├── verification/   # Phase 3 — global lore, name map, timeline
├── micro_facts/    # Phase 4-P1 — 3-pass merged ต่อตอน
├── analysis/pass2/ # Phase 4-P2 — sliding window
├── entities/       # characters, locations, concepts, visual_style, storyboard
├── chapters/       # สรุปต่อตอน
├── output/         # Phase 7/9/10 — master_lorebook_full.md, production/, spatial/
└── <prefix>_pipeline_state.json
```

> `master_lorebook_full.md` = ไฟล์เดียวที่อยู่รอด ทุกอย่างอื่นเป็น intermediate ลบได้

---

## Working Style

- **อย่าถาม — ลงมือ** ถ้าผู้ใช้บอก "continue/analyze" ให้เดา step ที่สมเหตุสมผลที่สุดแล้วทำเลย
- **รันจบทุก phase** ห้ามหยุดที่ Phase 7 — ไป Phase 9 + 10 ทุกครั้ง
- Phase 4 ใช้ delegate_task สำหรับ sub-agent (SA1 Combined + SA2 Lore) — ระวัง rate limit ของ free model (HTTP 429 หลัง 3-6 calls); ถ้าติด สลับไป Main Agent direct write
