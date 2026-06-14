#!/usr/bin/env python3
"""
Standard Ebooks Acquisition Engine
===================================
Fetches public-domain books from Standard Ebooks (standardebooks.org)
via their GitHub repos. Each book is a git repo under the
`standardebooks` GitHub organization with XHTML-per-chapter structure.

Output: same `raw/<prefix>_full.txt` + `clean/<prefix>_EP###.txt` format
as PG acquisition, so the downstream pipeline (Phase 3+) works identically.

Key advantage over PG: NO Gutenberg boilerplate, NO OCR errors,
NO regex chapter splitting needed — chapters are already separate XHTML files.
"""

import os
import re
import sys
import html as html_mod
import json
import tempfile
import shutil
import subprocess
import time
from pathlib import Path

# ── Helpers ────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Lowercase, replace spaces/special chars with hyphens, strip non-alnum except hyphens."""
    text = text.lower()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9\-]', '', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def _se_repo_name(author: str, title: str) -> str:
    """
    Convert author + title to Standard Ebooks repo name.
    Pattern: `{first-last}_{book-title-with-hyphens}`
    Example: 'Arthur Conan Doyle' + 'A Study in Scarlet'
          → 'arthur-conan-doyle_a-study-in-scarlet'
    """
    author_slug = _slugify(author)
    title_slug = _slugify(title)
    return f"{author_slug}_{title_slug}"


