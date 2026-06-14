#!/usr/bin/env python3
"""
Phase 1b: EPUB Acquisition (Engine)
===================================
Read a local .epub file, extract chapter text, and scaffold the project
directory exactly like Phase 1 + Phase 2 would for Gutenberg text.

Usage:
    python engine/fetch_epub.py <epub_path> [author_last] [base_dir]
    python engine/fetch_epub.py "book.epub" escottinman .
"""
import os
import re
import sys
import json
import html as _html
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from pathlib import Path
import urllib.parse


XHTML_NS = "http://www.w3.org/1999/xhtml"
CHAPTER_PATTERNS = [
    re.compile(r"^CHAPTER\s+([IVXLCDM\d]+)", re.IGNORECASE),
    re.compile(r"^Chapter\s+(\d+)", re.IGNORECASE),
    re.compile(r"^CH\.\s*([IVXLCDM\d]+)", re.IGNORECASE),
]


def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s[:60]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_html(body_elem: ET.Element) -> str:
    lines = []
    for elem in body_elem.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "p":
            txt = "".join(elem.itertext()).strip()
            if txt:
                lines.append(_html.unescape(txt))
        elif tag in ("h2", "h3", "h4"):
            txt = "".join(elem.itertext()).strip()
            if txt:
                lines.append("")
                lines.append(_html.unescape(txt))
                lines.append("")
    return "\n".join(lines)


def _find_author_title(opf_path: str, z: zipfile.ZipFile) -> tuple[str, str]:
    try:
        text = z.read(opf_path).decode("utf-8", errors="replace")
        root = ET.fromstring(text)
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        title = root.findtext(".//dc:title", namespaces=ns) or ""
        creator = root.findtext(".//dc:creator", namespaces=ns) or ""
        return title.strip(), creator.strip()
    except Exception:
        return "", ""


def _find_spine_order(opf_path: str, z: zipfile.ZipFile) -> list[str]:
    """Parse the OPF file and return the list of hrefs in spine order."""
    try:
        text = z.read(opf_path).decode("utf-8", errors="replace")
        root = ET.fromstring(text)
        
        ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
        
        # Get manifest items: id -> href
        manifest_items = {}
        manifest_elem = root.find(".//opf:manifest", namespaces=ns) or root.find(".//manifest")
        if manifest_elem is not None:
            for item in list(manifest_elem):
                iid = item.get("id")
                href = item.get("href")
                if iid and href:
                    manifest_items[iid] = href
        
        # Get spine itemrefs
        spine_hrefs = []
        spine_elem = root.find(".//opf:spine", namespaces=ns) or root.find(".//spine")
        if spine_elem is not None:
            for itemref in list(spine_elem):
                idref = itemref.get("idref")
                if idref in manifest_items:
                    href = manifest_items[idref]
                    opf_dir = os.path.dirname(opf_path)
                    if opf_dir:
                        resolved_href = opf_dir + "/" + href
                    else:
                        resolved_href = href
                    resolved_href = urllib.parse.unquote(resolved_href)
                    parts = []
                    for part in resolved_href.split('/'):
                        if part == '..':
                            if parts:
                                parts.pop()
                        elif part != '.' and part != '':
                            parts.append(part)
                    normalized_href = "/".join(parts)
                    spine_hrefs.append(normalized_href)
        return spine_hrefs
    except Exception as e:
        print(f"[WARNING] Failed to parse OPF spine: {e}")
        return []


