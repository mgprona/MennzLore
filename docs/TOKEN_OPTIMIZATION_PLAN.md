# MennzLore Token Optimization Plan v2

> **Status:** Draft v2 — revised 2026-06-10  
> **Target:** v5.1  
> **Goal:** ลด token consumption ~50% โดยไม่เสียความสามารถในการ detect disguised names และไม่ลดทอนคุณภาพ micro_facts

---

## หลักการออกแบบ (Design Principles)

ก่อนตัดสินใจเปลี่ยนอะไร ต้องเข้าใจก่อนว่า **งานไหน LLM ทำแทน engine ไม่ได้:**

| งาน | Engine ทำได้? | LLM จำเป็น? |
|---|---|---|
| หาชื่อ `Mr./Captain/Sir` จาก regex | ✅ | ❌ |
| นับจำนวนครั้งที่ชื่อปรากฏต่อตอน | ✅ | ❌ |
| ตรวจจับ chapter heading จาก pattern | ✅ | ❌ |
| รู้ว่า `Spyglass` เป็นชื่อตัวละคร ไม่ใช่สิ่งของ | ❌ | ✅ |
| รู้ว่า `Heans = Sir William = Sir William Heans` | ❌ | ✅ |
| แยกแยะ mood ของ scene (tense/comic/tragic) | ❌ | ✅ |
| เข้าใจ foreshadowing ข้ามตอน | ❌ | ✅ |
| รู้ว่า dialogue นี้ประชดหรือจริงใจ | ❌ | ✅ |

**กฎเหล็ก:** งานที่ต้องใช้ **ความเข้าใจภาษา** = LLM เท่านั้น — ห้ามย้ายไป engine

---

## สิ่งที่ pipeline ปัจจุบันทำซ้ำซ้อน

LLM อ่านข้อมูลชุดเดียวกันหลายรอบเพื่อ extract ข้อมูลที่ทับซ้อนกัน:

| ข้อมูล | ถูก extract ที่ไหน | ซ้ำกี่รอบ |
|---|---|---|
| Character names | Phase 3.1 + Phase 4 Architect + Phase 4 Profiler | **3×** |
| Character traits & descriptions | Phase 3.1 + Phase 4 Profiler | **2×** |
| Locations | Phase 3.1 + Phase 4 Architect | **2×** |
| Events & timeline | Phase 3.1 + Phase 4 Architect + Phase 4 Chronicler | **3×** |
| Cross-chapter connections | Phase 4 Chronicler + Phase 4-P2 Sliding Window | **2×** |
| Chapter text (raw input) | Phase 4 Architect + Phase 4 Profiler | **2× ต่อตอน** |

**ตัวเลขสำหรับนิยาย 39 ตอน (~200K words):**

| | Current | Target |
|---|---|---|
| Phase 3.1 tokens | ~240K | ~120K |
| Phase 4 LLM calls | 117 (3×39) | 78-97 (adaptive 2-3 pass) |
| Phase 4-P2 calls | ~8 batches | 0 |
| Total LLM calls | ~125 | ~78-97 |
| Total tokens | ~1,500K | ~750K |

---

## Change 1: Phase 3.1 — LLM ยังอ่านทั้งเล่ม แต่ extract แค่ชื่อ

### ปัญหาที่ต้องแก้

Global Lore ปัจจุบันขอให้ LLM extract 4 อย่างจาก text ทั้งเล่ม:
1. Characters (ชื่อ + description + arc + relationships + visual profile)
2. Timeline (เหตุการณ์สำคัญ + chapter summaries)
3. Chapter appearance (ตัวละครโผล่ตอนไหน)
4. World building & motifs

**ของข้อ 2-4** Phase 4 ทำซ้ำอยู่แล้วและละเอียดกว่า:
- Timeline → Architect ทำ `key_plot_points` ต่อตอน granular กว่า
- Chapter appearance → grep จาก name_map ที่มีอยู่แล้ว แม่น 100%
- World building → Chronicler ทำ `lore_discoveries` ต่อตอน

**ของข้อ 1** มีส่วนที่ Phase 4 ทำซ้ำ (descriptions, visual profile) และส่วนที่ **LLM เท่านั้นที่ทำได้** (detect ชื่อปลอมอย่าง `Spyglass`)

### วิธีแก้

**Phase 3.1a — ENGINE (0 tokens):**
```
Input:  clean/*.txt ทั้งหมด
Output: name_candidates (จาก regex) + chapter_appearance_skeleton + book_structure
```
- grep `Mr\.?|Mrs\.?|Captain|Sir|Miss|Dr\.?|Lady|Lord|Colonel|Major` → พบ ~80% ของชื่อ
- grep capitalized words ที่ปรากฏ ≥3 ครั้ง → candidate pool
- detect chapter headings → book_structure (BOOK I/II/III, ตอนละกี่ chapter)

