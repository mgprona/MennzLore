#!/usr/bin/env python3
"""
MennzLore MCP Server
====================
Provides Model Context Protocol (MCP) server interface for MennzLore project,
exposing tools, prompts, and resources to LLM clients.
"""
import sys
import os
import time
import asyncio
import json as _json
import subprocess
import socket
import concurrent.futures

# Ensure the repository root and engine directory are in the Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT_DIR, "engine")
for d in (ROOT_DIR, ENGINE_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from fastmcp import FastMCP
from fastmcp.prompts import Message
import fastmcp.prompts.base as _fb

# ── Prompt role fix ────────────────────────────────────────────────────
# MCP protocol v2025-03-26 (FastMCP 3.4.x) only accepts role="user" or
# role="assistant" in prompt messages.  System-instruction content is
# embedded directly into a user message instead.
# See: https://github.com/modelcontextprotocol/specification


# ── Auto-update check (non-blocking, cached 24h) ──────────────────────────

def _check_for_updates():
    """Warn on stderr if a newer MennzLore version is on GitHub.
    Cached: only checks once per 24 hours. Non-blocking (<1s).
    Skips silently if git remote is not configured or network is unavailable.
    """
    cache_path = os.path.join(os.path.expanduser("~"), ".mennzlore_update_cache.json")
    if not os.path.exists(cache_path):
        cache = {"checked_at": 0}
    else:
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = _json.load(f)
            if time.time() - cache.get("checked_at", 0) < 86400:  # 24 hours
                if cache.get("update_available"):
                    print(f"[MennzLore] UPDATE AVAILABLE — run: python install.py --upgrade", file=sys.stderr)
                return
        except Exception:
            cache = {"checked_at": 0}

    # Verify a remote named 'origin' exists before attempting network fetch
    try:
        remote_check = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT_DIR, capture_output=True, text=True, timeout=3,
        )
        if remote_check.returncode != 0:
            return  # No origin remote — skip silently
    except Exception:
        return

    # Refresh: git fetch + compare (short timeout to avoid blocking startup)
    try:
        subprocess.run(
            ["git", "fetch", "origin", "master"],
            cwd=ROOT_DIR, capture_output=True, text=True, timeout=5,
        )
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/master"],
            cwd=ROOT_DIR, capture_output=True, text=True, timeout=3,
        )
        behind = int(result.stdout.strip() or "0")
        cache = {"checked_at": time.time(), "update_available": behind > 0, "commits_behind": behind}
    except Exception:
        cache = {"checked_at": time.time(), "update_available": False, "error": "check failed"}

    try:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            _json.dump(cache, f)
    except Exception:
        pass

    if cache.get("update_available"):
        print(f"[MennzLore] UPDATE AVAILABLE ({cache['commits_behind']} new commits) — run: python install.py --upgrade", file=sys.stderr)


# Run the check at import time (non-blocking, cached)
_check_for_updates()


from engine.merge_to_micro_facts import merge_to_micro_facts
from engine.assemble_generic import assemble_lorebook
from engine.assemble_production_generic import build_production
from engine.chart_render_generic import build_chart
from engine.verify_names import verify_names
from engine.rag_memory import query_past_lore
from engine.relationship_graph import render_relationships
from engine.hybrid_notes import generate_hybrid_notes
from engine.entity_registry import build_entity_registry
from engine.knowledge_graph import KnowledgeGraph, load_knowledge_graph
from engine.timeline_render import render_timeline
from engine.vector_rag import query_lore_semantic, VectorRAG, VECTOR_RAG_AVAILABLE
from engine.image_generator import generate_storyboard
from engine.youtube_acquire import analyze_playlist_transcripts, run_playlist_acquisition, get_working_proxy_pool
from engine.fetch_epub import epub_to_project


# Initialize FastMCP Server
mcp = FastMCP("MennzLore")

