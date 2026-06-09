#!/usr/bin/env python3
"""
Integration tests for Phase 3 improvements:
  - P3.1: Timeline Visualization (SVG render from timeline data)
  - P3.2: Vector RAG (TF-IDF fallback, ChromaDB optional)
"""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine"))

from engine.timeline_render import render_timeline, _render_svg_timeline
from engine.vector_rag import VectorRAG, TFIDFMemory, VECTOR_RAG_AVAILABLE


class TestPhase3_1_Timeline(unittest.TestCase):
    """P3.1: Timeline Visualization."""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.prefix = "test_timeline"
        
        # Create verification directory with timeline data
        vf_dir = os.path.join(self.tmpdir, "verification")
        os.makedirs(vf_dir, exist_ok=True)
        
        timeline_framework = {
            "project": self.prefix,
            "timeline_framework": [
                {"chapter_id": "EP001", "title": "The Beginning", "day": 1,
                 "relative_time": "Morning", "primary_location": "London",
                 "summary": "Holmes meets Watson", "major_milestone_refs": [0],
                 "continuity_notes": ""},
                {"chapter_id": "EP002", "title": "The Investigation", "day": 2,
                 "relative_time": "Afternoon", "primary_location": "Crime Scene",
                 "summary": "Holmes examines clues", "major_milestone_refs": [],
                 "continuity_notes": ""},
                {"chapter_id": "EP003", "title": "The Resolution", "day": 3,
                 "relative_time": "Evening", "primary_location": "221B Baker Street",
                 "summary": "Case solved", "major_milestone_refs": [1],
                 "continuity_notes": ""},
            ]
        }
        
        chapter_appearance = {
            "project": self.prefix,
            "chapter_appearance": {
                "EP001": {"characters_present": ["Sherlock Holmes", "Dr. Watson"],
                          "mentioned_only": [], "locations": ["London"], "creatures": [], "concepts": []},
                "EP002": {"characters_present": ["Sherlock Holmes", "Dr. Watson", "Inspector Lestrade"],
                          "mentioned_only": ["Professor Moriarty"], "locations": ["Crime Scene"],
                          "creatures": [], "concepts": []},
                "EP003": {"characters_present": ["Sherlock Holmes", "Dr. Watson"],
                          "mentioned_only": [], "locations": ["221B Baker Street"],
                          "creatures": [], "concepts": []},
            }
        }
        
        with open(os.path.join(vf_dir, f"{self.prefix}_timeline_framework.json"), "w") as f:
            json.dump(timeline_framework, f)
        with open(os.path.join(vf_dir, f"{self.prefix}_chapter_appearance.json"), "w") as f:
            json.dump(chapter_appearance, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_render_timeline_svg(self):
        """Should render a valid SVG timeline."""
        result = render_timeline(self.tmpdir, self.prefix)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_chapters"], 3)
        self.assertTrue(result["timeline_has_data"])
        self.assertTrue(os.path.exists(result["svg_path"]))
        
        # Verify SVG content
        with open(result["svg_path"], "r") as f:
            svg = f.read()
        self.assertIn("<svg", svg)
        self.assertIn("Story Timeline", svg)
        self.assertIn("EP001", svg)
        self.assertIn("EP003", svg)
        self.assertIn("Sherlock Holmes", svg)
    
    def test_render_timeline_empty(self):
        """Empty timeline should still produce valid SVG."""
        empty_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(empty_dir, "verification"), exist_ok=True)
        
        result = render_timeline(empty_dir, "empty")
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["timeline_has_data"])
        
        import shutil
        shutil.rmtree(empty_dir, ignore_errors=True)
    
    def test_render_timeline_json_data(self):
        """Should also write JSON data file."""
        result = render_timeline(self.tmpdir, self.prefix)
        self.assertTrue(os.path.exists(result["json_path"]))
        
        with open(result["json_path"], "r") as f:
            data = json.load(f)
        self.assertEqual(data["total_chapters"], 3)
        self.assertEqual(data["day_span"], 3)


