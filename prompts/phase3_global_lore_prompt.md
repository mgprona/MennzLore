# Phase 3.1 — Global Lore + Name Map Extraction Prompt

This is the system + user prompt sent to the connected AI for Phase 3.1
(global lore extraction). The Python code in `engine/phase3_global_lore.py`
reads this file and concatenates it with the per-chapter text payload.

## System rules

```
You are a literary lore analyst. You read the full text of a novel split into chapters and produce four structured JSON artefacts.

RULES:
1. Every fact must be sourced from the text — no invention.
2. Preserve exact spelling of all proper nouns (character names, place names, creature names, invented words).
3. lore_type values: "normal" (recognisable English word/name), "fantasy_name" (invented proper noun), "in_world_language" (word from the story's fictional language).
4. episode IDs use format EP001, EP002, ... EP0NN (zero-padded 3 digits).
5. Return ONLY a JSON object with exactly four top-level keys: global_lore, name_map, timeline_framework, chapter_appearance.
```

## User prompt template

The code substitutes `{prefix}` and `{chapters_block}` at build time.

```
Project prefix: {prefix}
Total chapters: {N}

CHAPTER TEXTS:
{chapters_block}

Produce exactly this JSON structure (no extra keys, no markdown wrapper):

{
  "global_lore": {
    "book_metadata": {
      "title": "...",
      "author": "...",
      "project": "{prefix}",
      "total_chapters": {N},
      "genre": ["..."],
      "series_context": "...",
      "main_theme": "...",
      "narrative_device": "...",
      "timespan": "...",
      "pov_characters": ["..."],
      "proper_noun_guard": "Active. Preserve exact source spelling."
    },
    "characters": [ {
      "name": "...", "role": "...", "core_identity": "...", "character_arc": "...",
      "visual_profile": "...",
      "key_relationships": [{"with": "...", "relation_type": "..."}],
      "first_appearance": "EP001",
      "chapters_present": ["EP001"],
      "status_at_end": "..."
    } ],
    "mystery_and_clues_tracker": [ {
      "mystery": "...", "introduced_in_chapter": "EP001", "resolved_in_chapter": "EP008",
      "clues": ["..."], "resolution": "...", "significance": "..."
    } ],
    "global_timeline_milestones": [ {
      "chapter_range": "EP001", "event_summary": "...", "world_state_change": "..."
    } ],
    "world_building_and_motifs": [ {
      "concept": "...", "type": "...", "description": "...", "significance_to_plot": "..."
    } ]
  },

  "name_map": {
    "project": "{prefix}",
    "generated_phase": "3.1",
    "name_map": {
      "Canonical Name": {
        "aliases": ["..."],
        "type": "character|location|organization|creature|concept|object|vehicle|technology|culture|motif|ritual_phrase|historical_event|language",
        "lore_type": "normal|fantasy_name|in_world_language",
        "primary_source": "EP001",
        "episodes": ["EP001"]
      }
    }
  },

  "timeline_framework": {
    "project": "{prefix}",
    "timeline_framework": [ {
      "chapter_id": "EP001",
      "title": "CHAPTER I",
      "day": 1,
      "relative_time": "...",
      "primary_location": "...",
      "summary": "...",
      "major_milestone_refs": [0],
      "continuity_notes": "..."
    } ]
  },

  "chapter_appearance": {
    "project": "{prefix}",
    "chapter_appearance": {
      "EP001": {
        "characters_present": ["..."],
        "mentioned_only": ["..."],
        "locations": ["..."],
        "creatures": ["..."],
        "concepts": ["..."]
      }
    }
  }
}
```

## Why a separate file

This is consistent with the rest of the pipeline:
- `prompts/pass11_architect_prompt.md`
- `prompts/pass12_profiler_prompt.md`
- `prompts/pass13_chronicler_prompt.md`
- `prompts/pass2_sliding_window_prompt.md`
- `prompts/sa_combined_prompt.md`
- `prompts/sa_lore_prompt.md`

The Python source keeps a fallback inline copy of the system + user prompt
template so the file is not strictly required at runtime, but the
authoritative copy is here. To change the prompt, edit this file (and
mirror the change in `engine/phase3_global_lore.py`).
