#!/usr/bin/env python3
"""
MennzLore MCP Server
====================
Provides Model Context Protocol (MCP) server interface for MennzLore project,
exposing tools, prompts, and resources to LLM clients.
"""
import sys
import os

# Ensure the repository root and engine directory are in the Python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT_DIR, "engine")
for d in (ROOT_DIR, ENGINE_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

from fastmcp import FastMCP

from engine.merge_to_micro_facts import merge_to_micro_facts
from engine.assemble_generic import assemble_lorebook
from engine.assemble_production_generic import build_production
from engine.chart_render_generic import build_chart
from engine.verify_names import verify_names
from engine.rag_memory import query_past_lore
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
def merge_micro_facts(prefix: str, ep_num: str, base_dir: str = ".") -> str:
    """
    Phase 4: Merge and validate the 3-pass JSON outputs (architect, profiler, chronicler) for a specific episode.
    
    Args:
        prefix: The project prefix name (e.g. 'jurgen').
        ep_num: The episode identifier (e.g. 'EP010').
        base_dir: The project root directory (defaults to current working directory).
    """
    try:
        result = merge_to_micro_facts(prefix, ep_num, base_dir)
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
def run_gutenberg_acquire(book_id: str, prefix: str, raw_dir: str, url_override: str = None) -> dict:
    """
    Phase 1: Download a Project Gutenberg ebook by ID, clean its headers/footers,
    and split it into sequential chapter files (EP001.txt, EP002.txt etc.).
    
    Args:
        book_id: The Project Gutenberg Book ID (e.g. '62' for A Princess of Mars).
        prefix: Project prefix to use.
        raw_dir: Absolute path to the destination directory to save raw chapter text files.
        url_override: Optional direct URL download override.
    """
    from engine.gutenberg_acquire import download_and_split
    try:
        result = download_and_split(book_id, prefix, raw_dir, url_override)
        return {"status": "success", "result": result}
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
def analyze_architect(chapter_text: str) -> str:
    """Get the prompt for Pass 1.1 (Architect) to extract scene structure."""
    template = read_repo_file("prompts/pass11_architect_prompt.md")
    return template.replace("{chapter_text}", chapter_text)

@mcp.prompt()
def analyze_profiler(chapter_text: str, scene_list: str) -> str:
    """Get the prompt for Pass 1.2 (Profiler) to extract characters and behaviors."""
    template = read_repo_file("prompts/pass12_profiler_prompt.md")
    return template.replace("{chapter_text}", chapter_text).replace("{scene_list}", scene_list)

@mcp.prompt()
def analyze_chronicler(architect_json: str, profiler_json: str, global_lore_excerpt: str) -> str:
    """Get the prompt for Pass 1.3 (Chronicler) to extract cross-chapter connections."""
    template = read_repo_file("prompts/pass13_chronicler_prompt.md")
    return (template
            .replace("{architect_json}", architect_json)
            .replace("{profiler_json}", profiler_json)
            .replace("{global_lore_excerpt}", global_lore_excerpt))

@mcp.prompt()
def synthesize_window(batch_range: str, episodes_data: str) -> str:
    """Get the prompt for Phase 4-P2 (Sliding Window Synthesis) to synthesize batches of episodes."""
    template = read_repo_file("prompts/pass2_sliding_window_prompt.md")
    return template

@mcp.prompt()
def sa_combined(chapter_text: str) -> str:
    """Get the prompt for SA Combined: direct micro-facts extraction from a single chapter."""
    template = read_repo_file("prompts/sa_combined_prompt.md")
    return template.replace("{chapter_text}", chapter_text)

@mcp.prompt()
def sa_lore(part1_output: str, global_lore_excerpt: str) -> str:
    """Get the prompt for SA Lore matching: match combined facts against global lore."""
    template = read_repo_file("prompts/sa_lore_prompt.md")
    return template.replace("{part1_output}", part1_output).replace("{global_lore_excerpt}", global_lore_excerpt)


if __name__ == "__main__":
    mcp.run()