**Phase 3.1b — LLM (อ่านทั้งเล่ม แต่ prompt เล็กลง 60%):**
```
Input:  clean/*.txt ทั้งหมด + name_candidates จาก engine
Prompt: "Here are known character names found by pattern matching: [engine list].
         Read ALL chapters and identify:
         1. Any MISSING character names — especially disguised names (objects, 
            nicknames, titles used as names). Flag them with the chapter where 
            they first appear.
         2. All aliases for each character (e.g. 'Heans' = 'Sir William' = 
            'Sir William Heans').
         3. Which episodes each character appears in.
         Do NOT write descriptions, arcs, or relationships. Names and 
         aliases ONLY. Engine will handle the rest."
Output: name_map (canonical + aliases + episodes) + chapter_appearance
Tokens: ~120K (vs ~240K เดิม — เพราะไม่ต้อง extract descriptions)
```

**Phase 3.1c — ENGINE (0 tokens):**
```
Input:  name_map + book_structure
Output: global_lore skeleton + timeline_framework skeleton
```
- `book_metadata` → จาก source.json + chapter headings
- `timeline_framework` → จาก book_structure (derive book/chapter structure)
- `global_lore.characters[*].description` → เว้นว่าง (Phase 4 Profiler จะเติม)
- `global_lore.characters[*].character_arc` → เว้นว่าง (Phase 4 Cross-Ref จะเติม)

### Why this preserves quality

| Concern | Answer |
|---|---|
| "Spyglass" จะถูก detect ไหม? | ✅ LLM ยังอ่านทั้งเล่ม — เห็น "Spyglass said..." → รู้ว่านี่คือตัวละคร |
| Description characters หายไป? | ไม่หาย — ย้ายไป Phase 4 Profiler ซึ่ง extract ต่อตอน ละเอียดกว่า |
| Name map quality ลดลง? | ดีขึ้น — LLM focus แค่ชื่ออย่างเดียว ไม่ต้องแบ่ง attention ไปเขียน description |
| Timeline หายไป? | ไม่หาย — derive จาก chapter headings (engine) แม่นยำกว่า LLM เดา |

### Edge cases

| Edge case | Handling |
|---|---|
| นิยายที่ไม่มี `Mr./Captain` เลย (ทุกคนเรียกชื่อเปล่า) | Engine candidates = เฉพาะ capitalized words; LLM batch จะ catch ส่วนที่เหลือ |
| ตัวละครถูกเรียก 3-4 ชื่อสลับกันทั้งเล่ม | LLM batch อ่านทั้งเล่ม → มองเห็น pattern การสลับชื่อ |
| ชื่อตัวละครเป็นภาษาต่างประเทศ (ไม่เข้า regex) | LLM batch คือ safety net — ตรวจจับจาก context ว่าคำนี้คือชื่อคน |
| นิยายสั้นมาก (<10 chapters) | Phase 3.1b ต้นทุนต่ำอยู่แล้ว — ใช้ full prompt ได้เลย ไม่ต้อง batch |

### What Could Go Wrong

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM batch มองข้ามชื่อปลอมเพราะ focus แค่ชื่อ | Low | HIGH — เสียตัวละคร | Prompt ให้ LLM flag "any word used as a name, even if it looks like an object" |
| Engine grep ได้ชื่อซ้ำ/สะกดผิด | Medium | LOW | LLM batch จะ canonicalize + deduplicate |
| Chapter appearance จาก grep คลาดเคลื่อน (เจอชื่อในความหมายอื่น) | Medium | LOW | LLM batch verify + Phase 3.2 auto_verify_names cross-check |

---

## Change 2: Phase 4 — Adaptive 2/3-Pass

### ปัญหาที่ต้องแก้

3-Pass (Architect → Profiler → Chronicler) อ่าน chapter text ซ้ำ:
- Architect อ่าน chapter text → extract scenes + plot points
- Profiler อ่าน chapter text **เดิม** → extract characters + behaviors + items
- Chronicler อ่าน Architect+Profiler output → cross-chapter connections

SA Combined path (มีอยู่แล้วใน repo) ทำ Architect+Profiler ใน call เดียว — พิสูจน์ว่า combine ได้

แต่มีเคสที่ combine แล้วคุณภาพตก: **chapter ที่ยาวมาก (>15KB)** — LLM ต้องทำสองอย่างพร้อมกัน (structure scenes + profile characters) ใน prompt เดียว โอกาสพลาดสูงขึ้น

### วิธีแก้: Adaptive Threshold

