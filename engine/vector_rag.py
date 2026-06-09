#!/usr/bin/env python3
"""
MennzLore Vector RAG Memory
============================
Phase 3.2: Semantic search over micro_facts using sentence-transformers embeddings.

Tries ChromaDB first (for persistent vector store), falls back to pure-Python
TF-IDF if chromadb is not installed. Both paths are zero-config for the user.

Install optional deps for full semantic search:
  pip install chromadb sentence-transformers

Without them, the existing TF-IDF engine is used (no quality degradation from
the user's perspective — just no semantic matching).
"""
import os
import sys
import json
import glob
import math
import re
from collections import defaultdict
from typing import List, Dict, Optional

# ── Try importing ChromaDB + sentence-transformers (optional) ────────────────

_CHROMADB_AVAILABLE = False
_SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings
    _CHROMADB_AVAILABLE = True
except ImportError:
    pass

try:
    from sentence_transformers import SentenceTransformer
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

VECTOR_RAG_AVAILABLE = _CHROMADB_AVAILABLE and _SENTENCE_TRANSFORMERS_AVAILABLE


# ── TF-IDF Fallback (pure Python) ────────────────────────────────────────────

class TFIDFMemory:
    """Pure-Python TF-IDF vector memory. Used if ChromaDB is not installed."""
    
    def __init__(self):
        self.documents = []
        self.vocab = {}
        self.idf = {}
        self.tf_vectors = []
    
    def _tokenize(self, text: str) -> List[str]:
        return [w.lower() for w in re.findall(r'\w+', text) if len(w) > 2]
    
    def index(self, texts: List[str], metadatas: List[dict] = None):
        self.documents = []
        self.vocab = {}
        doc_freq = defaultdict(int)
        all_tokens_per_doc = []
        
        for i, text in enumerate(texts):
            tokens = self._tokenize(text)
            all_tokens_per_doc.append(tokens)
            unique = set(tokens)
            for token in unique:
                doc_freq[token] += 1
            
            meta = metadatas[i] if metadatas else {}
            self.documents.append({"text": text, "metadata": meta})
        
        # Build vocabulary
        self.vocab = {token: idx for idx, token in enumerate(sorted(doc_freq.keys()))}
        n_docs = len(texts) or 1
        
        # Compute IDF
        self.idf = {}
        for token, idx in self.vocab.items():
            self.idf[token] = math.log((n_docs + 1) / (doc_freq[token] + 1)) + 1
        
        # Compute TF vectors
        self.tf_vectors = []
        for tokens in all_tokens_per_doc:
            vec = [0.0] * len(self.vocab)
            tf = defaultdict(int)
            for t in tokens:
                if t in self.vocab:
                    tf[t] += 1
            for token, count in tf.items():
                vec[self.vocab[token]] = (1 + math.log(count)) * self.idf[token]
            self.tf_vectors.append(vec)
    
    def query(self, query: str, limit: int = 5) -> List[dict]:
        tokens = self._tokenize(query)
        if not tokens or not self.vocab:
            return []
        
        # Build query vector
        qvec = [0.0] * len(self.vocab)
        tf = defaultdict(int)
        for t in tokens:
            if t in self.vocab:
                tf[t] += 1
        for token, count in tf.items():
            qvec[self.vocab[token]] = (1 + math.log(count)) * self.idf.get(token, 1)
        
        # Cosine similarity
        qnorm = math.sqrt(sum(v * v for v in qvec)) or 1
        scores = []
        for i, dvec in enumerate(self.tf_vectors):
            dnorm = math.sqrt(sum(v * v for v in dvec)) or 1
            dot = sum(qvec[j] * dvec[j] for j in range(len(qvec)))
            score = dot / (qnorm * dnorm) if (qnorm * dnorm) > 0 else 0
            scores.append((score, self.documents[i]))
        
        scores.sort(key=lambda x: -x[0])
        return [{"text": doc["text"], "score": round(score, 4),
                 "metadata": doc["metadata"]}
                for score, doc in scores[:limit] if score > 0]


# ── ChromaDB Vector Memory ───────────────────────────────────────────────────

class ChromaVectorMemory:
    """ChromaDB-backed semantic memory. Requires chromadb + sentence-transformers."""
    
    def __init__(self, persist_dir: str = None):
        if not VECTOR_RAG_AVAILABLE:
            raise ImportError("chromadb and sentence-transformers are required")
        
        if persist_dir:
            self.client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.client = chromadb.Client(Settings(anonymized_telemetry=False))
        
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
    
    def index(self, texts: List[str], metadatas: List[dict] = None,
              collection_name: str = "lore_memory"):
        """Index documents into a ChromaDB collection."""
        # Delete existing collection if present
        try:
            self.client.delete_collection(collection_name)
        except Exception:
            pass
        
        collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        
        if metadatas is None:
            metadatas = [{}] * len(texts)
        
        embeddings = self.model.encode(texts, show_progress_bar=False).tolist()
        ids = [f"doc_{i}" for i in range(len(texts))]
        
        # Batch insert (ChromaDB has limits on batch size)
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            end = min(i + batch_size, len(texts))
            collection.add(
                ids=ids[i:end],
                documents=texts[i:end],
                metadatas=metadatas[i:end],
                embeddings=embeddings[i:end],
            )
        
        return collection
    
    def query(self, query: str, limit: int = 5, collection_name: str = "lore_memory") -> List[dict]:
        """Semantic search query."""
        collection = self.client.get_collection(collection_name)
        query_embedding = self.model.encode([query], show_progress_bar=False).tolist()
        
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        
        docs = []
        for i in range(len(results["documents"][0])):
            docs.append({
                "text": results["documents"][0][i],
                "score": round(1 - results["distances"][0][i], 4),  # Convert distance to similarity
                "metadata": results["metadatas"][0][i],
            })
        return docs


