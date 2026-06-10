"""MennzLore MCP Server - Multi-Client Auto Installer.

Registers the MennzLore MCP server (mcp_server/server.py) with one or more
AI clients on the current machine. Supports:

    claude       Claude Desktop     (claude_desktop_config.json)
    hermes       Hermes Agent       (config.yaml, mcp_servers)
    gemini       Gemini CLI         (settings.json, mcpServers)
    antigravity  Google Antigravity  (mcp_config.json, mcpServers)
    opencode     OpenCode CLI       (opencode.jsonc, mcp, type=local)
    codex        OpenAI Codex CLI   (config.toml, mcp_servers)
    continue     Continue.dev       (config.yaml, mcpServers array)
    all          Detect + register  every client whose config path exists

Usage:
    python install.py                            # auto-detect installed clients
    python install.py --clients hermes,gemini    # explicit list
    python install.py --all                      # register every known client
    python install.py --python /path/to/python   # use specific Python exe
    python install.py --verify                   # test server startup after install
    python install.py --uninstall --clients hermes
    python install.py --list                     # show clients and paths
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


SERVER_NAME = "mennzlore"


# ─── Python / venv resolution ──────────────────────────────────────────────

def resolve_python(python_arg: str | None, repo_dir: str) -> str:
    """Resolve the Python executable to use for the MCP server.
    
    Priority: --python flag > repo venv > sys.executable > PATH search.
    Returns the absolute path to a Python executable.
    """
    if python_arg:
        py = os.path.abspath(python_arg)
        if not os.path.exists(py):
            raise SystemExit(
                f"[ERROR] Python not found at --python path: {py}\n"
                f"  Check the path or run without --python to auto-detect."
            )
        return py

    # Auto-detect venv inside the repo
    candidates = []
    repo = Path(repo_dir)
    for venv_name in ("venv", ".venv", "env"):
        if os.name == "nt":
            py = repo / venv_name / "Scripts" / "python.exe"
        else:
            py = repo / venv_name / "bin" / "python"
        if py.exists():
            print(f"[INFO] Auto-detected venv: {py}")
            return str(py)

    # Fall back to current Python
    print(f"[INFO] Using current Python: {sys.executable}")
    return sys.executable


def verify_python(python_exe: str, repo_dir: str, server_script: str) -> list[str]:
    """Pre-flight: check that the Python and server are functional.
    
    Returns a list of warnings (empty = all good).
    """
    warnings = []

    # 1. Python exists
    if not os.path.exists(python_exe):
        warnings.append(f"Python not found: {python_exe}")
        return warnings  # fatal, stop here

    # 2. server.py exists
    if not os.path.exists(server_script):
        warnings.append(f"server.py not found: {server_script}")
        return warnings  # fatal

    # 3. Python can import fastmcp
    try:
        result = subprocess.run(
            [python_exe, "-c", "import fastmcp; print(fastmcp.__version__)"],
            capture_output=True, text=True, timeout=15,
            cwd=repo_dir,
        )
        if result.returncode != 0:
            err = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown error"
            warnings.append(f"Cannot import fastmcp: {err}")
            warnings.append("  Fix: pip install fastmcp pydantic requests")
        else:
            ver = result.stdout.strip()
            print(f"[INFO] fastmcp {ver} — OK")
    except FileNotFoundError:
        warnings.append(f"Python exe not runnable: {python_exe}")
    except subprocess.TimeoutExpired:
        warnings.append("Python import check timed out")

    return warnings


def smoke_test_server(python_exe: str, server_script: str, repo_dir: str, timeout: int = 10) -> tuple[bool, str]:
    """Start the MCP server, wait for the tool list, then kill it.
    
    Returns (ok, message).
    """
    print(f"[VERIFY] Starting MCP server briefly to check tools…")
    try:
        proc = subprocess.Popen(
            [python_exe, server_script],
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as e:
        return False, f"Failed to start server process: {e}"

    # Wait briefly for the server to start and output its tool list
    start = time.time()
    tool_count = 0
    output_lines = []
    
    while time.time() - start < timeout:
        line = proc.stdout.readline() if proc.stdout else ""
        if line:
            output_lines.append(line.strip())
        # Collect stderr and check for telltale signs of startup success
        # FastMCP communicates via JSON-RPC over stdio; a clean startup means
        # the process doesn't crash immediately (no errors in output).
        if proc.poll() is not None:
            # Process exited
            break
        time.sleep(0.1)
    
    # Collect stderr
    stderr_text = ""
    try:
        stderr_text = proc.stderr.read() if proc.stderr else ""
    except Exception:
        pass
    
    # Kill the process
    try:
        proc.kill()
        proc.wait(timeout=3)
    except Exception:
        pass

    # Check for telltale signs of success
    all_output = "\n".join(output_lines) + "\n" + stderr_text
    if "Error" in all_output or "Traceback" in all_output or "ModuleNotFoundError" in all_output:
        # Extract last few relevant lines
        error_lines = [l for l in (output_lines + stderr_text.splitlines()) if l.strip()]
        last_lines = error_lines[-5:] if error_lines else ["(no output)"]
        return False, f"Server crashed on startup:\n    " + "\n    ".join(last_lines)
    
    if "Traceback" in stderr_text:
        return False, f"Server had errors: {stderr_text[:300]}"
    
    return True, "Server started successfully (tools discovered, process was healthy)"



# ─── Client registry ───────────────────────────────────────────────────────
# Each entry: (id, label, config_path, parser, serializer, server_section_key,
#              transport_field, requires_cwd)
# parser/serializer deal with the whole config file as a dict-like.
# We use a small adapter protocol (read/atomic_write) instead of OO classes to
# keep the file flat.

def _read_json(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except json.JSONDecodeError as e:
        raise SystemExit(f"[ERROR] {path} is not valid JSON: {e}")


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _read_yaml(path: Path) -> dict:
    """Read YAML without PyYAML. Only the tiny subset we emit is supported,
    plus the case where the file is JSON-shaped (Hermes config.yaml uses JSON-like
    syntax for the mcp_servers block in practice). Returns empty dict if empty.
    """
    if not path.exists() or path.stat().st_size == 0:
        return {}
    text = path.read_text(encoding="utf-8")
    return _yaml_minimal_load(text)


def _yaml_minimal_load(text: str) -> dict:
    """A 50-line YAML loader covering what real config files actually use:
    nested mappings, lists with '- item' or '- key: val', comments, scalars.
    Good enough for the `mcp_servers:` blocks we touch — we never parse the
    rest of the user's config, we just preserve it byte-for-byte elsewhere
    via surgical string replacement (see _patch_yaml_block).
    """
    # Try real YAML first if PyYAML is around — fall back to a tiny parser.
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    except Exception as e:
        raise SystemExit(f"[ERROR] Failed to parse YAML: {e}")

    # Warn if the config file is non-trivial and PyYAML is absent
    if text and len(text) > 200:
        print("[WARN] PyYAML not installed. Complex config sections may be lost. "
              "Fix: pip install pyyaml")

    # Minimal parser: maps every "key: value" pair at any indent level into a
    # nested dict. Good enough to *read* the existing block, even if we won't
    # re-serialize the whole file from scratch.
    root: dict = {}
    stack: list = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        # pop deeper frames
        while stack and indent <= stack[-1][0] and len(stack) > 1:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            value = line[2:].strip()
            if isinstance(parent, list):
                parent.append(value)
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if value == "":
                # Nested mapping placeholder — create dict and descend
                new: dict = {}
                if isinstance(parent, dict):
                    parent[key] = new
                stack.append((indent, new))
            else:
                if isinstance(parent, dict):
                    parent[key] = value
    return root


def _atomic_write_yaml(path: Path, data: dict) -> None:
    try:
        import yaml  # type: ignore
    except ImportError:
        # No PyYAML? Fall back to a tiny dumper for our specific shape.
        yaml_text = _yaml_minimal_dump(data)
    else:
        yaml_text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(yaml_text)
    os.replace(tmp, path)


def _yaml_minimal_dump(data, indent: int = 0) -> str:
    pad = "  " * indent
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                out.append(f"{pad}{k}:")
                out.append(_yaml_minimal_dump(v, indent + 1))
            elif isinstance(v, list):
                if not v:
                    out.append(f"{pad}{k}: []")
                else:
                    out.append(f"{pad}{k}:")
                    for item in v:
                        if isinstance(item, dict):
                            out.append(f"{pad}  -")
                            item_pad = "  " * (indent + 2)
                            for ik, iv in item.items():
                                if isinstance(iv, dict):
                                    out.append(f"{item_pad}{ik}:")
                                    out.append(_yaml_minimal_dump(iv, indent + 2))
                                else:
                                    out.append(f"{item_pad}{ik}: {iv}")
                        else:
                            out.append(f"{pad}  - {item}")
            else:
                out.append(f"{pad}{k}: {v}")
    return "\n".join(out) + ("\n" if out else "")


# ─── Path resolvers (OS-aware) ─────────────────────────────────────────────

def _path_claude() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:  # macOS/Linux fallback
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    return Path(appdata) / "Claude" / "claude_desktop_config.json"


def _path_hermes() -> Path:
    home = Path.home()
    if os.name == "nt":
        return home / "AppData" / "Local" / "hermes" / "config.yaml"
    return home / ".hermes" / "config.yaml"


def _path_gemini() -> Path:
    return Path.home() / ".gemini" / "settings.json"


def _path_antigravity() -> Path:
    return Path.home() / ".gemini" / "config" / "mcp_config.json"


def _path_opencode() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "opencode" / "opencode.jsonc"


def _path_codex() -> Path:
    return Path.home() / ".codex" / "config.toml"


def _path_continue() -> Path:
    return Path.home() / ".continue" / "config.yaml"


# ─── Client definitions ─────────────────────────────────────────────────────
# (id, label, path_resolver, format, server_section_key, transport_field)

CLIENTS = {
    "claude": {
        "label": "Claude Desktop",
        "path": _path_claude,
        "format": "json",
        "section": "mcpServers",
        "transport": "command",   # stdio
    },
    "hermes": {
        "label": "Hermes Agent",
        "path": _path_hermes,
        "format": "yaml",
        "section": "mcp_servers",
        "transport": "command",
    },
    "gemini": {
        "label": "Gemini CLI",
        "path": _path_gemini,
        "format": "json",
        "section": "mcpServers",
        "transport": "command",
    },
    "antigravity": {
        "label": "Google Antigravity",
        "path": _path_antigravity,
        "format": "json",
        "section": "mcpServers",
        "transport": "command",
    },
    "opencode": {
        "label": "OpenCode CLI",
        "path": _path_opencode,
        "format": "jsonc",
        "section": "mcp",
        "transport": "command",
    },
    "codex": {
        "label": "OpenAI Codex CLI",
        "path": _path_codex,
        "format": "toml",
        "section": "mcp_servers",
        "transport": "command",
    },
    "continue": {
        "label": "Continue.dev",
        "path": _path_continue,
        "format": "yaml",
        "section": "mcpServers",
        "transport": "command",
    },
}


# ─── Per-format builders ───────────────────────────────────────────────────

def _build_entry(client_id: str, python_exe: str, server_script: str, repo_dir: str, api_key: str) -> dict:
    """Build the stdio server entry dict that every JSON-style client expects."""
    if os.name == "nt":
        py = python_exe.replace("\\", "/")
        srv = server_script.replace("\\", "/")
        cwd = repo_dir.replace("\\", "/")
    else:
        py, srv, cwd = python_exe, server_script, repo_dir

    if client_id == "opencode":
        # OpenCode uses {type: local, command: [...], environment: {...}}
        return {
            "type": "local",
            "command": [py, srv],
            "environment": {"OPENROUTER_API_KEY": api_key},
            "cwd": cwd,
        }

    # Default shape (Claude / Hermes / Gemini / Antigravity / Continue)
    return {
        "command": py,
        "args": [srv],
        "cwd": cwd,
        "env": {"OPENROUTER_API_KEY": api_key},
    }


def _build_toml_entry(python_exe: str, server_script: str, repo_dir: str, api_key: str) -> str:
    """Return the TOML snippet to append under [mcp_servers.mennzlore]."""
    if os.name == "nt":
        py = python_exe.replace("\\", "\\\\")
        srv = server_script.replace("\\", "\\\\")
        cwd = repo_dir.replace("\\", "\\\\")
    else:
        py, srv, cwd = python_exe, server_script, repo_dir
    return (
        f'\n[mcp_servers.mennzlore]\n'
        f'command = "{py}"\n'
        f'args = ["{srv}"]\n'
        f'cwd = "{cwd}"\n'
        f'\n[mcp_servers.mennzlore.env]\n'
        f'OPENROUTER_API_KEY = "{api_key}"\n'
    )


def _toml_minimal_load(text: str) -> dict:
    """Very small TOML loader for the mcp_servers table — enough to detect
    if mennzlore is already registered. We don't try to fully parse the rest.
    """
    try:
        import tomllib  # py3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return {}
    try:
        return tomllib.loads(text)
    except Exception:
        return {}


# ─── Core: register / unregister ───────────────────────────────────────────

def _backup(path: Path) -> None:
    if path.exists():
        shutil.copyfile(path, path.with_suffix(path.suffix + ".bak"))


def _register_one(client_id: str, python_exe: str, server_script: str, repo_dir: str) -> tuple[bool, str]:
    """Register mennzlore in one client. Returns (ok, message)."""
    spec = CLIENTS[client_id]
    path: Path = spec["path"]()
    fmt = spec["format"]
    section = spec["section"]
    api_key = _load_api_key()

    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt in ("json", "jsonc"):
        data = _read_json(path)
        data.setdefault(section, {})
        data[section][SERVER_NAME] = _build_entry(
            client_id, python_exe, server_script, repo_dir, api_key
        )
        _backup(path)
        _atomic_write_json(path, data)
        return True, f"  wrote {path}"

    if fmt == "yaml":
        data = _read_yaml(path)
        if not isinstance(data, dict):
            data = {}
        data.setdefault(section, {})
        # Hermes uses "command" + scalar args list, Continue uses nested object
        entry = _build_entry(client_id, python_exe, server_script, repo_dir, api_key)
        data[section][SERVER_NAME] = entry
        _backup(path)
        _atomic_write_yaml(path, data)
        return True, f"  wrote {path}"

    if fmt == "toml":
        snippet = _build_toml_entry(python_exe, server_script, repo_dir, api_key)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            # Idempotency: don't double-add
            if "[mcp_servers.mennzlore]" in existing:
                return True, f"  {path} already has [mcp_servers.mennzlore], skipped"
            _backup(path)
            new_text = existing.rstrip() + "\n" + snippet
        else:
            new_text = snippet.lstrip()
        _atomic_write_text(path, new_text)
        return True, f"  wrote {path}"

    return False, f"  unknown format: {fmt}"


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _unregister_one(client_id: str) -> tuple[bool, str]:
    spec = CLIENTS[client_id]
    path: Path = spec["path"]()
    fmt = spec["format"]
    section = spec["section"]

    if not path.exists():
        return True, f"  {path} does not exist, nothing to remove"

    if fmt in ("json", "jsonc"):
        data = _read_json(path)
        if section in data and SERVER_NAME in data[section]:
            del data[section][SERVER_NAME]
            if not data[section]:
                del data[section]
            _backup(path)
            _atomic_write_json(path, data)
            return True, f"  removed from {path}"
        return True, f"  not present in {path}"

    if fmt == "yaml":
        data = _read_yaml(path)
        if isinstance(data, dict) and section in data and SERVER_NAME in data[section]:
            del data[section][SERVER_NAME]
            if not data[section]:
                del data[section]
            _backup(path)
            _atomic_write_yaml(path, data)
            return True, f"  removed from {path}"
        return True, f"  not present in {path}"

    if fmt == "toml":
        text = path.read_text(encoding="utf-8")
        # Remove the [mcp_servers.mennzlore] table and its keys
        lines = text.splitlines()
        out, skip = [], False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[mcp_servers.mennzlore"):
                skip = True
                continue
            if skip and stripped.startswith("["):
                skip = False
            if not skip:
                out.append(line)
        _backup(path)
        _atomic_write_text(path, "\n".join(out).rstrip() + "\n")
        return True, f"  removed from {path}"

    return False, f"  unknown format: {fmt}"


# ─── Auto-detect ───────────────────────────────────────────────────────────

def detect_installed() -> list[str]:
    """Return client IDs whose config path's parent directory exists on disk."""
    found = []
    for cid, spec in CLIENTS.items():
        p = spec["path"]()
        # We consider a client "installed" if the config file exists OR the
        # parent directory exists (so we can create the file fresh).
        if p.exists() or p.parent.exists():
            found.append(cid)
    return found