def _find_se_repo(author: str, title: str) -> str | None:
    """
    Search GitHub for a Standard Ebooks repo matching author + title.
    Returns full repo name (e.g. 'standardebooks/arthur-conan-doyle_a-study-in-scarlet')
    or None if not found.
    """
    import urllib.request
    import urllib.parse

    # Strategy 1: Try direct repo name (fastest)
    repo_name = _se_repo_name(author, title)
    url = f"https://api.github.com/repos/standardebooks/{repo_name}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        resp = urllib.request.urlopen(req, timeout=5)
        if resp.status == 200:
            return f"standardebooks/{repo_name}"
    except Exception:
        pass

    # Strategy 2: Search by keywords (fallback)
    keywords = []
    # Take first 2-3 significant words from author
    author_parts = [w for w in author.lower().split() if len(w) > 2][:2]
    keywords.extend(author_parts)
    # Take first 2-3 significant words from title
    title_parts = [w for w in title.lower().split() if len(w) > 2]
    # Prefer non-stop words
    stop_words = {'the', 'a', 'an', 'of', 'in', 'to', 'and', 'or', 'for', 'with', 'by'}
    title_significant = [w for w in title_parts if w not in stop_words]
    keywords.extend(title_significant[:3])

    query = "org:standardebooks " + "+".join(keywords)
    search_url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&per_page=10"

    try:
        req = urllib.request.Request(search_url, headers={"Accept": "application/vnd.github+json"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        for repo in data.get("items", []):
            name = repo["full_name"]
            desc = (repo.get("description") or "").lower()
            # Check if description mentions both author and title
            if author.lower().split()[-1] in desc and title.lower().split()[0] in desc:
                return name
            # Broader: check repo name overlaps with expected slug
            expected_slug = _se_repo_name(author, title)
            if expected_slug[:20] in name:
                return name
        # Last resort: return first non-tool repo that matches some keywords
        for repo in data.get("items", []):
            name = repo["full_name"]
            # Filter out standardebooks/tools, standardebooks/web, standardebooks/manual
            if name.count("/") == 1 and name.split("/")[1] not in ("tools", "web", "manual", "miscellany"):
                return name
    except Exception:
        pass

    return None


def xhtml_to_clean_text(xhtml_path: str) -> str:
    """
    Convert a Standard Ebooks XHTML chapter file to clean plain text.
    Preserves paragraph structure, removes all HTML tags.
    """
    with open(xhtml_path, encoding="utf-8") as f:
        raw = f.read()

    # Extract body content
    body_match = re.search(r'<body[^>]*>(.*?)</body>', raw, re.DOTALL)
    if not body_match:
        return ""

    body = body_match.group(1)

    # Remove HTML tags, preserve paragraph breaks
    # Convert </p>, </div>, </section>, </hgroup>, </blockquote> to newlines
    body = re.sub(r'</(?:p|div|section|hgroup|blockquote|h[1-6])>', '\n\n', body)
    body = re.sub(r'<br\s*/?>', '\n', body)
    body = re.sub(r'<[^>]+>', '', body)
    body = html_mod.unescape(body)

    # Normalize non-breaking spaces → regular spaces
    body = body.replace('\xa0', ' ')

    # Clean up whitespace: strip leading/trailing whitespace per line
    lines = []
    for line in body.split('\n'):
        stripped = line.strip()
        lines.append(stripped if stripped else '')

    # Remove consecutive blank lines
    result = []
    prev_blank = False
    for line in lines:
        if line == '':
            if not prev_blank:
                result.append('')
                prev_blank = True
        else:
            result.append(line)
            prev_blank = False

    # Join and strip leading blank lines
    text = '\n'.join(result).strip()

    return text


def _get_chapter_title(xhtml_path: str) -> str:
    """Extract chapter title from XHTML <title> tag."""
    with open(xhtml_path, encoding="utf-8") as f:
        raw = f.read()
    m = re.search(r'<title>(.*?)</title>', raw)
    return m.group(1) if m else ""


def _read_content_opf(opf_path: str) -> list[dict]:
    """
    Parse content.opf to get the reading order of chapters.
    Returns list of {id, href, title} in spine order.
    Falls back to alphabetical sort if OPF not found.
    """
    if not os.path.exists(opf_path):
        return []

    with open(opf_path, encoding="utf-8") as f:
        raw = f.read()

    chapters = []
    # Find all <item> tags with id and href
    items = {}
    for m in re.finditer(r'<item\s+([^>]+?)\s*/>', raw):
        attrs = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', m.group(1)))
        if attrs.get("id") and attrs.get("href"):
            items[attrs["id"]] = attrs["href"]

    # Get spine order
    spine_refs = re.findall(r'<itemref\s+idref\s*=\s*"([^"]*)"', raw)
    for ref_id in spine_refs:
        href = items.get(ref_id)
        if href and href.startswith("text/") and "chapter" in href:
            chapters.append({
                "id": ref_id,
                "href": href,
            })

    return chapters


def _get_chapter_files(text_dir: str, opf_path: str | None = None) -> list[tuple[str, str, str]]:
    """
    Get ordered list of chapter XHTML files.
    Returns [(filename, title, filepath), ...] in reading order.
    Only includes chapter files (excludes colophon, imprint, titlepage, etc.)
    """
    # Try OPF spine order first
    if opf_path:
        opf_order = _read_content_opf(opf_path)
        if opf_order:
            result = []
            for entry in opf_order:
                # The href in OPF is relative to text/ dir, e.g. "text/chapter-1-1.xhtml"
                # or just "chapter-1-1.xhtml"
                filename = os.path.basename(entry["href"])
                filepath = os.path.join(text_dir, filename)
                if os.path.exists(filepath):
                    title = _get_chapter_title(filepath)
                    result.append((filename, title, filepath))
            if result:
                return result

    # Fallback: alphabetical sort of chapter-* files
    chapter_files = sorted([
        f for f in os.listdir(text_dir)
        if f.endswith(".xhtml") and f.startswith("chapter-")
    ])

    result = []
    for f in chapter_files:
        filepath = os.path.join(text_dir, f)
        title = _get_chapter_title(filepath)
        result.append((f, title, filepath))

    return result


def fetch_se(repo_full_name: str, base_dir: str = ".") -> dict:
    """
    Clone a Standard Ebooks repo and extract chapter text.

    Args:
        repo_full_name: GitHub repo name, e.g. 'standardebooks/arthur-conan-doyle_a-study-in-scarlet'
        base_dir: Directory under which the project folder is created.

    Returns:
        dict with project_dir, prefix, chapter_count, total_chars, source, status
    """
    # Determine prefix from repo name
    repo_short = repo_full_name.split("/")[-1]
    # Remove leading author slug part for prefix (keep last 30 chars max)
    # e.g. 'arthur-conan-doyle_a-study-in-scarlet' → 'a-study-in-scarlet'
    if "_" in repo_short:
        prefix = repo_short.split("_", 1)[-1]
    else:
        prefix = repo_short
    # Shorten prefix if too long
    prefix = prefix[:40].strip("-")

    # Create project directory
    project_dir = os.path.join(base_dir, prefix)
    os.makedirs(project_dir, exist_ok=True)

    # Clone repo into temp directory
    temp_dir = tempfile.mkdtemp(prefix="se_")
    git_url = f"https://github.com/{repo_full_name}.git"

    try:
        result = subprocess.run(
            ["git", "clone", "--depth=1", git_url, temp_dir],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {
                "status": "error",
                "message": f"Git clone failed: {result.stderr.strip()[:200]}",
            }

        # Find text directory
        text_dir = os.path.join(temp_dir, "src", "epub", "text")
        opf_path = os.path.join(temp_dir, "src", "epub", "content.opf")

        if not os.path.isdir(text_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {
                "status": "error",
                "message": f"No src/epub/text/ directory found in {repo_full_name}",
            }

        # Determine author and title from repo metadata or path
        # Try to parse from content.opf
        author_name = ""
        book_title = ""
        if os.path.exists(opf_path):
            with open(opf_path, encoding="utf-8") as f:
                opf_raw = f.read()
            # Title
            tm = re.search(r'<dc:title[^>]*>(.*?)</dc:title>', opf_raw)
            if tm:
                book_title = tm.group(1).strip()
            # Author
            am = re.search(r'<dc:creator[^>]*>(.*?)</dc:creator>', opf_raw)
            if am:
                author_name = am.group(1).strip()

        # Get chapter files in order
        chapters = _get_chapter_files(text_dir, opf_path)

        if not chapters:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {
                "status": "error",
                "message": f"No chapter files found in {repo_full_name}",
            }

        # Create raw/ and clean/ directories
        raw_dir = os.path.join(project_dir, "raw")
        clean_dir = os.path.join(project_dir, "clean")
        verification_dir = os.path.join(project_dir, "verification")
        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(clean_dir, exist_ok=True)
        os.makedirs(verification_dir, exist_ok=True)

        # Write full text file
        full_text_parts = []
        ep_mapping = []

        for i, (filename, title, filepath) in enumerate(chapters):
            ep_id = f"EP{i+1:03d}"
            clean_text = xhtml_to_clean_text(filepath)
            full_text_parts.append(clean_text)

            # Write individual chapter
            clean_filename = f"{prefix}_{ep_id}.txt"
            clean_path = os.path.join(clean_dir, clean_filename)
            with open(clean_path, "w", encoding="utf-8") as f:
                f.write(clean_text)

            ep_mapping.append({
                "ep_id": ep_id,
                "title": title,
                "source_file": filename,
                "clean_file": clean_filename,
                "char_count": len(clean_text),
            })

        # Write raw full text
        full_text = "\n\n".join(full_text_parts)
        full_path = os.path.join(raw_dir, f"{prefix}_full.txt")
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        # Write provenance
        provenance = {
            "source": "Standard Ebooks",
            "repo": repo_full_name,
            "git_url": git_url,
            "author": author_name,
            "title": book_title,
            "chapter_count": len(chapters),
            "total_chars": len(full_text),
            "ep_mapping": ep_mapping,
            "acquired_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        prov_path = os.path.join(project_dir, "provenance.json")
        with open(prov_path, "w", encoding="utf-8") as f:
            json.dump(provenance, f, indent=2, ensure_ascii=False)

        # Write metadata as global_lore stub
        if book_title or author_name:
            global_lore_stub = {
                "source": "Standard Ebooks",
                "book_metadata": {
                    "title": book_title,
                    "author": author_name,
                    "source": f"Standard Ebooks ({repo_full_name})",
                },
                "characters": [],
                "settings": [],
                "themes": [],
                "summary": f"Automatically acquired from Standard Ebooks: {repo_full_name}",
            }
            gl_path = os.path.join(verification_dir, f"{prefix}_global_lore.json")
            with open(gl_path, "w", encoding="utf-8") as f:
                json.dump(global_lore_stub, f, indent=2, ensure_ascii=False)

        # Clean up temp
        shutil.rmtree(temp_dir, ignore_errors=True)

        return {
            "status": "success",
            "source": "Standard Ebooks",
            "project_dir": project_dir,
            "prefix": prefix,
            "repo": repo_full_name,
            "author": author_name,
            "title": book_title,
            "chapter_count": len(chapters),
            "total_chars": len(full_text),
            "chapters": [e["ep_id"] for e in ep_mapping],
        }

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {"status": "error", "message": "Git clone timed out (60s)"}
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {"status": "error", "message": str(e)}


def fetch_se_by_title(title: str, author: str, base_dir: str = ".") -> dict:
    """
    Search Standard Ebooks catalog by title + author, then fetch.

    This is the primary entry point. It searches GitHub's standardebooks org
    for a matching repo, then clones and extracts it.

    Returns same dict as fetch_se(), or error if not found.
    """
    result = _find_se_repo(author, title)
    if result is None:
        return {
            "status": "not_found",
            "message": f"No Standard Ebooks edition found for '{title}' by '{author}'",
        }

    return fetch_se(result, base_dir)


# ── CLI test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python acquire_se.py <title> <author> [base_dir]")
        sys.exit(1)

    title = sys.argv[1]
    author = sys.argv[2]
    base_dir = sys.argv[3] if len(sys.argv) > 3 else "."

    result = fetch_se_by_title(title, author, base_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))