# ── Unified API ──────────────────────────────────────────────────────────────

class VectorRAG:
    """Unified semantic search over lore data. Auto-selects ChromaDB or TF-IDF."""
    
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir
        self._engine = None
        self._is_chromadb = False
        self._collection_name = "lore_memory"
    
    def index_project(self, project_dir: str, prefix: str) -> int:
        """Index all micro_facts from a project.
        
        Returns number of documents indexed.
        """
        mf_dir = os.path.join(project_dir, "micro_facts")
        if not os.path.isdir(mf_dir):
            mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
        
        if not os.path.isdir(mf_dir):
            return 0
        
        pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
        files = sorted(glob.glob(pattern))
        
        texts = []
        metadatas = []
        
        for fpath in files:
            data = {}
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                continue
            
            ch_id = data.get("chapter_id", os.path.basename(fpath))
            ch_title = data.get("chapter_title", "")
            
            # Build searchable text from multiple fields
            text_parts = [f"Chapter: {ch_id} - {ch_title}"]
            
            # Key plot points
            for kpp in data.get("key_plot_points", []):
                if isinstance(kpp, dict):
                    text_parts.append(f"Event: {kpp.get('description', '')}")
                    if kpp.get("evidence_quote"):
                        text_parts.append(f"Quote: {kpp['evidence_quote'][:200]}")
            
            # Character behaviors
            for beh in data.get("character_behaviors", []):
                if isinstance(beh, dict):
                    text_parts.append(f"{beh.get('character', '')}: {beh.get('behavior', '')}")
            
            # Cross-chapter connections
            for conn in data.get("cross_chapter_connections", []):
                if isinstance(conn, dict):
                    text_parts.append(
                        f"Connection: {conn.get('from_entity', '')} → {conn.get('to_entity', '')} "
                        f"({conn.get('connection_type', '')}): {conn.get('description', '')}"
                    )
            
            # Lore discoveries
            for disc in data.get("lore_discoveries", []):
                if isinstance(disc, dict):
                    text_parts.append(f"Lore: {disc.get('description', '')}")
                    if disc.get("evidence_quote"):
                        text_parts.append(f"Evidence: {disc['evidence_quote'][:200]}")
            
            combined = "\n".join(text_parts)
            texts.append(combined)
            metadatas.append({
                "chapter_id": ch_id,
                "chapter_title": ch_title,
                "source_file": os.path.basename(fpath),
            })
        
        if not texts:
            return 0
        
        # Try ChromaDB first, fall back to TF-IDF
        if VECTOR_RAG_AVAILABLE:
            try:
                self._engine = ChromaVectorMemory(self.persist_dir)
                self._engine.index(texts, metadatas, self._collection_name)
                self._is_chromadb = True
                return len(texts)
            except Exception:
                pass  # Fall through to TF-IDF
        
        # Fallback: TF-IDF
        self._engine = TFIDFMemory()
        self._engine.index(texts, metadatas)
        self._is_chromadb = False
        return len(texts)
    
    def query(self, query: str, limit: int = 5) -> List[dict]:
        """Search for relevant lore context.
        
        Returns list of {text, score, metadata} dicts.
        """
        if self._engine is None:
            return []
        
        if self._is_chromadb:
            return self._engine.query(query, limit, self._collection_name)
        else:
            return self._engine.query(query, limit)
    
    @property
    def engine_type(self) -> str:
        if self._engine is None:
            return "none"
        return "chromadb" if self._is_chromadb else "tfidf"


# ── Public API ───────────────────────────────────────────────────────────────

def query_lore_semantic(project_dir: str, prefix: str, query: str,
                        limit: int = 5) -> dict:
    """Convenience function: index + query in one call.
    
    Args:
        project_dir: Path to project directory
        prefix: Project prefix
        query: Search query
        limit: Max results
    
    Returns:
        dict with results and engine info
    """
    rag = VectorRAG()
    indexed = rag.index_project(project_dir, prefix)
    
    if indexed == 0:
        return {
            "status": "error",
            "message": "No micro_facts found to index",
            "results": [],
        }
    
    results = rag.query(query, limit)
    return {
        "status": "success",
        "query": query,
        "engine": rag.engine_type,
        "indexed_documents": indexed,
        "results": results,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python vector_rag.py <project_dir> <prefix> [query] [limit]")
        print("  Without query: shows engine status")
        print("  With query: semantic search")
        sys.exit(1)
    
    proj = sys.argv[1]
    pfx = sys.argv[2]
    
    rag = VectorRAG()
    indexed = rag.index_project(proj, pfx)
    print(f"[OK] Indexed {indexed} documents using {rag.engine_type}")
    print(f"     ChromaDB available: {VECTOR_RAG_AVAILABLE}")
    
    if len(sys.argv) >= 4:
        query = sys.argv[3]
        limit = int(sys.argv[4]) if len(sys.argv) >= 5 else 5
        results = rag.query(query, limit)
        for i, r in enumerate(results):
            print(f"\n--- Result {i+1} (score: {r['score']}) ---")
            print(f"Chapter: {r['metadata'].get('chapter_id', '?')}")
            print(r["text"][:300])