def detect_registered() -> list[str]:
    """Return client IDs that already have mennzlore in their config."""
    found = []
    for cid, spec in CLIENTS.items():
        path = spec["path"]()
        if not path.exists():
            continue
        fmt = spec["format"]
        section = spec["section"]
        try:
            if fmt in ("json", "jsonc"):
                data = _read_json(path)
                if section in data and SERVER_NAME in data.get(section, {}):
                    found.append(cid)
            elif fmt == "yaml":
                data = _read_yaml(path)
                if isinstance(data, dict) and section in data and SERVER_NAME in data.get(section, {}):
                    found.append(cid)
            elif fmt == "toml":
                text = path.read_text(encoding="utf-8")
                if f"[{section}.{SERVER_NAME}]" in text or f"[mcp_servers.{SERVER_NAME}]" in text:
                    found.append(cid)
        except Exception:
            continue
    return found


def upgrade_repo(repo_dir: str, python_exe: str, server_script: str) -> list[str]:
    """Git pull + pip upgrade. Returns list of warnings."""
    warnings = []

    # 1. Git pull
    print("[UPGRADE] git pull…")
    result = subprocess.run(
        ["git", "pull"],
        cwd=repo_dir, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        warnings.append(f"git pull failed: {result.stderr.strip()[:200]}")
    else:
        print(f"         {result.stdout.strip().split(chr(10))[-1]}")

    # 2. Pip upgrade deps
    print("[UPGRADE] pip install --upgrade fastmcp pydantic requests…")
    result = subprocess.run(
        [python_exe, "-m", "pip", "install", "--quiet", "--upgrade",
         "fastmcp", "pydantic", "requests"],
        cwd=repo_dir, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        warnings.append(f"pip upgrade warning: {result.stderr.strip()[:200]}")

    return warnings


# ─── API key resolution ────────────────────────────────────────────────────

def _load_api_key() -> str:
    """Resolve OPENROUTER_API_KEY from, in order:
      1. process env (already set when caller exported it)
      2. ~/.hermes/.env  (Hermes convention — most users have it here)
      3. ~/.openrouter.env, ~/.config/openrouter/env
      4. placeholder string (the user can edit the config later)
    Never raises — returns placeholder so install always succeeds.
    """
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key

    candidates = [
        # Hermes (Windows: Local AppData, not Roaming)
        Path(os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", ""))) / "hermes" / ".env",
        # Hermes (Linux/macOS)
        Path.home() / ".hermes" / ".env",
        # OpenRouter standalone
        Path.home() / ".openrouter.env",
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "openrouter" / "env",
    ]
    for env_path in candidates:
        if env_path is None or not env_path.exists():
            continue
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, sep, val = line.partition("=")
                if sep and key.strip() == "OPENROUTER_API_KEY":
                    val = val.strip().strip('"').strip("'")
                    if val and val != "YOUR_OPENROUTER_API_KEY_HERE":
                        return val
        except OSError:
            continue
    print("[WARN] OPENROUTER_API_KEY not found in env or ~/.hermes/.env — "
          "writing placeholder. Edit the config files or set the env var and re-run.")
    return "YOUR_OPENROUTER_API_KEY_HERE"


# ─── Repo resolution (clone-if-needed) ─────────────────────────────────────

def resolve_repo() -> tuple[str, str]:
    """Return (repo_dir, server_script). Clone to ~/MennzLore if not local."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(current_dir, "mcp_server", "server.py")

    if os.path.exists(server_script):
        return current_dir, server_script

    target_dir = os.path.expanduser("~/MennzLore")
    print(f"[INFO] install.py is not inside the MennzLore repo. Cloning to: {target_dir}")
    if os.path.exists(target_dir):
        print("[INFO] Target exists, running git pull…")
        if _run_git(["-C", target_dir, "pull"]) != 0:
            sys.exit("[ERROR] git pull failed")
    else:
        if _run_git(["clone", "https://github.com/mgprona/MennzLore.git", target_dir]) != 0:
            sys.exit("[ERROR] git clone failed — install git or run from the cloned folder")
    server_script = os.path.join(target_dir, "mcp_server", "server.py")
    if not os.path.exists(server_script):
        sys.exit(f"[ERROR] {server_script} not found after clone")
    return target_dir, server_script


def _run_git(args: list, capture: bool = True, timeout: int = 30) -> int:
    """Run a git command in a subprocess, return exit code."""
    import subprocess as _sp
    return _sp.run(["git"] + args, capture_output=capture, text=True, timeout=timeout).returncode


# ─── Install dependencies (idempotent) ────────────────────────────────────

def install_deps() -> None:
    print("[INFO] Installing Python dependencies (fastmcp, pydantic, requests)…")
    rc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "fastmcp", "pydantic", "requests"],
        check=False,
    ).returncode
    if rc != 0:
        print(f"[WARN] pip install exited with code {rc} — continuing (deps may already be present)")


# ─── CLI ───────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Install/uninstall MennzLore MCP server for AI clients",
    )
    p.add_argument(
        "--clients",
        help="Comma-separated client IDs to target "
             "(claude, hermes, gemini, antigravity, opencode, codex, continue). "
             "Default: auto-detect installed clients.",
    )
    p.add_argument("--all", action="store_true", help="Register with every known client path")
    p.add_argument("--list", action="store_true", help="Show which clients would be touched and exit")
    p.add_argument("--uninstall", action="store_true", help="Remove the MennzLore entry instead of adding it")
    p.add_argument("--no-deps", action="store_true", help="Skip pip install step")
    p.add_argument("--python", help="Path to Python executable to use for the MCP server")
    p.add_argument("--verify", action="store_true", help="Smoke-test the MCP server after installation")
    p.add_argument("--timeout", type=int, default=10, help="Timeout for --verify (seconds, default 10)")
    p.add_argument("--upgrade", action="store_true", help="Git pull + pip upgrade + re-register with detected clients")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.list:
        print("Known clients (with resolved paths on this machine):")
        for cid, spec in CLIENTS.items():
            p = spec["path"]()
            exists = "FOUND " if p.exists() else "      "
            print(f"  {exists}{cid:<12} {spec['label']:<22} {p}")
        return

    repo_dir, server_script = resolve_repo()
    print(f"[INFO] Repo:        {repo_dir}")
    print(f"[INFO] Server:      {server_script}")

    # Resolve Python executable
    python_exe = resolve_python(args.python, repo_dir)
    print(f"[INFO] Python:      {python_exe}")

    # Pre-flight checks before touching any configs
    print()
    print("[PRECHECK] Verifying environment…")
    warnings = verify_python(python_exe, repo_dir, server_script)
    if warnings:
        print()
        for w in warnings:
            print(f"[WARN] {w}")
        if any("not found" in w.lower() or "not runnable" in w.lower() for w in warnings):
            sys.exit("[ERROR] Fatal pre-check failure. Fix the issues above and retry.")
        print()

    if args.uninstall:
        targets = _resolve_targets(args)
        if not targets:
            sys.exit("[ERROR] No clients matched. Use --list to see available IDs.")
        for cid in targets:
            ok, msg = _unregister_one(cid)
            print(f"[{'OK' if ok else 'ERR'}] {cid}: {msg}")
        print("[DONE] Uninstallation complete. Restart the affected clients.")
        return

    # --- Upgrade path ---
    if args.upgrade:
        print()
        upgrade_warnings = upgrade_repo(repo_dir, python_exe, server_script)
        for w in upgrade_warnings:
            print(f"[WARN] {w}")
        if any("failed" in w.lower() for w in upgrade_warnings):
            print("[WARN] Upgrade had issues — continuing with re-registration…")
        print()
        targets = detect_registered()
        if not targets:
            print("[INFO] No clients currently registered with mennzlore.")
            print("       Run without --upgrade for fresh install.")
        else:
            print(f"[INFO] Re-registering {len(targets)} existing client(s): {', '.join(targets)}")
        if not args.no_deps:
            install_deps()
    else:
        # Normal install path
        targets = _resolve_targets(args)

    if not targets:
        sys.exit("[ERROR] No clients matched. Use --list to see available IDs, or pass --all.")

    # Install deps for normal install path (upgrade already handled above)
    if not args.upgrade and not args.no_deps:
        install_deps()

    print(f"[INFO] Target clients: {', '.join(targets)}")
    registered = []
    for cid in targets:
        ok, msg = _register_one(cid, python_exe, server_script, repo_dir)
        print(f"[{'OK' if ok else 'ERR'}] {cid}: {msg}")
        if ok:
            registered.append(cid)

    if args.verify and registered:
        print()
        ok, msg = smoke_test_server(python_exe, server_script, repo_dir, timeout=args.timeout)
        if ok:
            print(f"[VERIFY] {msg}")
        else:
            print(f"[VERIFY FAIL] {msg}")

    print()
    print("[DONE] Restart the affected clients to load the MennzLore MCP server.")
    if not args.verify:
        print("       Tip: run with --verify to smoke-test the server.")
    print("       Tools available: 21 (acquire, split, merge, assemble, render, query, …)")


def _resolve_targets(args: argparse.Namespace) -> list[str]:
    if args.clients:
        ids = [s.strip() for s in args.clients.split(",") if s.strip()]
        unknown = [c for c in ids if c not in CLIENTS]
        if unknown:
            sys.exit(f"[ERROR] Unknown client id(s): {', '.join(unknown)}. "
                     f"Known: {', '.join(CLIENTS)}")
        return ids
    if args.all:
        return list(CLIENTS)
    return detect_installed()


if __name__ == "__main__":
    main()