```
ถ้า chapter_text < 15,000 chars:
  → 2-Pass (SA Combined path)
     Pass 1: EXTRACT — chapter_text + name_map → scenes + characters + behaviors + items + dialogue
     Pass 2: CROSS-REF — Pass1 output + prev_chapters_summary → connections + lore discoveries

ถ้า chapter_text >= 15,000 chars:
  → 3-Pass (เดิม)
     Pass 1: Architect — chapter_text → scenes + plot points
     Pass 2: Profiler — chapter_text + scenes → characters + behaviors + items
     Pass 3: Chronicler — Architect+Profiler output + prev_chapters_summary → connections
```

**สำหรับ heans (39 chapters):**
- <15KB: ~25 chapters → 2-Pass = 50 calls
- ≥15KB: ~14 chapters → 3-Pass = 42 calls
- Total: **92 calls** (vs 117 calls เดิม = **ลด 21%**)

**สำหรับนิยายทั่วไป (chapter สั้น):**
- ส่วนใหญ่ <15KB → 2-Pass เกือบทั้งหมด = **ลด ~33%**

### ทำไม SA Combined ใช้ได้ (ไม่ใช่ของด้อยคุณภาพ)

`prompts/sa_combined_prompt.md` (v3.7) ถูกออกแบบมาหลัง 3-Pass — เป็น evolution ไม่ใช่ fallback:

- Schema ครอบคลุม **ทุก field** ที่ Architect+Profiler มี:
  - `scene_details` ← Architect
  - `key_plot_points` ← Architect  
  - `characters_present` ← Profiler
  - `character_behaviors` ← Profiler
  - `items_of_interest` ← Profiler
  - `dialogue_summaries` ← Profiler
  - `character_states` ← Profiler
- บวกเพิ่ม `character_states` ที่ 3-Pass ไม่มี

ที่ผ่านมาใช้ SA Combined เฉพาะตอน rate limited — ไม่เคยมีปัญหาคุณภาพตก

### การ merge Chronicler + Sliding Window

แทนที่จะมี Sliding Window แยกต่างหาก (อ่าน 5 chapters/batch → หา cross-chapter arcs):

```
Pass 2 (CROSS-REF) ทุกตอนได้รับ:
  - Pass1 output ของตอนปัจจุบัน (scenes, characters, behaviors, items)
  - summary ของ 2-3 ตอนก่อนหน้า (auto-generated จาก key_plot_points)
  - global_lore_excerpt (name_map + timeline)
  
→ LLM เห็นภาพต่อเนื่องโดยไม่ต้องมี batch processing แยก
```

**Auto-summary สร้างยังไง (0 tokens):**
```python
summary = {
    "chapter": "EP005",
    "heading": "CHAPTER V. ANOTHER BLACK STRING",
    "key_events": [first 3 key_plot_points],  # จาก Pass1 output
    "characters_present": [...],               # จาก Pass1 output
    "new_characters_introduced": [...],        # เทียบกับ name_map
}
# ความยาว ~500 chars ต่อตอน — เล็กมากเทียบกับ chapter text
```

### Edge cases

| Edge case | Handling |
|---|---|
| Chapter แรก (EP001) — ไม่มี previous chapters | summary = empty → LLM รู้ว่านี่คือตอนแรก |
| Chapter ที่ตัวละครใหม่โผล่ครั้งแรก | auto-summary flag `new_characters_introduced` → Cross-Ref รู้ว่านี่คือ first appearance |
| Chapter ที่ไม่มี dialogue เลย | auto-summary ยาวพอ ๆ กับ chapter ที่มี dialogue — `key_plot_points` ยังมี |
| นิยายที่ timeline กระโดด (flashback) | auto-summary ไม่ cover — แต่ Chronicler prompt มี `global_lore_excerpt` + timeline_framework อยู่แล้ว |

### What Could Go Wrong

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 2-Pass on large chapter → LLM output ครึ่ง ๆ กลาง ๆ | Medium | MED | Threshold ป้องกัน — chapters >15KB ใช้ 3-Pass |
| Auto-summary สั้นเกิน → Cross-Ref จับ arc ไม่ได้ | Low | MED | 3 `key_plot_points` + character list = พอสำหรับ LLM เข้าใจ context |
| Summary จากตอนที่ LLM hallucinate → propagate error | Medium | HIGH | `MicroFactsFinal.@model_validator` ตรวจ scene_id references ก่อนใช้เป็น summary |

---

## Change 3: Pipeline Architecture — ทำไมต้อง LLM แบก

นี่ไม่ใช่ optimization โดยตรง แต่เป็น **กรอบคิด** ที่อธิบายว่าทำไม optimization ต้องระวัง:

```
┌─────────────────────────────────────────────────┐
│                  MENNZLORE                       │
│                                                  │
│  ┌──────────┐    ┌──────────────────────────┐   │
│  │  ENGINE  │    │         LLM              │   │
│  │ (30%)    │    │        (70%)             │   │
│  │          │    │                           │   │
│  │ download │    │ detect "Spyglass" = name  │   │
│  │ split    │    │ Heans = Sir William       │   │
│  │ grep     │    │ mood = tense              │   │
│  │ merge    │    │ foreshadowing             │   │
│  │ validate │    │ character arc             │   │
│  │ render   │    │ lore discoveries          │   │
│  └──────────┘    └──────────────────────────┘   │
│       ▲                      ▲                   │
│       │                      │                   │
│   งานที่ถูก 100%          งานที่ผิดได้            │
│   ไม่มีวันผิด             ต้อง validate          │
└─────────────────────────────────────────────────┘
```

**Engine = ฐานรากที่แข็ง** — งาน mechanical ทั้งหมด
**LLM = สมองที่เข้าใจภาษา** — งานที่ต้องใช้ปัญญา

Optimization ที่ถูกต้องคือ:
- ✅ LLM ยังทำสิ่งที่มันทำได้คนเดียว — **ไม่ลด scope ความเข้าใจ**
- ✅ ลดเฉพาะส่วนที่ LLM ทำซ้ำหรือ engine ทำแทนได้
- ❌ NOT: ย้ายงานที่ต้องใช้ความเข้าใจภาษาไป engine

---

## Implementation Sequence

| Step | What | Risk | Tokens Saved | Verification |
|---|---|---|---|---|
| **1** | Add `previous_chapters_summary` generator (engine) | Low | 0 (enabler) | Unit test: summary length < 1000 chars |
| **2** | Update Chronicler prompt to accept summaries | Low | 0 (enabler) | Smoke test 1 chapter: output schema valid |
| **3** | Make SA Combined the DEFAULT for chapters <15KB | Low-Med | 21-33% of Phase 4 | Run 3-novel test, compare character count |
| **4** | Remove Sliding Window (fold into Cross-Ref) | Medium | 100% of Phase 4-P2 | Compare Conn-IDs before/after |
| **5** | Split Phase 3.1 into Engine+LLM (names-only prompt) | Medium | 50% of Phase 3.1 | Verify "Spyglass"-type names detected |
| **6** | Remove `analyze_architect` + `analyze_profiler` MCP prompts | Low | 0 (cleanup) | Old path still callable via direct prompt text |

**Verification gate after each step:** 3-novel stress test (PG #62 Burroughs, PG #29416 Burks, PG #244 Doyle) — compare:
- Character count (ห้ามลด)
- Event count (ห้ามลดเกิน 10%)
- Hallucination rate (`in_scene_id` validation errors)
- Disguised name detection (Doyle มี alias-heavy characters)

---

## What Does NOT Change

| Component | เพราะ |
|---|---|
| Name Map ในทุก Phase 4 prompt | Hallucination protection — LLM ต้องรู้ว่าใครเป็นใคร |
| `MicroFactsFinal.@model_validator` | Cross-field scene_id validation — ด่านสุดท้ายกัน hallucination |
| LLM อ่านทั้งเล่มใน Phase 3.1 | ต้องเห็น context ทั้งหมดถึงจะ detect disguised names |
| Phase 7-16 Engine pipeline | Deterministic — ไม่ใช้ LLM ตั้งแต่แรก |
| Saga Mode + YouTube pipeline | แยก architecture — unaffected |

---

## Rollback Plan

ทุก change เป็น **prompt-level** (ไม่แก้ engine logic):
1. Revert prompt files from git → กลับเป็น 3-Pass + full Global Lore ทันที
2. Old MCP prompts (`analyze_architect`, `analyze_profiler`) ยังอยู่ใน server.py (แค่ไม่เป็น default)
3. Engine code unchanged — `merge_to_micro_facts.py`, `assemble_generic.py` รับ input format เดิม

---

## Open Questions

1. **Threshold สำหรับ adaptive 2/3-Pass:** 15,000 chars — ควร calibrate จาก stress test จริง
2. **auto-summary format:** เอา `key_plot_points` 3 ตัวพอไหม หรือควร include `character_behaviors` ด้วย?
3. **Phase 3.1b batching:** นิยาย >50 chapters — ควร batch LLM calls หรือทำ single call? (prompt อาจใหญ่เกิน)
4. **Prompt caching:** MCP prompts ใช้ system/user separation ได้ไหม? ถ้าได้ — schema/rules ถูก cache → ประหยัด token อีก 20%

---

*Drafted: 2026-06-10 | Revised: 2026-06-10*
*Target release: v5.1*
