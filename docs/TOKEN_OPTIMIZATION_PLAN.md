# MennzLore Token Optimization Plan

> **Status:** Draft — pending review  
> **Target:** v5.1  
> **Goal:** ลด token consumption 50-60% โดยไม่เสีย detail ของ micro_facts

---

## Problem

Pipeline ปัจจุบัน extract ข้อมูลชุดเดียวกันด้วย LLM ซ้ำ 2-3 รอบ:

| Data | Extracted in | Duplication |
|---|---|---|
| Character names | Phase 3.1 + Phase 4 Arch + Phase 4 Prof | **3×** |
| Character traits | Phase 3.1 + Phase 4 Prof | **2×** |
| Locations | Phase 3.1 + Phase 4 Arch | **2×** |
| Events/timeline | Phase 3.1 + Phase 4 Arch + Phase 4 Chron | **3×** |
| Cross-chapter connections | Phase 4 Chron + Phase 4-P2 Sliding Window | **2×** |

สำหรับนิยาย 39 ตอน (~200K words):

| Metric | Current | Target |
|---|---|---|
| Phase 3.1 tokens | ~240K | ~60K |
| Phase 4 LLM calls | 117 (3×39) | 78 (2×39) |
| Phase 4-P2 calls | ~8 batches | 0 |
| **Total LLM calls** | **~125** | **~78** |
| **Total tokens** | **~1,500K** | **~700K** |

---

## Proposed Changes

### Change 1: Phase 3.1 → Engine-First (75% token reduction)

**Current:** LLM reads ALL chapters → extracts 4 JSON artefacts

**Proposed:** Split into Engine (deterministic) + LLM (reading sample only)

```
Phase 3.1a (ENGINE — zero tokens):
  ├── grep chapter headings → book structure (BOOK I/II/III)
  ├── grep `Mr\.?|Mrs\.?|Captain|Sir|Miss|Dr\.?` patterns → name_map candidates
  ├── grep character mentions per chapter → chapter_appearance
  └── write name_map + chapter_appearance + timeline_framework skeleton

Phase 3.1b (LLM — ~60K tokens):
  ├── read ONLY 2-3 key chapters (first, turning point, last)
  ├── extract: book_metadata, genre, main_theme, narrative_device, pov
  ├── extract: key character relationships (from sample)
  └── merge into global_lore
```

**Quality guard:** Phase 4 Profiler will extract detailed character behaviors per chapter anyway. Global Lore only needs the OVERVIEW — character arcs and deep traits come from micro_facts.

**Files to modify:**
- `engine/phase3_global_lore.py` — split `build_global_lore_prompt()` into engine-only + LLM-sample paths
- `mcp_server/server.py` — update `extract_global_lore` prompt to accept `sample_only=true`

---

### Change 2: Merge 3-Pass → 2-Pass (33% call reduction)

**Current:** Architect → Profiler → Chronicler = 3 LLM calls per chapter

**Proposed:** Extract → Cross-Reference = 2 LLM calls per chapter

```
Pass 1 — EXTRACT (merged Architect + Profiler):
  Input:  chapter_text + name_map + global_lore_summary
  Output: scenes + characters + behaviors + items + dialogue + character_states
  Schema: same as current sa_combined_prompt.md (already exists)

Pass 2 — CROSS-REF (merged Chronicler + Sliding Window):
  Input:  Pass 1 output + previous 2 chapters' summaries + global_lore_excerpt
  Output: cross_chapter_connections + lore_discoveries
  Schema: same as current pass13_chronicler_prompt.md
```

**Why this works:** `prompts/sa_combined_prompt.md` already proves that Architect+Profiler can merge into one call. The schema covers ALL fields from both passes:
- `scene_details` (from Architect)
- `key_plot_points` (from Architect)
- `characters_present` (from Profiler)
- `character_behaviors` (from Profiler)
- `items_of_interest` (from Profiler)
- `dialogue_summaries` (from Profiler)
- `character_states` (from Profiler)

The separate 3-Pass was designed for weaker models that couldn't produce complex nested JSON reliably. Modern models (GPT-4, Claude 3.5, DeepSeek v4) handle combined schema fine.