class TestPhase3_2_VectorRAG(unittest.TestCase):
    """P3.2: Vector RAG (TF-IDF fallback)."""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.prefix = "test_rag"
        
        mf_dir = os.path.join(self.tmpdir, "micro_facts")
        os.makedirs(mf_dir, exist_ok=True)
        
        for ep in ["EP001", "EP002"]:
            data = {
                "chapter_id": ep,
                "chapter_title": f"Chapter {ep}",
                "key_plot_points": [
                    {"point_id": "KPP-001", "order": 1,
                     "description": "Sherlock Holmes solves a mysterious murder in London",
                     "characters_involved": ["Sherlock Holmes"],
                     "in_scene_id": "SC-001",
                     "evidence_quote": "The body lay in the study, a look of terror on its face",
                     "evidence_start_line": 1, "evidence_end_line": 1,
                     "match_confidence": 0.9},
                ],
                "character_behaviors": [
                    {"character": "Sherlock Holmes",
                     "behavior": "Examines the crime scene with intense focus",
                     "behavior_type": "action", "in_scene_id": "SC-001"},
                ],
                "cross_chapter_connections": [
                    {"connection_id": "CON-001",
                     "from_entity": "Sherlock Holmes", "to_entity": "Dr. Watson",
                     "connection_type": "partnership",
                     "description": "They solve the murder together",
                     "in_scene_id": "SC-001"},
                ],
                "lore_discoveries": [
                    {"discovery_id": "DSC-001",
                     "description": "The murder weapon was a rare poison from India",
                     "source": "Chapter text",
                     "evidence_quote": "A small vial, empty, with traces of an unknown substance",
                     "in_scene_id": "SC-001",
                     "verification_status": "VERIFIED"},
                ],
                "scene_details": [],
                "characters_present": ["Sherlock Holmes", "Dr. Watson"],
                "character_states": [],
                "items_of_interest": [],
                "dialogue_summaries": [],
                "tags": [],
                "total_events_count": 1,
                "total_scenes_count": 0,
                "total_dialogues_count": 0,
            }
            with open(os.path.join(mf_dir, f"{self.prefix}_{ep}_micro_facts.json"), "w") as f:
                json.dump(data, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_tfidf_fallback(self):
        """TF-IDF fallback should work without ChromaDB."""
        rag = VectorRAG()
        indexed = rag.index_project(self.tmpdir, self.prefix)
        
        self.assertGreater(indexed, 0)
        self.assertIn(rag.engine_type, ("tfidf", "chromadb"))
    
    def test_semantic_search(self):
        """Search should return relevant results."""
        rag = VectorRAG()
        rag.index_project(self.tmpdir, self.prefix)
        
        results = rag.query("murder investigation poison")
        self.assertGreater(len(results), 0)
        
        # Top result should mention murder or investigation
        top_text = results[0]["text"].lower()
        self.assertTrue("murder" in top_text or "investigation" in top_text or "poison" in top_text)
    
    def test_empty_project(self):
        """Empty project should return 0 indexed docs."""
        rag = VectorRAG()
        empty_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(empty_dir, "micro_facts"), exist_ok=True)
        
        indexed = rag.index_project(empty_dir, "empty")
        self.assertEqual(indexed, 0)
        
        import shutil
        shutil.rmtree(empty_dir, ignore_errors=True)
    
    def test_tfidf_direct(self):
        """TFIDFMemory should work standalone."""
        mem = TFIDFMemory()
        mem.index(
            ["Sherlock Holmes is a detective in London",
             "Dr. Watson is a doctor and Holmes' friend",
             "A mysterious murder occurs at midnight"],
            [{"chapter": "EP001"}, {"chapter": "EP001"}, {"chapter": "EP002"}]
        )
        
        results = mem.query("murder detective")
        self.assertGreater(len(results), 0)
        self.assertTrue(any("murder" in r["text"].lower() or "detective" in r["text"].lower()
                          for r in results))


if __name__ == "__main__":
    unittest.main()
