# SA Combined — Chapter Micro-Facts Extraction (v3.7)

**Role:** Meticulous clerk reading ONE chapter. Extract EVERY concrete fact — events, characters, behaviors, scenes, items, dialogue — with zero interpretation. No project-wide search.

## Schema — EXACT FIELD NAMES

```json
{
  "chapter_id": "EP002",
  "chapter_title": "Why Jurgen Did the Manly Thing",
  "key_plot_points": [
    {"point_id": "KPP-001", "order": 1, "description": "Jurgen passes the Cistercian Abbey and defends the Prince of Darkness to a monk",
     "characters_involved": ["Jurgen", "the monk"], "in_scene_id": "SC-001"}
  ],
  "characters_present": ["Jurgen", "Dame Lisa", "the monk"],
  "character_behaviors": [
    {"character": "Jurgen", "behavior": "Defends the Prince of Darkness", "behavior_type": "speech", "in_scene_id": "SC-001"}
  ],
  "scene_details": [
    {"scene_id": "SC-001", "order": 1, "location": "Outside the Cistercian Abbey",
     "description": "Evening, Jurgen walking home after closing his pawnshop",
     "visual_details": "A stone roadway, a monk has tripped, evening light",
     "mood": "mundane, philosophical",
     "characters_present_in_scene": ["Jurgen", "the monk"]}
  ],
  "items_of_interest": [
    {"item": "shirt of Nessus", "description": "A magical shirt that gives youth",
     "role_in_chapter": "Given to Jurgen by Nessus", "in_scene_id": "SC-003",
     "owner": "Jurgen", "location": "Nessus's Cave"}
  ],
  "character_states": [
    {"character": "Jurgen", "state": "active",
     "description": "Walking home and talking to a monk",
     "in_scene_id": "SC-001"}
  ],
  "dialogue_summaries": [
    {"dialogue_id": "DLG-001", "participants": ["Jurgen", "the monk"],
     "topic": "Defending the Devil's industry",
     "summary": "Jurgen argues the Devil works diligently",
     "key_quotes": ["Fie, brother! and have not the devils enough to bear as it is?"],
     "in_scene_id": "SC-001"}
  ],
  "tags": ["mundane", "philosophical debate", "supernatural introduction"],
  "total_events_count": 3,
  "total_scenes_count": 2,
  "total_dialogues_count": 2,
  "_source_hash": "a1b2c3d4..."
}
```

## ⚠️ Critical Rules

1. **This chapter ONLY** — Do not reference events/characters from other chapters
2. **Characters from text ONLY** — If a name does NOT appear in this chapter text, do NOT include it
3. **Every scene needs an `in_scene_id`** — All entries must reference a defined scene
4. **No null values** — Use `[]` for empty arrays, `""` for empty strings
5. **Minimum thresholds**: 3+ events, 2+ scenes, 2+ behaviors, 1+ dialogue
6. **No search_files, no read_file** — Your context IS the chapter text below
7. **`_source_hash`** — Use the EXACT hash value provided in your prompt instructions (above). This proves you read the actual chapter.

## Usage

Replace `{chapter_text}` below with the full chapter text. Set `chapter_id` to exactly `EP{NNN}`.

## Chapter Text

```
{chapter_text}
```
