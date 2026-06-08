#!/usr/bin/env python3
"""
Phase 1 — Fetch Raw
====================
Search by title + author → download raw text from PG-19 (fallback: Gutenberg)
→ create project directory structure + write verification/source.json

Usage:
    python engine/fetch_raw.py "<title>" "<author>" [output_base_dir]

Examples:
    python engine/fetch_raw.py "Voodoo Planet" "Andre Norton"
    python engine/fetch_raw.py "Pride and Prejudice" "Jane Austen" ~/projects
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

# optional state integration — silently skipped if pipeline_state not on path
try:
    from pipeline_state import PipelineState
    _HAS_STATE = True
except ImportError:
    _HAS_STATE = False

GUTENDEX_SEARCH = "https://gutendex.com/books/?search={query}"
GUTENDEX_BY_ID  = "https://gutendex.com/books/?ids={id}"
PG19_PREFIXES   = ["test", "validation", "train"]
PG19_URL        = "https://storage.googleapis.com/deepmind-gutenberg/{split}/{id}.txt"
GUTENBERG_URL   = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"


# ── helpers ──────────────────────────────────────────────────────────────────

_USER_AGENT = "Mozilla/5.0 (compatible; MennzLore/1.0; +https://github.com/mgprona/MennzLore)"


def _get(url: str, retries: int = 3, timeout: int = 60) -> bytes:
    # Default Python-urllib UA is frequently rejected (503/403) by gutendex
    # and Gutenberg; send a real UA so requests are accepted.
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def _slug(text: str) -> str:
    """Convert title/author to lowercase-hyphenated slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def make_prefix(title: str, author_last: str) -> str:
    """e.g. 'Voodoo Planet' + 'Norton' → 'voodoo-planet-norton'"""
    return _slug(f"{title}-{author_last}")


# ── search ───────────────────────────────────────────────────────────────────

def search_gutendex(title: str, author: str) -> list[dict]:
    """Return ranked list of candidate books from gutendex."""
    query = urllib.parse.quote(f"{title} {author}")
    data = json.loads(_get(GUTENDEX_SEARCH.format(query=query)))
    results = data.get("results", [])

    title_l  = title.lower()
    author_l = author.lower()

    def score(b):
        t = b.get("title", "").lower()
        a = " ".join(p.get("name", "") for p in b.get("authors", [])).lower()
        return (title_l in t) * 2 + any(w in a for w in author_l.split())

    return sorted(results, key=score, reverse=True)


def _text_plain_url(book: dict) -> str | None:
    """Return best text/plain URL from gutendex formats, preferring utf-8. Never readme."""
    fmts = book.get("formats", {})
    candidates = [
        (k, v) for k, v in fmts.items()
        if k.startswith("text/plain") and not v.endswith("readme.txt")
    ]
    # utf-8 first, then ascii
    for charset in ("utf-8", "us-ascii"):
        for k, v in candidates:
            if charset in k:
                return v
    return candidates[0][1] if candidates else None


def pick_best(candidates: list[dict], title: str, author: str) -> dict:
    """Return highest-scored candidate that has a usable text/plain URL."""
    if not candidates:
        raise LookupError(f"No results for '{title}' by '{author}'")
    title_l  = title.lower()
    author_l = author.lower()

    def score(b):
        t = b.get("title", "").lower()
        a = " ".join(p.get("name", "") for p in b.get("authors", [])).lower()
        return (title_l in t) * 2 + any(w in a for w in author_l.split())

    # candidates with usable text/plain float to top, then by title/author score
    candidates.sort(key=lambda c: (bool(_text_plain_url(c)), score(c)), reverse=True)
    best = candidates[0]
    t = best.get("title", "").lower()
    if title.lower() not in t and t not in title.lower():
        raise LookupError(
            f"Best match '{best['title']}' doesn't look like '{title}'. "
            f"Try a more specific title/author."
        )
    return best


# ── download ─────────────────────────────────────────────────────────────────

def fetch_from_pg19(gutenberg_id: int) -> tuple[bytes, str]:
    """Try PG-19 splits in order. Return (bytes, url) or raise."""
    for split in PG19_PREFIXES:
        url = PG19_URL.format(split=split, id=gutenberg_id)
        try:
            data = _get(url, retries=2, timeout=45)
            return data, url
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
    raise FileNotFoundError(f"ID {gutenberg_id} not found in PG-19 (all splits)")


def fetch_from_gutenberg(book: dict) -> tuple[bytes, str]:
    """Fallback: fetch from Project Gutenberg using URL from gutendex formats."""
    url = _text_plain_url(book)
    if not url:
        raise LookupError(f"No text/plain format available for Gutenberg ID {book['id']}")
    data = _get(url, timeout=60)
    return data, url


# ── project scaffold ─────────────────────────────────────────────────────────

PROJECT_DIRS = ["raw", "clean", "verification", "micro_facts",
                "analysis/sa_raw", "analysis/pass2",
                "entities", "chapters", "output"]

