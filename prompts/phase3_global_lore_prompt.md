# Phase 3.1 — Global Lore: Name Map + Chapter Appearance

System prompt and user template for Phase 3.1. The engine reads this file at build
time and concatenates it with the per-chapter text payload via `_build_user_prompt()`.

**Scope (v5.1 names-only path):** Produce ONLY `name_map` and `chapter_appearance`.
The engine auto-generates `global_lore` and `timeline_framework` skeletons from these two.
This cuts Phase 3.1 token cost ~50% vs the full 4-key path.

## System prompt

```
You are a literary lore analyst. You read the full text of a novel split into chapters and identify character names and aliases.

Your output must be a clean JSON object containing character names, their aliases, and the chapters they appear in. Do NOT write descriptions, character arcs, or relationships. Focus strictly on names and aliases.
```

## User prompt template

The engine substitutes `{prefix}`, `{N}`, the name candidates block, and
`{chapters_block}` at build time (see `engine/phase3_global_lore.py` →
`_build_user_prompt()`).

```
Project prefix: {prefix}
Total chapters: {N}

Here are known character names found by pattern matching (pattern candidates):
[{candidates}]

Read ALL chapters and identify:
1. Any MISSING character names — especially disguised names (objects used as names, nicknames, titles used as names).
2. All aliases for each character (e.g. 'Heans' = 'Sir William' = 'Sir William Heans').
3. Which episodes each character appears in.

Do NOT write descriptions, arcs, or relationships. Names and aliases ONLY. Engine will handle the rest.

Produce exactly this JSON structure (no extra keys, no markdown wrapper):

{
  "name_map": {
    "project": "{prefix}",
    "generated_phase": "3.1",
    "name_map": {
      "Canonical Name": {
        "aliases": ["Alias 1", "Alias 2"],
        "type": "character",
        "lore_type": "normal|fantasy_name|in_world_language",
        "primary_source": "EP001",
        "episodes": ["EP001", "EP002"]
      }
    }
  },
  "chapter_appearance": {
    "project": "{prefix}",
    "chapter_appearance": {
      "EP001": {
        "characters_present": ["Canonical Name 1", "Canonical Name 2"]
      }
    }
  }
}
```

## Notes

- `type` values: `character`, `location`, `organization`, `creature`, `concept`, `object`
- `lore_type` values: `normal` (recognisable English word/name), `fantasy_name` (invented proper noun), `in_world_language` (fictional-language word)
- Episode IDs use format EP001, EP002, ... EP0NN (zero-padded 3 digits)
- The engine calls `save_global_lore` with the returned JSON; it unwraps `{"item": [...]}` array wrappers automatically

## Why only 2 keys (not 4)

The full 4-key output (`global_lore`, `name_map`, `timeline_framework`, `chapter_appearance`)
was used in v5.0 but costs ~2× more tokens for character/world detail that downstream
engine phases can generate deterministically from the name map.

v5.1 engine auto-generates:
- `global_lore` skeleton from `name_map` entries
- `timeline_framework` skeleton from `chapter_appearance` keys

If you want full character descriptions in `global_lore`, pass all 4 keys to
`save_global_lore` — the engine accepts them and skips skeleton generation.