# Helper to read files in the repository
def read_repo_file(rel_path: str) -> str:
    abs_path = os.path.join(ROOT_DIR, rel_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()

# ─── TOOLS ──────────────────────────────────────────────────────────────────

@mcp.tool()
def verify_character_names(project_dir: str, prefix: str = "") -> dict:
    """
    Phase 3.2: Verify name consistency. Cross-references the name map JSON 
    with raw or clean text files, identifying characters that do not appear in the text.
    
    Args:
        project_dir: The absolute path of the project folder containing raw/clean files.
        prefix: Project prefix (optional, defaults to name of project directory).
    """
    try:
        return verify_names(project_dir, prefix if prefix else None)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def merge_micro_facts(prefix: str, ep_num: str, base_dir: str = ".") -> str:
    """
    Phase 4: Merge and validate the 3-pass JSON outputs (architect, profiler, chronicler) for a specific episode.
    
    Args:
        prefix: The project prefix name (e.g. 'jurgen').
        ep_num: The episode identifier (e.g. 'EP010').
        base_dir: The project root directory (defaults to current working directory).
    """
    try:
        result = await asyncio.to_thread(merge_to_micro_facts, prefix, ep_num, base_dir)
        return (f"[OK] Merged EP{ep_num} micro-facts. "
                f"Events: {result.total_events_count} | Scenes: {result.total_scenes_count} | "
                f"Dialogues: {result.total_dialogues_count}")
    except Exception as e:
        return f"[ERROR] Failed to merge: {e}"

@mcp.tool()
def assemble_lorebook_tool(project_dir: str, prefix: str = "") -> str:
    """
    Phase 7: Assemble all intermediate episode outputs into a master lorebook Markdown file.
    
    Args:
        project_dir: Path to the project directory containing micro_facts/ and entities/.
        prefix: Project prefix (optional).
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        output_path = assemble_lorebook(project_dir, prefix)
        return f"[OK] Master lorebook successfully assembled at {output_path}."
    except Exception as e:
        return f"[ERROR] Failed to assemble lorebook: {e}"

@mcp.tool()
def render_production_tool(project_dir: str, prefix: str = "") -> str:
    """
    Phase 9: Process characters and micro-facts into cinematography lists, visual style guides, and image prompts.
    
    Args:
        project_dir: Path to the project directory.
        prefix: Project prefix (optional).
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        build_production(project_dir, prefix)
        out_dir = os.path.join(project_dir, "output", "production")
        return f"[OK] Production assets successfully rendered in {out_dir}."
    except Exception as e:
        return f"[ERROR] Failed to render production: {e}"

@mcp.tool()
def render_map_tool(project_dir: str, prefix: str = "") -> str:
    """
    Phase 10: Process locations from micro-facts, project coordinates, and draw route maps as SVG.
    
    Args:
        project_dir: Path to the project directory.
        prefix: Project prefix (optional).
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        build_chart(project_dir, prefix)
        out_dir = os.path.join(project_dir, "output", "spatial")
        return f"[OK] Spatial maps successfully rendered in {out_dir}."
    except Exception as e:
        return f"[ERROR] Failed to render map: {e}"

@mcp.tool()
def open_dashboard_tool() -> str:
    """
    Launch the interactive world explorer web dashboard on http://localhost:8000.
    Checks if the port is already open before starting the server.
    """
    port = 8000
    # Check if port is already open
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        is_open = s.connect_ex(('localhost', port)) == 0
        
    if is_open:
        return f"[OK] Dashboard is already running and accessible at http://localhost:{port}"
        
    try:
        server_path = os.path.join(ROOT_DIR, "engine", "dashboard_server.py")
        subprocess.Popen(
            [sys.executable, server_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return f"[OK] Started interactive dashboard server. Open http://localhost:{port} in your browser."
    except Exception as e:
        return f"[ERROR] Failed to start dashboard server: {e}"

@mcp.tool()
def query_past_lore_tool(project_dir: str, prefix: str, query: str, limit: int = 5) -> list:
    """
    Search past episodes' micro-facts for relevant background context (Local RAG Memory).
    
    Args:
        project_dir: Path to the project directory.
        prefix: Project prefix (e.g. 'tm').
        query: Search term (e.g. name of character or location).
        limit: Max number of facts to return.
    """
    try:
        results = query_past_lore(project_dir, prefix, query, limit)
        return [doc["text"] for doc in results]
    except Exception as e:
        return [f"[ERROR] Failed to query RAG: {e}"]

@mcp.tool()
def render_relationships_tool(project_dir: str, prefix: str = "") -> dict:
    """
    Phase 11 (NEW): Build and render a force-directed character/location/entity
    relationship graph from micro_facts data. Outputs SVG, GEXF, and JSON.
    
    Args:
        project_dir: Path to the project directory containing micro_facts/.
        prefix: Project prefix (auto-detected if empty).
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        result = render_relationships(project_dir, prefix)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def generate_hybrid_notes_tool(project_dir: str, prefix: str = "") -> dict:
    """
    Phase 12 (NEW): Generate structured per-entity hybrid notes with sections:
    [CONTEXT] [FACTS] [BEHAVIOR] [GAPS] [EVIDENCE]
    Inspired by LoreGraph's Hybrid Note format. Deterministic assembly from
    micro_facts — no LLM required.
    
    Args:
        project_dir: Path to the project directory containing micro_facts/.
        prefix: Project prefix (auto-detected if empty).
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        result = generate_hybrid_notes(project_dir, prefix)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def build_entity_registry_tool(project_dir: str, prefix: str = "") -> dict:
    """
    Phase 13 (NEW): Build a typed, normalized entity registry from micro_facts.
    Classifies every entity as CHARACTER, LOCATION, ORGANIZATION, ITEM, EVENT,
    or CONCEPT. Produces typed relation graph with 9 relation types.
    
    Args:
        project_dir: Path to the project directory containing micro_facts/.
        prefix: Project prefix (auto-detected if empty).
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        result = build_entity_registry(project_dir, prefix)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def query_knowledge_graph(project_dir: str, prefix: str = "",
                          action: str = "stats", query: str = "",
                          from_entity: str = "", to_entity: str = "",
                          entity_name: str = "", limit: int = 10) -> dict:
    """
    Phase 14 (NEW): Query the embedded knowledge graph (SQLite FTS5 + graph).
    
    Actions:
      stats    — Return entity/relation statistics
      search   — Full-text search across entities and evidence (use 'query' param)
      entity   — Get full entity profile with all relations (use 'entity_name')
      path     — Find shortest path between two entities (use 'from_entity', 'to_entity')
      neighbors — Get directly connected entities (use 'entity_name')
    
    Args:
        project_dir: Path to the project directory.
        prefix: Project prefix (auto-detected if empty).
        action: One of stats, search, entity, path, neighbors.
        query: Search query (for action='search').
        from_entity: Source entity (for action='path').
        to_entity: Target entity (for action='path').
        entity_name: Entity name (for action='entity' or 'neighbors').
        limit: Max results for search.
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        
        kg = load_knowledge_graph(project_dir, prefix,
                                   db_path=os.path.join(project_dir, "output", "knowledge_graph.db"))
        
        if action == "stats":
            result = kg.stats()
        elif action == "search":
            result = kg.search(query, limit=limit)
        elif action == "entity":
            result = kg.get_entity(entity_name)
            if result is None:
                result = {"error": f"Entity '{entity_name}' not found"}
        elif action == "path":
            result = kg.find_path(from_entity, to_entity)
        elif action == "neighbors":
            result = kg.get_neighbors(entity_name)
        else:
            result = {"error": f"Unknown action: {action}. Use stats/search/entity/path/neighbors."}
        
        kg.close()
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def render_timeline_tool(project_dir: str, prefix: str = "") -> dict:
    """
    Phase 15 (NEW): Render an SVG timeline visualization from timeline_framework
    and chapter_appearance data. Shows chapter sequence with day markers, character
    appearance heatmap, and location tracking.
    
    Args:
        project_dir: Path to the project directory.
        prefix: Project prefix (auto-detected if empty).
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        result = render_timeline(project_dir, prefix)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def query_lore_semantic_tool(project_dir: str, prefix: str, query: str,
                              limit: int = 5) -> dict:
    """
    Phase 16 (NEW): Semantic search over micro_facts using vector embeddings.
    Uses ChromaDB+sentence-transformers if installed, falls back to TF-IDF.
    
    Args:
        project_dir: Path to the project directory.
        prefix: Project prefix.
        query: Natural language search query.
        limit: Max results to return (default: 5).
    """
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        result = query_lore_semantic(project_dir, prefix, query, limit=limit)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def generate_storyboard_tool(project_dir: str, prefix: str, approved_scenes: list, model_id: str = "google/gemini-2.5-flash-image") -> str:
    """
    Generate storyboard images for approved scenes using OpenRouter.
    Only scenes in the approved_scenes list will be generated to control costs.
    
    Args:
        project_dir: Path to the project directory.
        prefix: Project prefix.
        approved_scenes: List of scene IDs (e.g. ['SC-001', 'SC-002']) to generate.
        model_id: OpenRouter model ID to use (defaults to Gemini 2.5 Flash Image).
    """
    try:
        res = generate_storyboard(project_dir, prefix, approved_scenes, model_id)
        if res["status"] == "ok":
            return (f"[OK] Storyboard rendering completed. "
                    f"Generated: {res['generated_count']} images | "
                    f"Skipped/Existed: {res['skipped_count']} images.")
        else:
            return f"[ERROR] Generation failed: {res.get('message', 'Unknown error')}"
    except Exception as e:
        return f"[ERROR] Storyboard generation threw exception: {e}"

@mcp.tool()
def analyze_youtube_playlist(playlist_url: str, use_proxies: bool = False) -> dict:
    """
    Scan a YouTube playlist or video URL and check subtitle availability
    (manual, auto-generated, or missing).
    
    Args:
        playlist_url: The YouTube playlist or single video URL.
        use_proxies: Set to True to scrape and rotate proxies if rate limited.
    """
    try:
        # Check if we should initialize a proxy pool for the scan
        proxy_pool = []
        if use_proxies:
            proxy_pool = get_working_proxy_pool(limit=5)
            
        # Try scan
        scan_errors = []
        try:
            return analyze_playlist_transcripts(playlist_url)
        except Exception as e:
            scan_errors.append(str(e))
            if use_proxies and proxy_pool:
                for p in proxy_pool:
                    try:
                        return analyze_playlist_transcripts(playlist_url, proxy=p)
                    except Exception as err:
                        scan_errors.append(str(err))
            raise Exception(f"Failed to scan playlist metadata: {scan_errors}")
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def run_youtube_acquisition(playlist_url: str, project_dir: str, prefix: str, approved: bool = False, model_id: str = "openai/whisper-large-v3-turbo", use_proxies: bool = False) -> dict:
    """
    Run full YouTube transcript/STT acquisition.
    Pulls free transcripts or uses Whisper STT via OpenRouter for missing subtitles (if approved).
    
    Args:
        playlist_url: The YouTube playlist or single video URL.
        project_dir: The project directory path where files will be saved.
        prefix: Project prefix (e.g. 'dyfed').
        approved: Set to True if the user has approved the cost of doing Whisper STT.
        model_id: The OpenRouter model ID to use for audio transcription.
        use_proxies: Set to True to scrape and rotate proxies to prevent rate limiting.
    """
    try:
        return run_playlist_acquisition(playlist_url, project_dir, prefix, approved=approved, model_id=model_id, use_proxies=use_proxies)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def acquire_epub(epub_path: str, base_dir: str = ".", prefix: str = "",
                 title: str = "", author: str = "") -> dict:
    """Phase 1 (EPUB): Import a local .epub file and scaffold the project.
    
    Extracts chapter text from the EPUB, writes raw/full.txt, splits into
    clean/EP*.txt chapters, and writes provenance. Ready for Phase 2+ pipeline.

    Args:
        epub_path: Absolute path to the .epub file.
        base_dir: Directory under which the project folder is created (default: cwd).
        prefix: Project prefix (auto-generated if empty).
        title: Book title (auto-detected from EPUB metadata if empty).
        author: Author name (auto-detected from EPUB metadata if empty).
    Returns:
        Dict with project_dir, prefix, chapter_count, total_chars.
    """
    project_dir = epub_to_project(epub_path, base_dir=base_dir, prefix=prefix,
                                  title=title, author=author)
    prefix = prefix or os.path.basename(project_dir.rstrip("/\\"))
    return {
        "status": "ok",
        "project_dir": project_dir,
        "prefix": prefix,
        "phase": "1 (EPUB import)",
        "next": f"split_into_chapters('{project_dir}', '{prefix}') or proceed to Phase 3",
    }

@mcp.tool()
def acquire_by_id(book_id: int, base_dir: str = ".") -> dict:
    """
    Phase 1 (by Gutenberg ID): Download a public-domain book by its Gutenberg ID,
    scaffold the project directory, and write provenance. Uses the same download
    and `<prefix>_full.txt` naming path as acquire_by_title, so the downstream
    pipeline works identically. Use split_into_chapters (Phase 2) afterwards.

    Args:
        book_id: The Project Gutenberg book ID (e.g. 62 for A Princess of Mars).
        base_dir: Directory under which the `<prefix>/` project folder is created (default: cwd).
    """
    from engine.fetch_raw import fetch_raw_by_id
    try:
        provenance = fetch_raw_by_id(int(book_id), base_dir)
        return {"status": "success", "result": provenance}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def acquire_by_title(title: str, author: str, base_dir: str = ".") -> dict:
    """
    Phase 1 (recommended): Find a public-domain book by TITLE + AUTHOR via gutendex,
    download its raw text (PG-19 first, Project Gutenberg fallback), scaffold the
    project directory, and write provenance. Output uses the canonical
    `<prefix>_full.txt` naming that the downstream pipeline expects.

    Args:
        title: Book title (e.g. 'Voodoo Planet').
        author: Author name (e.g. 'Andre Norton').
        base_dir: Directory under which the `<prefix>/` project folder is created (default: cwd).
    """
    from engine.fetch_raw import fetch_raw
    try:
        provenance = fetch_raw(title, author, base_dir)
        return {"status": "success", "result": provenance}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def split_into_chapters(project_dir: str, prefix: str = "") -> dict:
    """
    Phase 2: Strip Gutenberg boilerplate from the raw full-text and split it into
    per-chapter files `clean/<prefix>_EP###.txt`, detecting chapter headings with a
    blank-line guard. Also writes a chapter manifest.

    Args:
        project_dir: Path to the project directory (must contain raw/<prefix>_full.txt).
        prefix: Project prefix (optional, defaults to project directory name).
    """
    from engine.split_chapters import split_chapters
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        chapters = split_chapters(project_dir, prefix)
        return {"status": "success", "chapters": len(chapters),
                "episodes": [c["ep_id"] for c in chapters]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def save_global_lore(project_dir: str, global_lore: dict, name_map: dict,
                     timeline_framework: dict, chapter_appearance: dict,
                     prefix: str = "") -> dict:
    """
    Phase 3.1 (recommended): Persist the global-lore analysis that YOU (the connected
    AI) produced from the chapter texts. Call the `extract_global_lore` prompt first,
    reason over the chapters, then pass the four resulting JSON objects here. This is
    the MCP-native path — no external API key required.

    Args:
        project_dir: Path to the project directory.
        global_lore: The global_lore object (book_metadata, characters, etc.).
        name_map: The name_map object (canonical names, aliases, lore_type).
        timeline_framework: The timeline_framework object.
        chapter_appearance: The chapter_appearance object.
        prefix: Project prefix (optional, defaults to project directory name).
    """
    from engine.phase3_global_lore import write_global_lore_outputs
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        # Unwrap any {"item": ...} envelopes on the four top-level objects BEFORE
        # the engine sees them. The MCP/JSON-RPC + Pydantic stack sometimes wraps
        # arrays in {"item": <value>}, and write_global_lore_outputs already
        # handles that, but doing it here means downstream engines that read the
        # raw dict (e.g. phase3_auto_verify) also see clean data.
        # NOTE: write_global_lore_outputs() calls _unwrap_xml_arrays() on its
        # inputs, so this defensive unwrap is belt-and-braces. Harmless if the
        # input is already plain.
        result = {
            "global_lore":        global_lore,
            "name_map":           name_map,
            "timeline_framework": timeline_framework,
            "chapter_appearance": chapter_appearance,
        }
        stats = await asyncio.to_thread(write_global_lore_outputs, project_dir, prefix, result)
        return {"status": "success", **stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def run_global_lore(project_dir: str, prefix: str = "", model: str = "gpt-4o") -> dict:
    """
    Phase 3.1 (API fallback): Extract global lore via an EXTERNAL LLM. Use this only
    for headless/CLI runs. When connected to an MCP client, prefer the
    `extract_global_lore` prompt + `save_global_lore` tool so the connected AI does
    the extraction (no OPENAI_API_KEY needed). Requires OPENAI_API_KEY in the env.

    Args:
        project_dir: Path to the project directory (must contain clean/<prefix>_EP###.txt).
        prefix: Project prefix (optional, defaults to project directory name).
        model: OpenAI model ID (defaults to gpt-4o).
    """
    from engine.phase3_global_lore import run_phase3_global_lore
    try:
        if not os.environ.get("OPENAI_API_KEY"):
            return {"status": "error", "message": "OPENAI_API_KEY not set. Use save_global_lore instead (no API key needed)."}
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        result = run_phase3_global_lore(project_dir, prefix, model=model)
        return {
            "status": "success",
            "characters": len(result["global_lore"].get("characters", [])),
            "name_map_entries": len(result["name_map"].get("name_map", {})),
            "timeline_entries": len(result["timeline_framework"].get("timeline_framework", [])),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def auto_verify_names(project_dir: str, prefix: str = "") -> dict:
    """
    Phase 3.2: Deterministically cross-reference the generated name_map against the
    clean chapter texts (no LLM). Flags entries declared but never found, ellipsis/
    truncation, and foreign-script leakage. Writes a validation report and updates
    pipeline state.

    Args:
        project_dir: Path to the project directory (must contain verification/<prefix>_name_map.json).
        prefix: Project prefix (optional, defaults to project directory name).
    """
    from engine.phase3_auto_verify import run_auto_verify
    try:
        if not prefix:
            prefix = os.path.basename(project_dir.rstrip("/\\"))
        return run_auto_verify(project_dir, prefix)
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def run_saga_assembly(saga_dir: str) -> dict:
    """
    Saga Mode: Run Saga timeline creation, compile the Master Saga Lorebook,
    and perform the cross-volume consistency audit.
    
    Args:
        saga_dir: The absolute path to the saga directory containing saga_config.json.
    """
    from engine.saga_assembler import build_saga_master_lorebook, generate_cross_volume_consistency_report
    from engine.saga_config import load_saga_config
    try:
        config = load_saga_config(saga_dir)
        lorebook_path = build_saga_master_lorebook(saga_dir)
        report_path = generate_cross_volume_consistency_report(saga_dir)
        return {
            "status": "success",
            "saga_title": config.saga_title,
            "master_lorebook": lorebook_path,
            "consistency_report": report_path
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def query_saga_rag(saga_dir: str, query: str, limit: int = 5) -> dict:
    """
    Saga Mode: Search across all volumes in a saga using local vector memory (Local RAG).
    
    Args:
        saga_dir: The absolute path to the saga directory containing saga_config.json.
        query: Search term or character/location history query.
        limit: Maximum number of historical facts to return.
    """
    from engine.saga_config import load_saga_config
    from engine.saga_rag_memory import SagaVectorMemory
    try:
        config = load_saga_config(saga_dir)
        mem = SagaVectorMemory()
        volumes_list = []
        for vol in config.volumes:
            volumes_list.append({
                "volume_id": vol.volume_id,
                "title": vol.title,
                "prefix": vol.prefix,
                "project_dir": vol.project_dir
            })
        mem.load_saga_facts(saga_dir, volumes_list)
        results = mem.query_cross_volume(query, limit=limit)
        serializable_results = []
        for doc in results:
            serializable_results.append({
                "text": doc["text"],
                "score": doc.get("score", 0.0),
                "metadata": doc["metadata"]
            })
        return {
            "status": "success",
            "query": query,
            "results": serializable_results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ─── RESOURCES ──────────────────────────────────────────────────────────────

@mcp.resource("schema://architect")
def get_architect_schema() -> str:
    """JSON schema for Pass 1.1: Architect structure output."""
    return read_repo_file("schemas/architect.schema.json")

@mcp.resource("schema://profiler")
def get_profiler_schema() -> str:
    """JSON schema for Pass 1.2: Profiler structure output."""
    return read_repo_file("schemas/profiler.schema.json")

@mcp.resource("schema://chronicler")
def get_chronicler_schema() -> str:
    """JSON schema for Pass 1.3: Chronicler structure output."""
    return read_repo_file("schemas/chronicler.schema.json")

@mcp.resource("schema://micro_facts_final")
def get_micro_facts_schema() -> str:
    """JSON schema for final merged micro-facts format (validated by lore_models)."""
    return read_repo_file("schemas/micro_facts_final.schema.json")

@mcp.resource("example://micro_facts")
def get_micro_facts_example() -> str:
    """Example final micro facts JSON file for reference."""
    return read_repo_file("examples/example_micro_facts.json")


# ─── FULL PIPELINE RUNNER ──────────────────────────────────────────────────

PIPELINE_ORDER = [
    ("1_acquire",       "Acquire raw text (Engine)"),
    ("2_clean",         "Split & clean chapters (Engine)"),
    ("3_global_lore",   "Global lore + names + timeline (LLM)"),
    ("4_micro_facts",   "Micro-facts extraction per chapter (LLM)"),
    ("5_merge",         "Merge & validate micro_facts (Engine)"),
    ("6_production",    "Production render: cinematography + image prompts (Engine)"),
    ("7_map",           "Spatial render: map SVG + routes (Engine)"),
    ("8_relationships", "Relationship graph: force-directed SVG (Engine)"),
    ("9_hybrid_notes",  "Per-entity hybrid notes (Engine)"),
    ("10_entity_registry", "Typed entity registry (Engine)"),
    ("11_knowledge_graph", "SQLite knowledge graph (Engine)"),
    ("12_timeline",     "Timeline SVG render (Engine)"),
    ("13_semantic",     "Semantic search index (Engine)"),
    ("14_assemble",     "MASTER LOREBOOK — final assembly of all outputs (Engine)"),
]

ENGINE_ONLY_PHASES = {"5_merge", "6_production", "7_map", "8_relationships",
                      "9_hybrid_notes", "10_entity_registry", "11_knowledge_graph",
                      "12_timeline", "13_semantic", "14_assemble"}


@mcp.tool()
def run_full_pipeline(project_dir: str, prefix: str = "",
                      start_phase: str = "5_merge",
                      skip_llm: bool = True) -> dict:
    """Run all engine pipeline phases (5-14) in order for a project.

    Use this AFTER phases 1-4 are complete (acquire, split, global lore, micro_facts).
    Phases 1-4 require LLM interaction and should be run separately.

    Args:
        project_dir: Path to the project directory.
        prefix: Project prefix (auto-detected if empty).
        start_phase: Phase to start from (default: "5_merge").
        skip_llm: Always skip LLM phases (default: True).
    Returns:
        Dict with per-phase status and overall summary.
    """
    if not prefix:
        prefix = os.path.basename(project_dir.rstrip("/\\"))

    results = {}
    started = False
    engine_pass = 0
    engine_fail = 0
    skipped = 0

    for phase_id, phase_desc in PIPELINE_ORDER:
        # Wait until we reach start_phase
        if not started:
            if phase_id == start_phase:
                started = True
            else:
                results[phase_id] = {"status": "SKIPPED", "desc": phase_desc}
                skipped += 1
                continue

        # Skip LLM phases when skip_llm is set
        if skip_llm and phase_id not in ENGINE_ONLY_PHASES:
            results[phase_id] = {"status": "SKIPPED (LLM)", "desc": phase_desc}
            skipped += 1
            continue

        try:
            _run_engine_phase(phase_id, project_dir, prefix,
                              phase_timeout=120)
            results[phase_id] = {"status": "OK", "desc": phase_desc}
            engine_pass += 1
        except Exception as e:
            results[phase_id] = {"status": f"FAIL: {e}", "desc": phase_desc}
            engine_fail += 1
    summary = {
        "project": prefix,
        "phases": results,
        "engine_pass": engine_pass,
        "engine_fail": engine_fail,
        "skipped": skipped,
        "total": len(PIPELINE_ORDER),
    }

    print(f"\n[PIPELINE] {engine_pass}/{engine_pass + engine_fail} engine phases OK ({skipped} skipped)")
    return summary


def _run_engine_phase(phase_id: str, project_dir: str, prefix: str,
                      phase_timeout: int = 120) -> None:
    """Execute one engine phase. All print() calls flush automatically so
    the MCP transport sees progress and doesn't time out the connection.
    Raises on failure."""
    _flush = lambda: (sys.stdout.flush(), sys.stderr.flush())

    if phase_id == "5_merge":
        # Already done via merge_micro_facts — check output exists
        mf_dir = os.path.join(project_dir, "micro_facts")
        if not os.path.isdir(mf_dir) or not any(f.endswith(".json") for f in os.listdir(mf_dir)):
            raise FileNotFoundError("No micro_facts found. Run Phase 4 LLM extraction first.")
        print(f"[Phase 5] micro_facts: {len([f for f in os.listdir(mf_dir) if f.endswith('.json')])} files — OK",
              flush=True)

    elif phase_id == "6_production":
        build_production(project_dir, prefix)

    elif phase_id == "7_map":
        build_chart(project_dir, prefix)

    elif phase_id == "8_relationships":
        render_relationships(project_dir, prefix)

    elif phase_id == "9_hybrid_notes":
        generate_hybrid_notes(project_dir, prefix)

    elif phase_id == "10_entity_registry":
        build_entity_registry(project_dir, prefix)

    elif phase_id == "11_knowledge_graph":
        load_knowledge_graph(project_dir, prefix,
                             db_path=os.path.join(project_dir, "output", "knowledge_graph.db"),
                             force_reload=True)

    elif phase_id == "12_timeline":
        render_timeline(project_dir, prefix)

    elif phase_id == "13_semantic":
        result = query_lore_semantic(project_dir, prefix=prefix, query="character", limit=1)
        n = len(result.get("results", [])) if isinstance(result, dict) else 0
        engine_type = result.get("engine", "?") if isinstance(result, dict) else "?"
        indexed = result.get("indexed_documents", 0) if isinstance(result, dict) else 0
        print(f"[Phase 13] Semantic index ({engine_type}): {indexed} docs indexed, {n} results — OK", flush=True)

    elif phase_id == "14_assemble":
        assemble_lorebook(project_dir, prefix)
    else:
        raise ValueError(f"Unknown phase: {phase_id}")

    # Flush so MCP transport sees progress
    _flush()


# ─── PROMPTS ────────────────────────────────────────────────────────────────

@mcp.prompt()
def extract_global_lore(project_dir: str, prefix: str = "") -> list[Message]:
    """Phase 3.1 prompt: read all clean chapters and extract global lore, name map,
    timeline framework, and chapter appearances."""
    from engine.phase3_global_lore import SYSTEM_PROMPT, _load_clean_chapters, _build_user_prompt, extract_name_candidates
    if not prefix:
        prefix = os.path.basename(project_dir.rstrip("/\\"))
    chapters = _load_clean_chapters(project_dir, prefix)
    candidates = extract_name_candidates(chapters)
    user_content = _build_user_prompt(prefix, chapters, candidates)
    return [
            Message(SYSTEM_PROMPT + "\n\n" + user_content, role="user"),
        ]


def _split_chronicler_template() -> tuple[str, str]:
    """Split pass13_chronicler_prompt.md into (system_instructions, input_section)."""
    template = read_repo_file("prompts/pass13_chronicler_prompt.md")
    parts = template.split("## INPUT DATA")
    before = parts[0].strip()
    after = parts[1] if len(parts) > 1 else ""
    schema_start = after.find("## ")
    system_part = before + "\n\n" + after[schema_start:] if schema_start >= 0 else before
    input_header = "## INPUT DATA" + (after[:schema_start] if schema_start >= 0 else "")
    return system_part, input_header


@mcp.prompt()
def analyze_architect(chapter_text: str) -> list[Message]:
    """Get the prompt for Pass 1.1 (Architect): extract scene structure and key plot points from a chapter."""
    import hashlib
    template = read_repo_file("prompts/pass11_architect_prompt.md")
    source_hash = hashlib.sha256(chapter_text.encode("utf-8")).hexdigest()
    hash_note = (
        f"\n\n## REQUIRED: _source_hash\n"
        f'Include this EXACT field in your JSON output:\n'
        f'"_source_hash": "{source_hash}"\n'
        f"(This proves you read the actual chapter text)\n"
    )
    filled = template.replace("{chapter_text}", chapter_text)
    return [
            Message(filled + hash_note, role="user"),
        ]


@mcp.prompt()
def analyze_profiler(chapter_text: str, architect_json: str) -> list[Message]:
    """Get the prompt for Pass 1.2 (Profiler): extract characters, behaviors, items, and dialogue using Architect scene list."""
    import json as _j
    template = read_repo_file("prompts/pass12_profiler_prompt.md")
    # Build a compact scene list string from architect JSON for prompt injection
    try:
        arch = _j.loads(architect_json)
        scenes = arch.get("scene_details", [])
        scene_list = "\n".join(
            f"- {s.get('scene_id', '?')}: {s.get('location', '?')} — {s.get('description', '')[:80]}"
            for s in scenes
        )
    except Exception:
        scene_list = architect_json[:500]
    filled = template.replace("{scene_list}", scene_list).replace("{chapter_text}", chapter_text)
    return [
        Message(filled, role="user"),
    ]


@mcp.prompt()
def analyze_chronicler(architect_json: str, profiler_json: str, global_lore_excerpt: str, previous_chapters_summary: str = "") -> list[Message]:
    """Get the prompt for Pass 1.3 (Chronicler) to extract cross-chapter connections."""
    system_part, input_header = _split_chronicler_template()
    user_part = f"""{input_header}

### Architect (Scenes)
{architect_json}

### Profiler (Characters/Items/Dialogue)
{profiler_json}

### Global Lore Excerpt
{global_lore_excerpt}

### Previous Chapters Summary (Context)
{previous_chapters_summary}"""
    return [
        Message(system_part + "\n\n" + user_part, role="user"),
    ]


@mcp.prompt()
def sa_combined(chapter_text: str) -> list[Message]:
    """Get the prompt for SA Combined: direct micro-facts extraction from a single chapter."""
    import hashlib
    template = read_repo_file("prompts/sa_combined_prompt.md")
    source_hash = hashlib.sha256(chapter_text.encode("utf-8")).hexdigest()
    hash_note = (
        f"\n\n## REQUIRED: _source_hash\n"
        f'Include this EXACT field in your JSON output:\n'
        f'"_source_hash": "{source_hash}"\n'
        f"(This proves you read the actual chapter text — computed from its content)\n"
    )
    return [
        Message(template + hash_note + "\n\n## Chapter Text\n\n" + chapter_text, role="user"),
    ]


@mcp.prompt()
def sa_lore(part1_output: str, global_lore_excerpt: str, previous_chapters_summary: str = "") -> list[Message]:
    """Get the prompt for SA Lore matching: match combined facts against global lore."""
    template = read_repo_file("prompts/sa_lore_prompt.md")
    user_part = f"""## INPUT DATA

### Part 1 — SA Combined Output
```json
{part1_output}
```

### Global Lore Excerpt
{global_lore_excerpt}

### Previous Chapters Summary
{previous_chapters_summary}"""
    return [
        Message(template + "\n\n" + user_part, role="user"),
    ]


if __name__ == "__main__":
    mcp.run()