def epub_to_project(epub_path: str, base_dir: str = ".", prefix: str = "",
                    title: str = "", author: str = "") -> str:
    """Extract an EPUB into a MennzLore project directory.

    Returns the project directory path.
    """
    epub_path = os.path.abspath(epub_path)
    if not os.path.exists(epub_path):
        raise FileNotFoundError(f"EPUB not found: {epub_path}")

    with zipfile.ZipFile(epub_path, "r") as z:
        all_files = z.namelist()

        # --- 1. Find OPF for metadata ---
        opf_files = [f for f in all_files if f.endswith(".opf")]
        book_title, book_author = "", ""
        for opf in opf_files:
            t, a = _find_author_title(opf, z)
            if t:
                book_title = t
            if a:
                book_author = a
            if book_title and book_author:
                break

        if not book_title:
            book_title = os.path.splitext(os.path.basename(epub_path))[0]
            book_title = re.sub(r",\s*by\s+.*$", "", book_title).strip()

        # --- 2. Determine prefix and project dir ---
        if not prefix:
            author_slug = _slugify(author or book_author or "unknown")
            title_slug = _slugify(title or book_title)
            prefix = f"{title_slug}-{author_slug}" if author_slug != "unknown" else title_slug

        project_dir = os.path.abspath(os.path.join(base_dir, prefix))
        for d in ("raw", "clean", "verification", "micro_facts", "output"):
            os.makedirs(os.path.join(project_dir, d), exist_ok=True)

        # --- 3. Find chapter content files ---
        # Strategy A: filenames with body-dN.html pattern (TEI/NZETC) —
        # already split into individual chapters, do NOT re-split
        body_pattern = re.compile(r"body-d(\d+)\.html")
        chapter_candidates = []
        is_pre_split = False  # True if files are already 1-chapter-per-file
        for f in all_files:
            m = body_pattern.search(f)
            if m:
                chapter_candidates.append((int(m.group(1)), f))
                is_pre_split = True

        # Strategy B: check for heading-based chapters inside HTML, using OPF spine order if available
        spine_files = []
        for opf in opf_files:
            spine_files = _find_spine_order(opf, z)
            if spine_files:
                break
        
        if not chapter_candidates:
            if spine_files:
                html_spine = [f for f in spine_files if f.endswith((".xhtml", ".html", ".htm"))
                               and "nav" not in f.lower() and "toc" not in f.lower()
                               and "copyright" not in f.lower() and "metadata" not in f.lower()
                               and "front" not in f.lower() and "back" not in f.lower()]
                for f in html_spine:
                    exact_file = next((zf for zf in all_files if zf.lower() == f.lower()), None)
                    if exact_file:
                        try:
                            size = z.getinfo(exact_file).file_size
                            if size > 5000:
                                chapter_candidates.append((len(chapter_candidates) + 1, exact_file))
                        except Exception:
                            pass
            
            if not chapter_candidates:
                html_files = [f for f in all_files if f.endswith((".xhtml", ".html", ".htm"))
                              and "nav" not in f.lower() and "toc" not in f.lower()
                              and "copyright" not in f.lower() and "metadata" not in f.lower()
                              and "front" not in f.lower() and "back" not in f.lower()]
                for f in html_files:
                    size = z.getinfo(f).file_size
                    if size > 5000:
                        chapter_candidates.append((len(chapter_candidates) + 1, f))

        # Strategy C: one big file, split by chapter headings
        if not chapter_candidates:
            if spine_files:
                html_spine = [f for f in spine_files if f.endswith((".xhtml", ".html", ".htm"))
                              and "nav" not in f.lower() and "toc" not in f.lower()]
                for f in html_spine:
                    exact_file = next((zf for zf in all_files if zf.lower() == f.lower()), None)
                    if exact_file:
                        chapter_candidates.append((1, exact_file))
                        break
            
            if not chapter_candidates:
                html_files = sorted([f for f in all_files if f.endswith((".xhtml", ".html", ".htm"))
                                     and "nav" not in f.lower() and "toc" not in f.lower()])
                if html_files:
                    chapter_candidates.append((1, html_files[0]))

        if not chapter_candidates:
            raise ValueError("No chapter content found in EPUB. "
                             "The EPUB may be images-only or DRM-protected.")

        chapter_candidates.sort()

        # --- 4. Extract text from each chapter ---
        full_text_parts = []
        chapter_manifest = []

        ep_index = 1
        for ch_num, ch_file in chapter_candidates:
            html_bytes = z.read(ch_file)
            raw_html = html_bytes.decode("utf-8", errors="replace")

            try:
                root = ET.fromstring(raw_html)
                body = root.find(f".//{{{XHTML_NS}}}body") or root.find(".//body")
                text = _parse_html(body) if body is not None else ""
            except ET.ParseError:
                text = re.sub(r"<[^>]+>", " ", _html.unescape(raw_html))
                text = re.sub(r"\s+", " ", text)

            if not text.strip():
                # Skip tiny / empty files (front matter, empty divs)
                continue

            ep_id = f"EP{ep_index:03d}"

            # --- 5. Strategy B/C: split by chapter headings (only for non-pre-split) ---
            if not is_pre_split:
                chapter_splits = []
                lines = text.split("\n")
                current_chapter = []
                for line in lines:
                    is_heading = any(p.match(line.strip()) for p in CHAPTER_PATTERNS)
                    if is_heading and current_chapter:
                        chapter_splits.append("\n".join(current_chapter))
                        current_chapter = [line]
                    else:
                        current_chapter.append(line)
                if current_chapter:
                    chapter_splits.append("\n".join(current_chapter))

                if len(chapter_splits) > 1:
                    for split_text in chapter_splits:
                        if not split_text.strip():
                            continue
                        clean_path = os.path.join(project_dir, "clean", f"{prefix}_{ep_id}.txt")
                        with open(clean_path, "w", encoding="utf-8") as f:
                            f.write(split_text.strip())
                        full_text_parts.append(f"## Chapter {ep_index}\n\n{split_text.strip()}")
                        chapter_manifest.append({"file": f"clean/{prefix}_{ep_id}.txt", "chars": len(split_text)})
                        ep_index += 1
                    continue  # already wrote splits, skip single-file write below

            # Single chapter per file (or pre-split)
            clean_path = os.path.join(project_dir, "clean", f"{prefix}_{ep_id}.txt")
            with open(clean_path, "w", encoding="utf-8") as f:
                f.write(text.strip())
            full_text_parts.append(f"## Chapter {ep_index}\n\n{text.strip()}")
            chapter_manifest.append({"file": f"clean/{prefix}_{ep_id}.txt", "chars": len(text)})
            ep_index += 1

        # --- 6. Write raw full text ---
        full_text = "\n\n".join(full_text_parts)
        raw_path = os.path.join(project_dir, "raw", f"{prefix}_full.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        # --- 7. Write provenance ---
        source_info = {
            "source": "epub",
            "epub_path": epub_path,
            "title": title or book_title,
            "author": author or book_author,
            "fetched_at": _now(),
            "total_chars": len(full_text),
            "chapters": len(chapter_manifest),
        }
        src_path = os.path.join(project_dir, "verification", f"{prefix}_source.json")
        with open(src_path, "w", encoding="utf-8") as f:
            json.dump(source_info, f, ensure_ascii=False, indent=2)

        # --- 8. Write chapter manifest ---
        cm_path = os.path.join(project_dir, "verification", f"{prefix}_chapters.json")
        with open(cm_path, "w", encoding="utf-8") as f:
            json.dump(chapter_manifest, f, ensure_ascii=False, indent=2)

        print(f"[EPUB] Extracted: {source_info['title']}")
        print(f"       Author:   {source_info['author']}")
        print(f"       Chapters: {len(chapter_manifest)}  |  Total: {len(full_text):,} chars")
        print(f"       Project:  {project_dir}")
        return project_dir


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python engine/fetch_epub.py <epub_path> [base_dir]")
        sys.exit(1)
    epub_to_project(sys.argv[1], base_dir=sys.argv[2] if len(sys.argv) > 2 else ".")