def scaffold_project(base_dir: str, prefix: str) -> str:
    """Create <base_dir>/<prefix>/ with all pipeline subdirs. Return project_dir."""
    project_dir = os.path.join(base_dir, prefix)
    for d in PROJECT_DIRS:
        os.makedirs(os.path.join(project_dir, d), exist_ok=True)
    return project_dir


# ── main ─────────────────────────────────────────────────────────────────────

def _finalize(book_id, book_title, authors, raw_bytes, source, source_url, base_dir) -> dict:
    """Shared tail: scaffold project, write raw + provenance, update pipeline state."""
    author_last = authors[0].split(",")[0].strip() if authors else "unknown"
    prefix = make_prefix(book_title, author_last)
    project_dir = scaffold_project(base_dir, prefix)
    print(f"  Prefix:  {prefix}")
    print(f"  Project: {project_dir}")

    raw_path = os.path.join(project_dir, "raw", f"{prefix}_full.txt")
    with open(raw_path, "wb") as f:
        f.write(raw_bytes)
    print(f"  Raw:     {raw_path}  ({len(raw_bytes):,} bytes)")

    provenance = {
        "prefix":          prefix,
        "gutenberg_id":    book_id,
        "title":           book_title,
        "authors":         authors,
        "source":          source,
        "source_url":      source_url,
        "fetched_at":      datetime.utcnow().isoformat() + "Z",
        "raw_file":        f"raw/{prefix}_full.txt",
        "raw_bytes":       len(raw_bytes),
    }
    prov_path = os.path.join(project_dir, "verification", f"{prefix}_source.json")
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(provenance, f, ensure_ascii=False, indent=2)
    print(f"  Source:  {prov_path}")

    if _HAS_STATE:
        ps = PipelineState(project_dir, prefix)
        ps.init_meta(gutenberg_id=book_id, title=book_title, source=source)
        ps.set_phase("1_acquisition", "COMPLETE",
                     source=source_url, chars=len(raw_bytes))

    print(f"\nPhase 1 complete — project ready at: {project_dir}")
    return provenance


def _download(book: dict) -> tuple[bytes, str, str]:
    """Download raw text for a gutendex book record. Return (bytes, source, url)."""
    try:
        raw_bytes, source_url = fetch_from_pg19(book["id"])
        print(f"  Source:  PG-19  ({source_url})")
        return raw_bytes, "pg19", source_url
    except FileNotFoundError:
        print(f"  PG-19:   not found — fallback to Project Gutenberg")
        raw_bytes, source_url = fetch_from_gutenberg(book)
        print(f"  Source:  Gutenberg  ({source_url})")
        return raw_bytes, "gutenberg", source_url


def lookup_by_id(book_id: int) -> dict:
    """Fetch a single gutendex book record by its Gutenberg ID."""
    data = json.loads(_get(GUTENDEX_BY_ID.format(id=book_id)))
    results = data.get("results", [])
    if not results:
        raise LookupError(f"No Gutenberg book found for ID {book_id}")
    return results[0]


def fetch_raw(title: str, author: str, base_dir: str = ".") -> dict:
    print(f"\nPhase 1 — Fetch Raw")
    print(f"  Searching: '{title}' by '{author}'")

    candidates = search_gutendex(title, author)
    book = pick_best(candidates, title, author)
    authors = [p.get("name", "") for p in book.get("authors", [])]
    print(f"  Found: [{book['id']}] {book['title']}  |  {', '.join(authors)}")

    raw_bytes, source, source_url = _download(book)
    return _finalize(book["id"], book["title"], authors, raw_bytes, source, source_url, base_dir)


def fetch_raw_by_id(book_id: int, base_dir: str = ".") -> dict:
    """Phase 1 by Gutenberg ID — same download + naming path as title/author."""
    print(f"\nPhase 1 — Fetch Raw (by ID)")
    print(f"  Looking up Gutenberg ID: {book_id}")

    book = lookup_by_id(book_id)
    authors = [p.get("name", "") for p in book.get("authors", [])]
    print(f"  Found: [{book['id']}] {book['title']}  |  {', '.join(authors)}")

    raw_bytes, source, source_url = _download(book)
    return _finalize(book["id"], book["title"], authors, raw_bytes, source, source_url, base_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python engine/fetch_raw.py \"<title>\" \"<author>\" [base_dir]")
        print("  python engine/fetch_raw.py --id <gutenberg_id> [base_dir]")
        sys.exit(1)
    if sys.argv[1] == "--id":
        fetch_raw_by_id(
            book_id=int(sys.argv[2]),
            base_dir=sys.argv[3] if len(sys.argv) > 3 else ".",
        )
    else:
        if len(sys.argv) < 3:
            print("Usage: python engine/fetch_raw.py \"<title>\" \"<author>\" [base_dir]")
            sys.exit(1)
        fetch_raw(
            title=sys.argv[1],
            author=sys.argv[2],
            base_dir=sys.argv[3] if len(sys.argv) > 3 else ".",
        )
