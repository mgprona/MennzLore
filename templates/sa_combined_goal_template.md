# ===== DO NOT SHORTEN THIS TEMPLATE =====
# This template MUST be used verbatim for every SA Combined delegate_task goal.
# Replace {EP_ID}, {CHAPTER_TITLE}, {CHAPTER_TEXT} only.
# Shortening causes schema drift — validated across 3 sessions of Jurgen test.

## Task: SA Combined for {EP_ID}

Extract ALL events, characters, behaviors, scenes, items, and dialogue from this chapter into valid JSON.

### EXACT FIELD NAMES — use these, not alternatives:

```json
{
  "chapter_id": "{EP_ID}",
  "chapter_title": "{CHAPTER_TITLE}",
  "key_plot_points": [
    {"point_id": "KPP-001", "order": 1, "description": "...", "characters_involved": ["..."], "in_scene_id": "SC-001"}
  ],
  "characters_present": ["name1", "name2"],
  "character_behaviors": [
    {"character": "...", "behavior": "...", "behavior_type": "action|speech|reaction|thought", "in_scene_id": "SC-001"}
  ],
  "scene_details": [
    {"scene_id": "SC-001", "order": 1, "location": "...", "description": "...", "visual_details": "...", "mood": "...", "characters_present_in_scene": ["..."]}
  ],
  "items_of_interest": [
    {"item": "...", "description": "...", "role_in_chapter": "...", "in_scene_id": "SC-001"}
  ],
  "dialogue_summaries": [
    {"dialogue_id": "DLG-001", "participants": ["..."], "topic": "...", "summary": "...", "key_quotes": ["..."], "in_scene_id": "SC-001"}
  ],
  "tags": ["tag1", "tag2"],
  "total_events_count": 0,
  "total_scenes_count": 0,
  "total_dialogues_count": 0
}
```

### FIELD RULES
- `key_plot_points` — NOT `events`, NOT `plot_points`
- `characters_present` — NOT `key_characters`, NOT `character_list`
- `character_behaviors` — NOT `characters` as list of objects
- `scene_details` — NOT `scenes`
- `items_of_interest` — NOT `items_mentioned`
- `dialogue_summaries` — NOT `dialogue`

### ⚠️ CRITICAL TOOL RESTRICTIONS
- Do NOT use any search_files, grep_search, list_dir, or database tools.
- Do NOT search the repository or browse files. Your context is limited ONLY to the chapter text provided.

### VALIDATION (run before returning)
- [ ] All `point_id`s unique (KPP-001, KPP-002...)
- [ ] All `scene_id`s unique, every item references one
- [ ] `characters_present` matches behavior names
- [ ] Every scene has location + visual_details
- [ ] No `null` — use [] or ""
- [ ] Names from chapter text ONLY
- [ ] Min: 3 events, 2 scenes, 2 behaviors, 1 dialogue

### CHAPTER TEXT

{CHAPTER_TEXT}