# Pass 2: Sliding Window Batch Synthesis

You are synthesizing a batch of 5 chapters from micro_facts JSON data into a structured analysis.

## Input Data

You receive:
1. **micro_facts JSONs** for 5 chapters (EP001-EP005 or EP004-EP008, overlap 1)
2. **global_lore.json** (characters, locations, concepts, clues)
3. **timeline_framework.json** (chronology)
4. **name_map.json** (name standardization)

## Your Job

Read ALL 5 micro_facts JSONs, then synthesize the batch into ONE output JSON with EXACTLY these top-level keys — no others:

## 🚨 CRITICAL: Exact JSON Schema — TOP-LEVEL Field Names MUST Match

```json
{
  "batch_range": "EP001-EP005",
  "pillar_3_entity_world": { ... },
  "pillar_4_literary_texture": { ... },
  "pillar_5_production": { ... },
  "pillar_6_spatial": { ... },
  "foreshadowing_cross_reference": { ... }
}
```

❌ DO NOT use: analysis_metadata, batch_metadata, episode_summaries, structural_analysis, summary_table, overview, or any other wrapper object at the top level.

## Field Details

### batch_range
Simple string: `"EP001-EP005"` or `"EP004-EP008"`.

### pillar_3_entity_world
Character arcs, location descriptions, world-building rules.

```json
{
  "characters": {
    "core_cast": [
      {
        "name": "CharacterName",
        "role": "Protagonist / Antagonist / Victim / Witness",
        "arc_in_batch": "How this character changes across these 5 chapters"
      }
    ],
    "key_relationships": [
      "CharacterA → CharacterB: relation type",
      "CharacterC → CharacterD: relation type"
    ],
    "character_archetypes": {
      "archetype_name": "CharacterName — brief description"
    }
  },
  "locations": {
    "LocationName": "Setting for which chapters and its symbolic meaning",
    "AnotherLocation": "..."
  },
  "world_building": {
    "cosmic_rules": "Rules of the supernatural/magical world revealed so far",
    "supernatural_rules": "Rules specific to supernatural entities or forces"
  }
}
```

### pillar_4_literary_texture
Themes, symbols, motifs, and tone progression.

```json
{
  "themes": [
    {"theme": "Theme name", "manifestation": "How this theme appears in the batch"}
  ],
  "symbols": [
    {"symbol": "Object/Concept", "meaning": "What it represents"}
  ],
  "motifs": [
    "Recurring image or pattern 1",
    "Recurring image or pattern 2"
  ],
  "tone_progression": {
    "EP001": "Tone description",
    "EP002": "Tone description"
  }
}
```

### pillar_5_production
Cinematic elements: visual motifs, sound design, structure, cast.

```json
{
  "visual_motifs": ["Recurring visual pattern 1"],
  "sound_design": {
    "ambient": "Background sounds across the batch",
    "key_sounds": "Important sound moments"
  },
  "cinematic_structure": {
    "acts": "Act breakdown across the batch",
    "pacing": "Pacing description"
  },
  "suggested_cast": {
    "CharacterName": "Brief casting note"
  }
}
```

### pillar_6_spatial
Geography, environmental contrasts, spatial symbols.

```json
{
  "geography": {
    "Region/Place": "Description and chapters covered"
  },
  "environmental_contrasts": {
    "indoor_vs_outdoor": "Pattern description",
    "rural_vs_urban": "Pattern description"
  },
  "key_spatial_symbols": {
    "Location/Object": "What it represents spatially"
  }
}
```

### foreshadowing_cross_reference
Track clues introduced, resolved, or still open across the batch.

```json
{
  "clues_introduced": [
    {
      "clue_id": "CLUE_BX_001",
      "episode": "EP001",
      "description": "What the clue is",
      "status": "OPEN or RESOLVED",
      "foreshadowing": "What it sets up",
      "resolution": "Only if RESOLVED — where and how"
    }
  ],
  "arc_milestones": [
    {
      "arc_id": "ARC_BX_001",
      "description": "Character/plot arc update",
      "episode_range": "EP001-EP003"
    }
  ]
}
```

## Batch Assignment Rules

| Total EPs | Batches | Overlap |
|:----------|:--------|:--------|
| 5-7 | 1 | — |
| 8-12 | 2 | 1 EP |
| 13-20 | 3-4 | 1 EP |
| 21+ | ceil(N/5) | 1 EP |

## Golden Rules

1. **Read ALL micro_facts first** — don't synthesize from memory.
2. **Chapter overlap is intentional** — Batch 1 ends at EP005, Batch 2 starts at EP004. This ensures smooth transition.
3. **Keep foreshadowing references self-contained** — each batch's `foreshadowing_cross_reference` covers only clues visible within that batch.
4. **No raw text** — input is structured micro_facts JSON only. Do NOT re-read chapter text.
5. **Use name_map.json** for character name consistency. Do not invent nicknames.
6. **Global lore cross-reference** — check `global_lore.json` for character backstories and concept definitions before assigning archetypes.

## Output Path

`analysis/pass2/{prefix}_batch_{NN}_pass2.json`