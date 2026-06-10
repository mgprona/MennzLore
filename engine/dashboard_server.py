#!/usr/bin/env python3
"""
MennzLore Dashboard Server
==========================
A simple HTTP server that serves the dashboard frontend and provides JSON APIs
to explore project metadata, spatial maps, and micro-facts.
"""
import os
import re
import json
import glob
import http.server
import socketserver
import urllib.parse

from pathlib import Path
PORT = 8000
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard")

# Dynamic PROJECTS_ROOT detection
PROJECTS_ROOT = os.getenv("MENNZLORE_PROJECTS_ROOT", None)
if not PROJECTS_ROOT:
    candidates = [
        os.path.join(os.path.expanduser("~"), "lore-projects"),
        os.path.join(os.path.expanduser("~"), "Desktop", "projects"),
        os.getcwd(),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ]
    for c in candidates:
        if os.path.exists(c):
            has_project = False
            try:
                for sub in os.listdir(c):
                    subpath = os.path.join(c, sub)
                    if os.path.isdir(subpath):
                        if os.path.isdir(os.path.join(subpath, "micro_facts")) or os.path.isdir(os.path.join(subpath, "analysis", "micro_facts")):
                            has_project = True
                            break
            except Exception:
                pass
            if has_project:
                PROJECTS_ROOT = c
                break
    if not PROJECTS_ROOT:
        PROJECTS_ROOT = os.path.join(os.path.expanduser("~"), "lore-projects")