**Quality guard:** `MicroFactsFinal.@model_validator` still checks `in_scene_id` references → hallucination protection unchanged.

**Files to modify:**
- `prompts/pass11_architect_prompt.md` → merge into sa_combined
- `prompts/pass12_profiler_prompt.md` → merge into sa_combined
- `prompts/sa_combined_prompt.md` → make this the DEFAULT (rename to `pass1_extract_prompt.md`)
- `prompts/pass13_chronicler_prompt.md` → add `previous_chapters_summary` input
- `mcp_server/server.py` → remove `analyze_architect` + `analyze_profiler` prompts, rename `analyze_chronicler`

---

### Change 3: Eliminate Phase 4-P2 Sliding Window (100% reduction)

**Current:** Separate LLM pass reading 5-chapter batches of micro_facts

**Proposed:** Fold into Pass 2 (Cross-Ref) by feeding previous-chapter summaries

Instead of:
```
Sliding Window: read micro_facts EP001-EP005 → find arcs
Sliding Window: read micro_facts EP006-EP010 → find arcs
...
```

Do:
```
Pass 2 (EP005): input = EP005 Pass1 output + EP003+EP004 summaries
Pass 2 (EP006): input = EP006 Pass1 output + EP004+EP005 summaries
```

Each Pass 2 already has access to the current chapter's full extraction. Adding 2-3 previous chapter summaries gives it enough context to track character arcs, foreshadowing, and recurring motifs — without a separate batch-processing system.

**Quality guard:** The previous-chapter summaries are auto-generated from each chapter's `key_plot_points` (already extracted in Pass 1). No new LLM extraction needed.

**Files to modify:**
- Delete: `prompts/pass2_sliding_window_prompt.md` (or archive as `prompts/_archived/`)
- Remove: `synthesize_window` MCP prompt from server.py

---

## Implementation Sequence

| Step | What | Risk | Tokens Saved |
|---|---|---|---|
| **1** | Rename `sa_combined` → `pass1_extract` as default | Low — already tested | 33% of Phase 4 |
| **2** | Add `previous_chapters_summary` to Chronicler prompt | Low — additive change | Enables Step 3 |
| **3** | Remove Sliding Window | Medium — verify on 3-novel test | 100% of Phase 4-P2 |
| **4** | Split Phase 3.1 into Engine+LLM | Medium — affects name_map quality | 75% of Phase 3.1 |
| **5** | Remove `analyze_architect` + `analyze_profiler` MCP prompts | Low — cleanup | 0 (DX improvement) |

**Verification gate:** After each step, run the 3-novel stress test (Burroughs PG #62, Burks PG #29416, Doyle PG #244). Compare master_lorebook quality (character count, event count, hallucination rate) with baseline.

---

## What Does NOT Change

- **Name Map reference in every Phase 4 prompt** — hallucination protection unchanged
- **`MicroFactsFinal.@model_validator`** — cross-field scene_id validation unchanged
- **Phase 7-16 Engine pipeline** — deterministic, no tokens anyway
- **Saga Mode + YouTube pipeline** — unaffected

---

## Risk: What Could Degrade

| Risk | Mitigation |
|---|---|
| Combined prompt too complex → LLM misses fields | Keep schema identical to sa_combined (already proven); add `required` field validation |
| Previous-chapter summaries too short to catch arcs | Auto-summary = first 3 `key_plot_points` + character list; test on Doyle (complex timeline) |
| Engine-only name_map misses aliases | Phase 3.1b LLM step can suggest aliases from sample chapters; merge with grep results |
| Global Lore theme/genre less accurate from sample-only | Phase 7 Assemble will derive theme from micro_facts 39 chapters → more granular anyway |

---

## Rollback Plan

All changes are prompt-level (not engine). If quality degrades:
1. Revert prompt files from git
2. Re-enable `analyze_architect` + `analyze_profiler` MCP prompts
3. Old 3-Pass path still works because engine code unchanged

---

*Drafted: 2026-06-10*
*Target release: v5.1*
