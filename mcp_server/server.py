#!/usr/bin/env python3
"""
MennzLore MCP Server
====================
Provides Model Context Protocol (MCP) server interface for MennzLore project,
exposing tools, prompts, and resources to LLM clients.
"""
import sys
import os
import asyncio

# Ensure the repository root and engine directory are in the Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT_DIR, "engine")
for d in (ROOT_DIR, ENGINE_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from fastmcp import FastMCP
from fastmcp.prompts import Message

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
import subprocess
import socket


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
        subprocess.Popen([sys.executable, server_path], close_fds=True)
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
        
        kg = load_knowledge_graph(project_dir, prefix)
        
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
        Message(SYSTEM_PROMPT + "\n\n" + user_content, role="user")
    ]

@mcp.prompt()
def analyze_chronicler(architect_json: str, profiler_json: str, global_lore_excerpt: str, previous_chapters_summary: str = "") -> list[Message]:
    """Get the prompt for Pass 1.3 (Chronicler) to extract cross-chapter connections."""
    template = read_repo_file("prompts/pass13_chronicler_prompt.md")
    combined = (template
                .replace("{architect_json}", architect_json)
                .replace("{profiler_json}", profiler_json)
                .replace("{global_lore_excerpt}", global_lore_excerpt)
                .replace("{previous_chapters_summary}", previous_chapters_summary))
    return [
        Message(combined, role="user")
    ]

@mcp.prompt()
def sa_combined(chapter_text: str) -> list[Message]:
    """Get the prompt for SA Combined: direct micro-facts extraction from a single chapter."""
    template = read_repo_file("prompts/sa_combined_prompt.md")
    combined = template + "\n\n## CHAPTER TEXT\n\n" + chapter_text
    return [
        Message(combined, role="user")
    ]

@mcp.prompt()
def sa_lore(part1_output: str, global_lore_excerpt: str, previous_chapters_summary: str = "") -> list[Message]:
    """Get the prompt for SA Lore matching: match combined facts against global lore."""
    template = read_repo_file("prompts/sa_lore_prompt.md")
    combined = (template
                .replace("{part1_output}", part1_output)
                .replace("{global_lore_excerpt}", global_lore_excerpt)
                .replace("{previous_chapters_summary}", previous_chapters_summary))
    return [
        Message(combined, role="user")
    ]


if __name__ == "__main__":
    mcp.run()