print(f"[Dashboard Server] Projects root folder: {os.path.abspath(PROJECTS_ROOT)}")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Allow cross-origin requests for local debugging
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        # Parse path
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # 1. API Endpoint: List Projects
        # GET /api/projects
        if path == "/api/projects":
            projects = self.list_available_projects()
            self.send_json_response(projects)
            return
            
        # 2. API Endpoint: Project Manifest
        # GET /api/project/<project_name>
        project_match = re.match(r"^/api/project/([^/]+)$", path)
        if project_match:
            project_name = project_match.group(1)
            manifest = self.get_project_manifest(project_name)
            self.send_json_response(manifest)
            return
            
        # 3. API Endpoint: SVG Map
        # GET /api/project/<project_name>/map
        map_match = re.match(r"^/api/project/([^/]+)/map$", path)
        if map_match:
            project_name = map_match.group(1)
            svg_content = self.get_project_map(project_name)
            if svg_content:
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.end_headers()
                self.wfile.write(svg_content.encode("utf-8"))
            else:
                self.send_error(404, "Map SVG not found")
            return
            
        # 4. API Endpoint: Episode micro-facts
        # GET /api/project/<project_name>/episode/<ep_id>
        ep_match = re.match(r"^/api/project/([^/]+)/episode/(EP\d+)$", path)
        if ep_match:
            project_name = ep_match.group(1)
            ep_id = ep_match.group(2)
            ep_data = self.get_episode_data(project_name, ep_id)
            if ep_data:
                self.send_json_response(ep_data)
            else:
                self.send_error(404, "Episode micro-facts not found")
            return

        # 4. Static Frontend serving
        if path == "/" or path == "":
            self.serve_static_file(os.path.join(DASHBOARD_DIR, "index.html"), "text/html")
        elif path == "/app.js":
            self.serve_static_file(os.path.join(DASHBOARD_DIR, "app.js"), "application/javascript")
        else:
            # Fallback to standard request handler (but restrict directory access)
            super().do_GET()

    def serve_static_file(self, filepath, content_type):
        if os.path.exists(filepath):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            with open(filepath, "r", encoding="utf-8") as f:
                self.wfile.write(f.read().encode("utf-8"))
        else:
            self.send_error(404, f"File {os.path.basename(filepath)} not found")

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def list_available_projects(self):
        projects = []
        if not os.path.exists(PROJECTS_ROOT):
            return projects
            
        for name in os.listdir(PROJECTS_ROOT):
            path = os.path.join(PROJECTS_ROOT, name)
            if os.path.isdir(path):
                mf_dir = os.path.join(path, "micro_facts")
                if not os.path.isdir(mf_dir):
                    mf_dir = os.path.join(path, "analysis", "micro_facts")
                if os.path.isdir(mf_dir):
                    proj_dir, prefix = self.get_project_dir_and_prefix(name)
                    title = name
                    src_json = os.path.join(proj_dir, "verification", f"{prefix}_source.json")
                    if os.path.exists(src_json):
                        try:
                            with open(src_json, "r", encoding="utf-8") as f:
                                src_data = json.load(f)
                            title = src_data.get("title", title)
                        except Exception:
                            pass
                            
                    projects.append({
                        "name": name,
                        "prefix": prefix,
                        "title": title
                    })
        return sorted(projects, key=lambda x: x["title"])

    def get_project_dir_and_prefix(self, project_name):
        proj_dir = os.path.join(PROJECTS_ROOT, project_name)
        prefix = project_name
        ver_dir = os.path.join(proj_dir, "verification")
        if os.path.isdir(ver_dir):
            src_files = glob.glob(os.path.join(ver_dir, "*_source.json"))
            if src_files:
                # Find the one that matches _source.json
                for s in src_files:
                    if s.endswith("_source.json"):
                        prefix = os.path.basename(s).replace("_source.json", "")
                        break
        return proj_dir, prefix

    def get_project_manifest(self, project_name):
        proj_dir, prefix = self.get_project_dir_and_prefix(project_name)
        if not os.path.exists(proj_dir):
            return {"error": f"Project folder not found: {project_name}"}
        
        # Look for micro_facts files
        mf_dir = os.path.join(proj_dir, "micro_facts")
        if not os.path.isdir(mf_dir):
            mf_dir = os.path.join(proj_dir, "analysis", "micro_facts")

        episodes = []
        locations_map = {}

        if os.path.isdir(mf_dir):
            pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
            for fpath in sorted(glob.glob(pattern)):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    ep_id = data.get("chapter_id", "")
                    title = data.get("chapter_title", "")
                    
                    scenes = data.get("scene_details", [])
                    events = data.get("key_plot_points", [])
                    
                    episodes.append({
                        "id": ep_id,
                        "title": title,
                        "scenes_count": len(scenes),
                        "events_count": len(events)
                    })
                    
                    # Catalog locations
                    for s in scenes:
                        loc_name = s.get("location", "").strip()
                        if loc_name:
                            loc_key = loc_name.lower().strip()
                            if loc_key not in locations_map:
                                locations_map[loc_key] = {"name": loc_name, "episodes": []}
                            if ep_id not in locations_map[loc_key]["episodes"]:
                                locations_map[loc_key]["episodes"].append(ep_id)
                except Exception as e:
                    print(f"Error reading manifest details for {fpath}: {e}")

        # Check for global_lore.json
        global_lore = {}
        gl_path = os.path.join(proj_dir, "verification", f"{prefix}_global_lore.json")
        if os.path.exists(gl_path):
            with open(gl_path, "r", encoding="utf-8") as f:
                global_lore = json.load(f)

        return {
            "project_name": project_name,
            "prefix": prefix,
            "global_lore": global_lore,
            "episodes": episodes,
            "locations_map": locations_map
        }

    def get_project_map(self, project_name):
        proj_dir, _ = self.get_project_dir_and_prefix(project_name)
        svg_path = os.path.join(proj_dir, "output", "spatial", "chart_map_skeleton.svg")
        if os.path.exists(svg_path):
            with open(svg_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def get_episode_data(self, project_name, ep_id):
        proj_dir, prefix = self.get_project_dir_and_prefix(project_name)
        
        # Look for micro_facts files
        mf_dir = os.path.join(proj_dir, "micro_facts")
        if not os.path.isdir(mf_dir):
            mf_dir = os.path.join(proj_dir, "analysis", "micro_facts")
            
        fpath = os.path.join(mf_dir, f"{prefix}_{ep_id}_micro_facts.json")
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

def run_server():
    # Allow port reuse to avoid 'address already in use' during quick re-runs
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"\n========================================================")
        print(f"MennzLore Interactive Dashboard server running!")
        print(f"Open your browser and visit: http://localhost:{PORT}")
        print(f"Press CTRL+C in terminal to stop the server.")
        print(f"========================================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")

if __name__ == "__main__":
    run_server()
