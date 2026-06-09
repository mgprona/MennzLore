#!/usr/bin/env python3
"""
Integration tests for Phase 2 improvements:
  - P2.1: Structured Entity Registry (type classification, typed relations)
  - P2.2: Queryable Knowledge Graph (SQLite FTS5, graph queries)
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))

from engine.entity_registry import (
    build_entity_registry, classify_entity, classify_relation,
    ENTITY_TYPES, RELATION_TYPES
)
from engine.knowledge_graph import KnowledgeGraph, load_knowledge_graph


class TestPhase2_1_EntityRegistry(unittest.TestCase):
    """P2.1: Structured Entity Registry."""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.prefix = "test_registry"
        
        # Create micro_facts structure
        mf_dir = os.path.join(self.tmpdir, "micro_facts")
        os.makedirs(mf_dir, exist_ok=True)
        
        # Create global_lore
        vf_dir = os.path.join(self.tmpdir, "verification")
        os.makedirs(vf_dir, exist_ok=True)
        gl = {
            "characters": [
                {"name": "Sherlock Holmes", "role": "Detective"},
                {"name": "Dr. Watson", "role": "Companion"},
            ],
            "locations": [
                {"name": "221B Baker Street", "type": "Residence"},
            ]
        }
        with open(os.path.join(vf_dir, f"{self.prefix}_global_lore.json"), "w") as f:
            json.dump(gl, f)
        
        mf_data = {
            "chapter_id": "EP001",
            "chapter_title": "A Study in Scarlet",
            "characters_present": ["Sherlock Holmes", "Dr. Watson"],
            "scene_details": [
                {"scene_id": "SC-001", "order": 1, "location": "221B Baker Street",
                 "description": "Holmes' apartment", "mood": "conversational",
                 "characters_present_in_scene": ["Sherlock Holmes", "Dr. Watson"]},
            ],
            "key_plot_points": [
                {"point_id": "KPP-001", "order": 1,
                 "description": "Holmes and Watson meet for the first time",
                 "characters_involved": ["Sherlock Holmes", "Dr. Watson"],
                 "in_scene_id": "SC-001",
                 "evidence_quote": "Dr. Watson, I presume?",
                 "evidence_start_line": 1, "evidence_end_line": 1,
                 "match_confidence": 0.95},
            ],
            "cross_chapter_connections": [
                {"connection_id": "CON-001",
                 "from_entity": "Sherlock Holmes", "to_entity": "Dr. Watson",
                 "connection_type": "partnership",
                 "description": "They become detective partners",
                 "in_scene_id": "SC-001",
                 "evidence_quote": "We shall work together"},
                {"connection_id": "CON-002",
                 "from_entity": "Sherlock Holmes", "to_entity": "221B Baker Street",
                 "connection_type": "residence",
                 "description": "Holmes lives at this address",
                 "in_scene_id": "SC-001"},
            ],
            "character_behaviors": [
                {"character": "Sherlock Holmes",
                 "behavior": "Deduces Watson's background instantly",
                 "behavior_type": "action", "in_scene_id": "SC-001"},
            ],
            "character_states": [
                {"character": "Sherlock Holmes",
                 "state": "active",
                 "description": "Eager to solve crimes",
                 "in_scene_id": "SC-001"},
            ],
            "items_of_interest": [
                {"item": "Magnifying Glass",
                 "description": "Holmes' investigation tool",
                 "role_in_chapter": "Key tool",
                 "in_scene_id": "SC-001",
                 "owner": "Sherlock Holmes"},
            ],
            "dialogue_summaries": [],
            "lore_discoveries": [],
            "tags": [],
            "total_events_count": 1,
            "total_scenes_count": 1,
            "total_dialogues_count": 0,
        }
        
        with open(os.path.join(mf_dir, f"{self.prefix}_EP001_micro_facts.json"), "w") as f:
            json.dump(mf_data, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_classify_entity_types(self):
        """All 6 entity types should be classifiable."""
        self.assertEqual(classify_entity("Sherlock Holmes"), "CHARACTER")
        self.assertEqual(classify_entity("London City"), "LOCATION")
        self.assertEqual(classify_entity("The Royal Guild"), "ORGANIZATION")
        self.assertEqual(classify_entity("Excalibur Sword"), "ITEM")
        self.assertEqual(classify_entity("The Great War"), "EVENT")
        self.assertEqual(classify_entity("The Prophecy"), "CONCEPT")
    
    def test_classify_relation_types(self):
        """All 9 relation types should be classifiable."""
        self.assertEqual(classify_relation("residence", "lives at"), "resides_in")
        self.assertEqual(classify_relation("member of", "joined the group"), "belongs_to")
        self.assertEqual(classify_relation("owner", "holds the ring"), "owns")
        self.assertEqual(classify_relation("friendship", "they are close"), "allied_with")
        self.assertEqual(classify_relation("rivalry", "they fight"), "opposes")
        self.assertEqual(classify_relation("influence"), "influences")
        self.assertEqual(classify_relation("reference"), "mentions")
        self.assertEqual(classify_relation("located", "found at"), "located_at")
        self.assertEqual(classify_relation("subdivision"), "part_of")
    
    def test_build_registry(self):
        """Build entity registry from test micro_facts."""
        result = build_entity_registry(self.tmpdir, self.prefix)
        
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["total_entities"], 3)  # Holmes, Watson, Baker St, Magnifying Glass
        self.assertGreater(result["total_relations"], 2)
        
        # Should have multiple types
        types = result["type_distribution"]
        self.assertIn("CHARACTER", types)
        
        # Verify registry file exists
        self.assertTrue(os.path.exists(result["registry_path"]))
        self.assertTrue(os.path.exists(result["relations_path"]))


class TestPhase2_2_KnowledgeGraph(unittest.TestCase):
    """P2.2: Queryable Knowledge Graph."""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.prefix = "test_kg"
        
        mf_dir = os.path.join(self.tmpdir, "micro_facts")
        os.makedirs(mf_dir, exist_ok=True)
        
        vf_dir = os.path.join(self.tmpdir, "verification")
        os.makedirs(vf_dir, exist_ok=True)
        with open(os.path.join(vf_dir, f"{self.prefix}_global_lore.json"), "w") as f:
            json.dump({"characters": [
                {"name": "Sherlock Holmes"}, {"name": "Dr. Watson"},
                {"name": "Professor Moriarty"}
            ]}, f)
        
        # Two chapters of data
        for ep in ["EP001", "EP002"]:
            data = {
                "chapter_id": ep,
                "chapter_title": f"Chapter {ep}",
                "characters_present": ["Sherlock Holmes", "Dr. Watson"],
                "scene_details": [
                    {"scene_id": "SC-001", "order": 1, "location": "London",
                     "description": "The city", "mood": "dark",
                     "characters_present_in_scene": ["Sherlock Holmes"]},
                ],
                "key_plot_points": [
                    {"point_id": "KPP-001", "order": 1,
                     "description": "Holmes investigates a mysterious case",
                     "characters_involved": ["Sherlock Holmes"],
                     "in_scene_id": "SC-001",
                     "evidence_quote": "The game is afoot!",
                     "evidence_start_line": 1, "evidence_end_line": 1,
                     "match_confidence": 0.9},
                ],
                "cross_chapter_connections": [
                    {"connection_id": f"CON-{ep}",
                     "from_entity": "Sherlock Holmes", "to_entity": "Dr. Watson",
                     "connection_type": "partnership",
                     "description": "Solving crimes together",
                     "in_scene_id": "SC-001"},
                    {"connection_id": f"CON-{ep}B",
                     "from_entity": "Sherlock Holmes", "to_entity": "Professor Moriarty",
                     "connection_type": "rivalry",
                     "description": "Arch-enemies",
                     "in_scene_id": "SC-001"},
                ],
                "character_behaviors": [],
                "character_states": [],
                "items_of_interest": [],
                "dialogue_summaries": [],
                "lore_discoveries": [
                    {"discovery_id": f"DSC-{ep}",
                     "description": "Holmes is the world's greatest detective",
                     "source": "Chapter text",
                     "evidence_quote": "There is no one like Sherlock Holmes",
                     "in_scene_id": "SC-001",
                     "evidence_start_line": 2, "evidence_end_line": 2,
                     "match_confidence": 0.95,
                     "verification_status": "VERIFIED"},
                ],
                "tags": [],
                "total_events_count": 1,
                "total_scenes_count": 1,
                "total_dialogues_count": 0,
            }
            with open(os.path.join(mf_dir, f"{self.prefix}_{ep}_micro_facts.json"), "w") as f:
                json.dump(data, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_load_and_stats(self):
        """Load project and get stats."""
        kg = load_knowledge_graph(self.tmpdir, self.prefix)
        stats = kg.stats()
        
        self.assertGreater(stats["total_entities"], 3)
        self.assertGreater(stats["total_relations"], 3)
        kg.close()
    
    def test_search(self):
        """Full-text search should find entities."""
        kg = load_knowledge_graph(self.tmpdir, self.prefix)
        
        result = kg.search("Holmes")
        self.assertGreater(len(result["entities"]), 0)
        self.assertIn("Sherlock Holmes", [e["name"] for e in result["entities"]])
        
        kg.close()
    
    def test_get_entity(self):
        """Get entity profile should return relations."""
        kg = load_knowledge_graph(self.tmpdir, self.prefix)
        
        entity = kg.get_entity("Sherlock Holmes")
        self.assertIsNotNone(entity)
        self.assertEqual(entity["type"], "CHARACTER")
        self.assertIn("relations", entity)
        self.assertIn("relations_by_type", entity)
        
        kg.close()
    
    def test_find_path(self):
        """Should find path between connected entities."""
        kg = load_knowledge_graph(self.tmpdir, self.prefix)
        
        # Watson → Holmes → Moriarty
        result = kg.find_path("Dr. Watson", "Professor Moriarty")
        self.assertNotIn("error", result)
        self.assertEqual(result["length"], 2)  # Watson → Holmes → Moriarty
        self.assertIn("Sherlock Holmes", result["path"])
        
        kg.close()
    
    def test_get_neighbors(self):
        """Should return grouped neighbors."""
        kg = load_knowledge_graph(self.tmpdir, self.prefix)
        
        result = kg.get_neighbors("Sherlock Holmes")
        self.assertNotIn("error", result)
        self.assertGreater(result["neighbor_count"], 0)
        
        kg.close()
    
    def test_entity_not_found(self):
        """Non-existent entity should return None."""
        kg = load_knowledge_graph(self.tmpdir, self.prefix)
        
        entity = kg.get_entity("NonExistentCharacter")
        self.assertIsNone(entity)
        
        path = kg.find_path("NonExistent", "Sherlock Holmes")
        self.assertIn("error", path)
        
        kg.close()


if __name__ == "__main__":
    unittest.main()
