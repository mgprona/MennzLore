# Engine Reference

## `fetch_raw.py`  — Phase 1

```bash
python engine/fetch_raw.py "<title>" "<author>" [base_dir]
```

ค้นหา title+author ผ่าน gutendex → ดึง raw text (PG-19 ก่อน, fallback Gutenberg) → สร้างโครงโปรเจกต์

| output | เนื้อหา |
|:-------|:--------|
| `raw/<prefix>_full.txt` | raw text ทั้งเล่ม (ยังไม่แบ่งตอน) |
| `verification/<prefix>_source.json` | provenance: id, title, authors, source, url, fetched_at |

- `base_dir` — โฟลเดอร์ที่จะสร้าง `<prefix>/` ใต้ (default = cwd)
- `prefix` สร้างอัตโนมัติจาก `<title-slug>-<author-last>` เช่น `voodoo-planet-norton`
- ถ้าหนังสือมีหลาย edition ใน Gutenberg จะเลือก edition ที่มี `text/plain` ที่สมบูรณ์ที่สุดโดยอัตโนมัติ

---

Engine scripts ทั้งหมดเป็น **deterministic** (ไม่เรียก LLM) รับ `<project_dir> [prefix]` แบบเดียวกัน
ถ้าไม่ระบุ `prefix` จะใช้ชื่อโฟลเดอร์ของ `project_dir`

> ทุกตัว project-agnostic แล้ว — ไม่มี path hardcode ส่ง project เข้าไปได้เลย

---

## `split_chapters.py`  — Phase 2

```bash
python engine/split_chapters.py <project_dir> [prefix]
```

detect chapter headings ใน raw text → แบ่งตอน → เขียน `clean/<prefix>_EP###.txt`

รองรับ pattern:
- `Chapter N` / `Chapter One` / `Part II`
- Roman numerals standalone (`I`, `II`, `III`...)
- ต้องมี blank line ทั้งบนและล่าง heading (กัน false positive กลาง prose)

| output | เนื้อหา |
|:-------|:--------|
| `clean/<prefix>_EP###.txt` | text ต่อตอน cleaned (blank lines collapse) |
| `verification/<prefix>_chapters.json` | manifest: ep_id, heading, line_start, char_count |

---

## `lore_models.py`

Pydantic schemas สำหรับทั้ง pipeline — **source of truth ของ data shape**

| Model | ใช้ที่ |
|:------|:-------|
| `ArchitectOutput` | Pass 1.1 |
| `ProfilerOutput` | Pass 1.2 |
| `ChroniclerOutput` | Pass 1.3 |
| `MicroFactsFinal` | merged final + cross-field validation |

Helpers สร้าง JSON Schema สำหรับ Structured Outputs API:
```python
from lore_models import get_architect_schema, get_profiler_schema, get_chronicler_schema
```

`MicroFactsFinal.@model_validator` ตรวจว่า `in_scene_id` ทุกตัว (จาก key_plot_points,
character_behaviors, items, dialogues, connections, discoveries) อ้างถึง `scene_id`
ที่มีจริงใน `scene_details` — raise `ValueError("HALLUCINATION: ...")` ถ้าไม่ตรง

regen schemas เมื่อแก้ models:
```bash
python -c "import sys; sys.path.insert(0,'engine'); import lore_models as m, json; \
[open(f'schemas/{n}.schema.json','w',encoding='utf-8').write(json.dumps(s.model_json_schema(),ensure_ascii=False,indent=2)) \
 for n,s in [('architect',m.ArchitectOutput),('profiler',m.ProfilerOutput),('chronicler',m.ChroniclerOutput),('micro_facts_final',m.MicroFactsFinal)]]"
```

---

## `merge_to_micro_facts.py`  — Phase 4 merge

```bash
python engine/merge_to_micro_facts.py <prefix> <ep_num> [base_dir]
```

รวม output ของ 3 pass (architect + profiler + chronicler) ของตอนหนึ่ง →
`micro_facts/<prefix>_EP<nnn>_micro_facts.json` พร้อม validate ผ่าน `MicroFactsFinal`

- `prefix` — ชื่อโปรเจกต์ (เช่น `voodoo-planet-qa`)
- `ep_num` — เลขตอน
- `base_dir` — โฟลเดอร์โปรเจกต์ (optional, default = cwd)

---

## `assemble_generic.py`  — Phase 7

```bash
python engine/assemble_generic.py <project_dir> [prefix]
```

ประกอบทุก intermediate → `output/<prefix>_master_lorebook_full.md` (ไฟล์เดียวที่อยู่รอด)

สร้าง section: Metadata, Table of Contents, Name Map Table, Timeline Table,
Foreshadowing Cross-Reference, Character Arc Table, Entity Directory, Visual Style,
Storyboard, Chapter Summaries

---

## `assemble_production_generic.py`  — Phase 9

```bash
python engine/assemble_production_generic.py <project_dir> [prefix]
```

อ่าน micro_facts + entities → `output/production/`:

| ไฟล์ | เนื้อหา |
|:-----|:--------|
| `scene_image_prompts.json` | prompt ต่อฉาก (ป้อน Midjourney/SD ได้เลย) |
| `cinematography_shot_list.json` | shot list |
| `visual_style_bible.json` | สไตล์ภาพรวม |
| `entity_registry.json` | ทะเบียนตัวละคร/prop |
| `production_manifest.json` | manifest |

infer art style / era จาก `entities/visual_style.md` อัตโนมัติ

---

## `chart_render_generic.py`  — Phase 10

```bash
python engine/chart_render_generic.py <project_dir> [prefix]
```

อ่าน locations จาก micro_facts → `output/spatial/`:

| ไฟล์ | เนื้อหา |
|:-----|:--------|
| `location_geography.json` | พิกัด + terrain |
| `route_network.json` | เส้นทางเดินทางของตัวละคร |
| `chart_map_skeleton.svg` | แผนที่ SVG |

ใช้ haversine + lat/lon → canvas projection จัด terrain จากชื่อสถานที่
