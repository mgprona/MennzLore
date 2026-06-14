#!/usr/bin/env python3
"""
MennzLore Knowledge Graph
==========================
Phase 2.2: Embedded queryable knowledge graph using SQLite FTS5 + in-memory graph.

Zero external dependencies — uses Python's built-in sqlite3 module.

Capabilities:
  - Full-text search across entities, evidence quotes, descriptions
  - Entity lookup with all relations and evidence
  - Path finding between entities (shortest path in relation graph)
  - Neighbor queries (all entities connected to X)
  - Evidence retrieval by entity or relation type

Data model (SQLite):
  entities       — (id, name, type, importance, chapter_count)
  relations      — (id, source_id, target_id, type, description, chapter, evidence)
  evidence_fts   — FTS5 virtual table over evidence quotes

Query interface:
  search(query)          → FTS5-ranked entity/evidence matches
  get_entity(name)       → Full entity profile with relations
  get_relations(name)    → All relations for an entity
  find_path(from, to)    → Shortest path via BFS
  get_neighbors(name)    → Directly connected entities grouped by relation type
"""
import os
import sys
import json
import glob
import sqlite3
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple


# ── SQLite Schema ────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL DEFAULT 'CHARACTER',
    importance INTEGER DEFAULT 0,
    chapter_count INTEGER DEFAULT 0,
    first_chapter TEXT,
    last_chapter TEXT
);

CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES entities(id),
    target_id INTEGER NOT NULL REFERENCES entities(id),
    relation_type TEXT NOT NULL,
    description TEXT,
    chapter TEXT,
    evidence_quote TEXT,
    match_confidence REAL
);

CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
    entity_name,
    quote,
    description,
    chapter
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
"""


# ── Knowledge Graph Class ────────────────────────────────────────────────────

class KnowledgeGraph:
    """Embedded knowledge graph with SQLite FTS5 + in-memory graph traversal."""
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()
        
        # In-memory adjacency for fast graph traversal
        self._adj = defaultdict(set)  # entity_id → {neighbor_id}
        self._name_to_id = {}         # entity_name → entity_id
        self._id_to_name = {}         # entity_id → entity_name
    
    def close(self):
        self.conn.close()
    
    def clear(self):
        """Clear all data from the database tables and in-memory caches."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM entities")
        cursor.execute("DELETE FROM relations")
        cursor.execute("DELETE FROM evidence_fts")
        self.conn.commit()
        
        self._adj.clear()
        self._name_to_id.clear()
        self._id_to_name.clear()
    
    # ── Loading ──────────────────────────────────────────────────────────
    
    def load_project(self, project_dir: str, prefix: str) -> dict:
        """Load all micro_facts from a project into the knowledge graph.
        
        Returns stats dict.
        """
        mf_dir = os.path.join(project_dir, "micro_facts")
        if not os.path.isdir(mf_dir):
            mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
        
        if not os.path.isdir(mf_dir):
            raise FileNotFoundError("No micro_facts directory found.")
        
        pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
        mf_files = sorted(glob.glob(pattern))
        
        if not mf_files:
            raise FileNotFoundError(f"No micro_facts files matching {pattern}")
        
        # Load global_lore for type classification
        gl_path = os.path.join(project_dir, "verification", f"{prefix}_global_lore.json")
        global_lore = {}
        try:
            with open(gl_path, "r", encoding="utf-8") as f:
                global_lore = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        # Import classification helpers
        try:
            from engine.entity_registry import classify_entity, classify_relation
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from entity_registry import classify_entity, classify_relation
        
        entity_importance = defaultdict(int)
        entity_chapters = defaultdict(set)
        entity_type_cache = {}
        
        all_relations = []
        all_evidence = []
        
        for fpath in mf_files:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            ch_id = data.get("chapter_id", "?")
            
            # Characters
            for char in data.get("characters_present", []):
                if char and isinstance(char, str):
                    entity_importance[char] += 2
                    entity_chapters[char].add(ch_id)
                    if char not in entity_type_cache:
                        entity_type_cache[char] = classify_entity(char, global_lore)
            
            # Scene locations
            for scene in data.get("scene_details", []):
                loc = scene.get("location", "")
                if loc and isinstance(loc, str) and loc.lower() not in ("unknown location", "unknown", ""):
                    entity_importance[loc] += 1
                    entity_chapters[loc].add(ch_id)
                    if loc not in entity_type_cache:
                        entity_type_cache[loc] = classify_entity(loc, global_lore)
            
            # Connections → relations
            for conn in data.get("cross_chapter_connections", []):
                from_e = conn.get("from_entity", "")
                to_e = conn.get("to_entity", "")
                if not from_e or not to_e:
                    continue
                
                entity_importance[from_e] += 1
                entity_importance[to_e] += 1
                entity_chapters[from_e].add(ch_id)
                entity_chapters[to_e].add(ch_id)
                
                if from_e not in entity_type_cache:
                    entity_type_cache[from_e] = classify_entity(from_e, global_lore)
                if to_e not in entity_type_cache:
                    entity_type_cache[to_e] = classify_entity(to_e, global_lore)
                
                rel_type = classify_relation(
                    conn.get("connection_type", ""),
                    conn.get("description", "")
                )
                
                all_relations.append({
                    "source": from_e,
                    "target": to_e,
                    "type": rel_type,
                    "description": conn.get("description", ""),
                    "chapter": ch_id,
                    "evidence": conn.get("evidence_quote", ""),
                    "confidence": conn.get("match_confidence"),
                })
            
            # Items → ownership
            for item in data.get("items_of_interest", []):
                owner = item.get("owner", "")
                item_name = item.get("item", "")
                if owner and item_name:
                    entity_importance[owner] += 1
                    entity_importance[item_name] += 1
                    if owner not in entity_type_cache:
                        entity_type_cache[owner] = classify_entity(owner, global_lore)
                    if item_name not in entity_type_cache:
                        entity_type_cache[item_name] = classify_entity(item_name, global_lore)
                    
                    all_relations.append({
                        "source": owner,
                        "target": item_name,
                        "type": "owns",
                        "description": f"Possesses {item_name}",
                        "chapter": ch_id,
                        "evidence": "",
                        "confidence": None,
                    })
            
            # Evidence for FTS
            for section in ["key_plot_points", "lore_discoveries", "character_behaviors"]:
                for item in data.get(section, []):
                    quote = item.get("evidence_quote", "")
                    desc = item.get("description", "") or item.get("behavior", "")
                    if quote:
                        # Find which entities are mentioned
                        for ename in entity_type_cache:
                            if ename.lower() in (desc + quote).lower():
                                all_evidence.append({
                                    "entity": ename,
                                    "quote": quote,
                                    "description": desc,
                                    "chapter": ch_id,
                                })
        
        # ── Insert entities ──
        cursor = self.conn.cursor()
        for ename, importance in entity_importance.items():
            chapters = sorted(entity_chapters.get(ename, set()))
            etype = entity_type_cache.get(ename, "CHARACTER")
            first_ch = chapters[0] if chapters else None
            last_ch = chapters[-1] if chapters else None
            
            cursor.execute(
                "INSERT INTO entities (name, type, importance, chapter_count, first_chapter, last_chapter) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ename, etype, importance, len(chapters), first_ch, last_ch)
            )
            eid = cursor.lastrowid
            self._name_to_id[ename] = eid
            self._id_to_name[eid] = ename
        
        self.conn.commit()
        
        # ── Insert relations ──
        for rel in all_relations:
            src_id = self._name_to_id.get(rel["source"])
            tgt_id = self._name_to_id.get(rel["target"])
            if src_id is None or tgt_id is None:
                continue
            
            cursor.execute(
                "INSERT INTO relations (source_id, target_id, relation_type, description, chapter, evidence_quote, match_confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (src_id, tgt_id, rel["type"], rel["description"][:500],
                 rel["chapter"], rel["evidence"][:500], rel["confidence"])
            )
            self._adj[src_id].add(tgt_id)
            self._adj[tgt_id].add(src_id)  # Undirected for path finding
        
        self.conn.commit()
        
        # ── Insert evidence FTS ──
        for ev in all_evidence:
            cursor.execute(
                "INSERT INTO evidence_fts (entity_name, quote, description, chapter) VALUES (?, ?, ?, ?)",
                (ev["entity"], ev["quote"][:1000], ev["description"][:500], ev["chapter"])
            )
        
        self.conn.commit()
        
        return {
            "entities_loaded": len(self._name_to_id),
            "relations_loaded": len(all_relations),
            "evidence_loaded": len(all_evidence),
        }
    
    # ── Query API ────────────────────────────────────────────────────────
    
    def search(self, query: str, limit: int = 10) -> List[dict]:
        """Full-text search across entities and evidence.
        
        Returns list of matching entities ranked by relevance.
        """
        # FTS search on evidence
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT entity_name, quote, description, chapter, rank "
                "FROM evidence_fts WHERE evidence_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (query, limit)
            )
            evidence_results = [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            evidence_results = []
        
        # Entity name search (LIKE fallback)
        cursor.execute(
            "SELECT id, name, type, importance, chapter_count "
            "FROM entities WHERE name LIKE ? "
            "ORDER BY importance DESC LIMIT ?",
            (f"%{query}%", limit)
        )
        entity_results = [dict(row) for row in cursor.fetchall()]
        
        return {
            "query": query,
            "entities": entity_results,
            "evidence_matches": len(evidence_results),
            "evidence": evidence_results[:5],
        }
    
    def get_entity(self, name: str) -> Optional[dict]:
        """Get full entity profile with all relations."""
        eid = self._name_to_id.get(name)
        if eid is None:
            # Try case-insensitive search
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, name FROM entities WHERE LOWER(name) = LOWER(?)",
                (name,)
            )
            row = cursor.fetchone()
            if row:
                eid = row["id"]
                name = row["name"]
            else:
                return None
        
        cursor = self.conn.cursor()
        
        # Entity info
        cursor.execute("SELECT * FROM entities WHERE id = ?", (eid,))
        entity = dict(cursor.fetchone())
        
        # Relations (both directions)
        cursor.execute("""
            SELECT r.relation_type, r.description, r.chapter, r.evidence_quote, r.match_confidence,
                   CASE WHEN r.source_id = ? THEN e2.name ELSE e1.name END AS other_entity,
                   CASE WHEN r.source_id = ? THEN 'outgoing' ELSE 'incoming' END AS direction
            FROM relations r
            JOIN entities e1 ON r.source_id = e1.id
            JOIN entities e2 ON r.target_id = e2.id
            WHERE r.source_id = ? OR r.target_id = ?
            ORDER BY r.chapter
        """, (eid, eid, eid, eid))
        relations = [dict(row) for row in cursor.fetchall()]
        
        # Group relations by type
        relations_by_type = defaultdict(list)
        for rel in relations:
            relations_by_type[rel["relation_type"]].append(rel)
        
        entity["relations"] = relations
        entity["relations_by_type"] = dict(relations_by_type)
        entity["relation_count"] = len(relations)
        
        return entity
    
    def find_path(self, from_name: str, to_name: str, max_depth: int = 6) -> Optional[dict]:
        """Find shortest path between two entities using BFS."""
        src_id = self._name_to_id.get(from_name)
        tgt_id = self._name_to_id.get(to_name)
        
        if src_id is None or tgt_id is None:
            return {"error": f"Entity not found: {from_name if src_id is None else to_name}"}
        
        if src_id == tgt_id:
            return {"path": [from_name], "length": 0}
        
        # BFS
        visited = {src_id}
        queue = deque([(src_id, [src_id])])
        
        while queue:
            current, path = queue.popleft()
            
            if len(path) > max_depth:
                continue
            
            for neighbor in self._adj.get(current, set()):
                if neighbor == tgt_id:
                    # Found path
                    full_path = path + [neighbor]
                    path_names = [self._id_to_name[n] for n in full_path]
                    
                    # Get edge types along path
                    cursor = self.conn.cursor()
                    edge_types = []
                    for i in range(len(full_path) - 1):
                        a, b = full_path[i], full_path[i + 1]
                        cursor.execute(
                            "SELECT relation_type FROM relations "
                            "WHERE (source_id = ? AND target_id = ?) OR (source_id = ? AND target_id = ?) "
                            "LIMIT 1",
                            (a, b, b, a)
                        )
                        row = cursor.fetchone()
                        edge_types.append(row["relation_type"] if row else "unknown")
                    
                    return {
                        "path": path_names,
                        "length": len(path_names) - 1,
                        "edges": edge_types,
                    }
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return {"error": f"No path found between {from_name} and {to_name} within depth {max_depth}"}
    
    def get_neighbors(self, name: str) -> dict:
        """Get all directly connected entities grouped by relation type."""
        eid = self._name_to_id.get(name)
        if eid is None:
            return {"error": f"Entity not found: {name}"}
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT r.relation_type,
                   CASE WHEN r.source_id = ? THEN e2.name ELSE e1.name END AS neighbor,
                   CASE WHEN r.source_id = ? THEN e2.type ELSE e1.type END AS neighbor_type,
                   r.description, r.chapter
            FROM relations r
            JOIN entities e1 ON r.source_id = e1.id
            JOIN entities e2 ON r.target_id = e2.id
            WHERE r.source_id = ? OR r.target_id = ?
        """, (eid, eid, eid, eid))
        
        neighbors = defaultdict(list)
        for row in cursor.fetchall():
            d = dict(row)
            neighbors[d["relation_type"]].append({
                "entity": d["neighbor"],
                "type": d["neighbor_type"],
                "description": d["description"][:200],
                "chapter": d["chapter"],
            })
        
        return {
            "entity": name,
            "neighbor_count": sum(len(v) for v in neighbors.values()),
            "neighbors_by_type": dict(neighbors),
        }
    
    def stats(self) -> dict:
        """Return graph statistics."""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as cnt FROM entities")
        entity_count = cursor.fetchone()["cnt"]
        
        cursor.execute("SELECT COUNT(*) as cnt FROM relations")
        relation_count = cursor.fetchone()["cnt"]
        
        cursor.execute("SELECT type, COUNT(*) as cnt FROM entities GROUP BY type ORDER BY cnt DESC")
        type_dist = {row["type"]: row["cnt"] for row in cursor.fetchall()}
        
        cursor.execute("SELECT relation_type, COUNT(*) as cnt FROM relations GROUP BY relation_type ORDER BY cnt DESC")
        rel_dist = {row["relation_type"]: row["cnt"] for row in cursor.fetchall()}
        
        return {
            "total_entities": entity_count,
            "total_relations": relation_count,
            "entity_types": type_dist,
            "relation_types": rel_dist,
        }


# ── Public API ───────────────────────────────────────────────────────────────

def _rebuild_adjacency(kg: KnowledgeGraph) -> None:
    """Rebuild in-memory adjacency maps from the SQLite tables."""
    cursor = kg.conn.cursor()
    cursor.execute("SELECT id, name FROM entities")
    for row in cursor.fetchall():
        kg._name_to_id[row["name"]] = row["id"]
        kg._id_to_name[row["id"]] = row["name"]
    
    cursor.execute("SELECT source_id, target_id FROM relations")
    for row in cursor.fetchall():
        kg._adj[row["source_id"]].add(row["target_id"])
        kg._adj[row["target_id"]].add(row["source_id"])

def load_knowledge_graph(project_dir: str, prefix: str = "",
                         db_path: str | None = None,
                         force_reload: bool = False) -> KnowledgeGraph:
    """Load a project into a queryable KnowledgeGraph.
    
    Args:
        project_dir: Path to project directory
        prefix: Project prefix
        db_path: SQLite database path (default: in-memory)
            When a file path is given, the DB is persisted and reused across
            calls.  It is automatically created/refreshed the first time.
        force_reload: Bypass cache and force reload project data.
    
    Returns:
        KnowledgeGraph instance ready for queries
    """
    if not prefix:
        prefix = os.path.basename(project_dir.rstrip("/\\"))
    
    if db_path is None:
        db_path = ":memory:"
    else:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    
    stale_cache = False
    if db_path != ":memory:" and os.path.exists(db_path):
        # Check if any micro_facts file is newer than the DB file
        mf_dir = os.path.join(project_dir, "micro_facts")
        if not os.path.isdir(mf_dir):
            mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
        
        if os.path.isdir(mf_dir):
            try:
                db_mtime = os.path.getmtime(db_path)
                latest_mf_time = os.path.getmtime(mf_dir)
                for f in os.listdir(mf_dir):
                    if f.endswith(".json"):
                        latest_mf_time = max(latest_mf_time, os.path.getmtime(os.path.join(mf_dir, f)))
                if db_mtime < latest_mf_time:
                    stale_cache = True
                    print(f"[INFO] Knowledge graph cache is stale. Reloading data...")
            except OSError:
                pass
    
    kg = KnowledgeGraph(db_path)
    
    # If the file-based DB already has data, skip reloading (unless force_reload or stale)
    if db_path != ":memory:" and not force_reload and not stale_cache:
        cursor = kg.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM entities")
        count = cursor.fetchone()[0]
        if count > 0:
            # Rebuild the in-memory adjacency from existing tables
            _rebuild_adjacency(kg)
            print(f"[OK] Knowledge graph loaded from cache: {count} entities")
            return kg
            
    # Clear any existing tables if reloading
    if db_path != ":memory:":
        kg.clear()
    
    stats = kg.load_project(project_dir, prefix)
    # Rebuild adjacency after load (needed for in-memory case too)
    _rebuild_adjacency(kg)
    print(f"[OK] Knowledge graph loaded: {stats}")
    return kg


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python knowledge_graph.py <project_dir> [prefix]")
        print("  python knowledge_graph.py <project_dir> <prefix> search <query>")
        print("  python knowledge_graph.py <project_dir> <prefix> entity <name>")
        print("  python knowledge_graph.py <project_dir> <prefix> path <from> <to>")
        sys.exit(1)
    
    proj = sys.argv[1]
    pfx = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if len(sys.argv) >= 5:
        cmd = sys.argv[3]
        kg = load_knowledge_graph(proj, pfx)
        
        if cmd == "search":
            result = kg.search(sys.argv[4])
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif cmd == "entity":
            result = kg.get_entity(sys.argv[4])
            if result:
                print(f"Entity: {result['name']} ({result['type']})")
                print(f"  Chapters: {result['chapter_count']} | Relations: {result['relation_count']}")
                for rtype, rels in result.get("relations_by_type", {}).items():
                    print(f"  [{rtype}]: {len(rels)} connections")
            else:
                print(f"Entity '{sys.argv[4]}' not found.")
        elif cmd == "path" and len(sys.argv) >= 6:
            result = kg.find_path(sys.argv[4], sys.argv[5])
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Path ({result['length']} steps): {' → '.join(result['path'])}")
                print(f"Edges: {result['edges']}")
        elif cmd == "neighbors":
            result = kg.get_neighbors(sys.argv[4])
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Neighbors of {result['entity']}: {result['neighbor_count']}")
                for rtype, neighs in result["neighbors_by_type"].items():
                    print(f"  [{rtype}]: {', '.join(n['entity'] for n in neighs)}")
        
        kg.close()
    else:
        kg = load_knowledge_graph(proj, pfx)
        stats = kg.stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        kg.close()
