#!/usr/bin/env python3
"""
MennzLore RAG Memory
====================
Provides local semantic memory retrieval. Reads past micro-facts, indexes them
using a pure-python TF-IDF vectorizer, and allows querying past events/discoveries
for long-series context injection.
"""
import os
import re
import json
import glob
import math

class LocalVectorMemory:
    def __init__(self):
        self.documents = [] # List of dicts: {"text": str, "metadata": dict}
        self.vocab = {}
        self.idf = {}
        self.tf_vectors = []

    def load_project_facts(self, project_dir, prefix):
        self.documents = []
        mf_dir = os.path.join(project_dir, "micro_facts")
        if not os.path.isdir(mf_dir):
            mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
            
        if not os.path.isdir(mf_dir):
            return
            
        pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
        for fpath in sorted(glob.glob(pattern)):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                ep_id = data.get("chapter_id", "")
                ep_title = data.get("chapter_title", "")
                
                # 1. Index plot points
                for kpp in data.get("key_plot_points", []):
                    self.add_document(
                        text=f"Episode {ep_id}: {kpp.get('description')}",
                        metadata={"type": "plot_point", "ep": ep_id, "id": kpp.get("point_id")}
                    )
                    
                # 2. Index character behaviors
                for beh in data.get("character_behaviors", []):
                    self.add_document(
                        text=f"Character {beh.get('character')} in Episode {ep_id} scene {beh.get('in_scene_id')}: {beh.get('behavior')}",
                        metadata={"type": "behavior", "ep": ep_id, "character": beh.get("character")}
                    )
                    
                # 3. Index items of interest
                for item in data.get("items_of_interest", []):
                    self.add_document(
                        text=f"Item '{item.get('item')}' in Episode {ep_id}: {item.get('description')} (Role: {item.get('role_in_chapter')})",
                        metadata={"type": "item", "ep": ep_id, "item": item.get("item")}
                    )
                    
                # 4. Index dialogue summaries
                for dlg in data.get("dialogue_summaries", []):
                    self.add_document(
                        text=f"Dialogue between {', '.join(dlg.get('participants', []))} in Episode {ep_id} regarding '{dlg.get('topic')}': {dlg.get('summary')}",
                        metadata={"type": "dialogue", "ep": ep_id, "topic": dlg.get("topic")}
                    )
                    
                # 5. Index lore discoveries
                for disc in data.get("lore_discoveries", []):
                    self.add_document(
                        text=f"Lore Discovery in Episode {ep_id}: {disc.get('description')} (Evidence: \"{disc.get('evidence_quote')}\")",
                        metadata={"type": "discovery", "ep": ep_id, "id": disc.get("discovery_id")}
                    )
            except Exception as e:
                print(f"Warning: Failed to index facts from {fpath}: {e}")

        # Build TF-IDF vectors
        self.build_index()

    def add_document(self, text, metadata):
        self.documents.append({
            "text": text,
            "metadata": metadata
        })

    def tokenize(self, text):
        # Clean text and split into words
        text = re.sub(r'[^\w\s]', '', text.lower())
        return [w for w in text.split() if len(w) > 2] # Skip short stop-words

    def build_index(self):
        self.vocab = {}
        self.idf = {}
        self.tf_vectors = []
        
        if not self.documents:
            return
            
        # 1. Term frequency and vocabulary
        doc_tokens = []
        df = {}
        
        for doc in self.documents:
            tokens = self.tokenize(doc["text"])
            doc_tokens.append(tokens)
            
            # Record vocabulary and document frequency
            seen_terms = set()
            for t in tokens:
                if t not in self.vocab:
                    self.vocab[t] = len(self.vocab)
                seen_terms.add(t)
                
            for t in seen_terms:
                df[t] = df.get(t, 0) + 1

        # 2. IDF calculation
        N = len(self.documents)
        for term, freq in df.items():
            self.idf[term] = math.log((N + 1) / (freq + 0.5)) + 1.0

        # 3. TF-IDF vectors
        for tokens in doc_tokens:
            vec = {}
            for t in tokens:
                vec[t] = vec.get(t, 0) + 1
            # Normalize TF
            doc_len = len(tokens)
            if doc_len > 0:
                for t in vec:
                    vec[t] = (vec[t] / doc_len) * self.idf[t]
            self.tf_vectors.append(vec)

    def query(self, query_text, limit=5):
        if not self.documents or not self.vocab:
            return []
            
        q_tokens = self.tokenize(query_text)
        if not q_tokens:
            return []
            
        # Build query vector
        q_vec = {}
        for t in q_tokens:
            if t in self.vocab:
                q_vec[t] = q_vec.get(t, 0) + 1
                
        q_len = len(q_tokens)
        if q_len > 0:
            for t in q_vec:
                q_vec[t] = (q_vec[t] / q_len) * self.idf[t]

        # Calculate cosine similarity
        scores = []
        for idx, doc_vec in enumerate(self.tf_vectors):
            dot_product = 0.0
            q_norm_sq = 0.0
            doc_norm_sq = 0.0
            
            # Dot product and query norm
            for t, val in q_vec.items():
                q_norm_sq += val ** 2
                if t in doc_vec:
                    dot_product += val * doc_vec[t]
                    
            # Document norm
            for t, val in doc_vec.items():
                doc_norm_sq += val ** 2
                
            q_norm = math.sqrt(q_norm_sq)
            doc_norm = math.sqrt(doc_norm_sq)
            
            score = 0.0
            if q_norm > 0 and doc_norm > 0:
                score = dot_product / (q_norm * doc_norm)
                
            if score > 0.05: # Threshold
                scores.append((score, self.documents[idx]))

        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scores[:limit]]

def query_past_lore(project_dir, prefix, query_text, limit=5):
    mem = LocalVectorMemory()
    mem.load_project_facts(project_dir, prefix)
    return mem.query(query_text, limit)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python rag_memory.py <project_dir> <prefix> <query_text>")
        sys.exit(1)
    results = query_past_lore(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"\nQuery: '{sys.argv[3]}' - Found {len(results)} matches:")
    for idx, doc in enumerate(results):
        print(f"  [{idx+1}] {doc['text']} (Type: {doc['metadata']['type']})")
