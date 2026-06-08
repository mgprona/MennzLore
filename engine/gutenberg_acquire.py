import os
import re
import requests
from typing import List, Dict, Any

def download_gutenberg(book_id: str, dest_path: str, url_override: str = None) -> str:
    """
    Download plain text from Project Gutenberg using the book ID.
    Supports a list of fallback URLs.
    """
    if url_override:
        urls = [url_override]
    else:
        urls = [
            f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt",
            f"https://www.gutenberg.org/files/{book_id}/{book_id}.txt",
            f"https://www.gutenberg.org/ebooks/{book_id}.txt.utf-8",
            f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
        ]

    last_error = None
    for url in urls:
        try:
            print(f"[INFO] Attempting to download Gutenberg ID {book_id} from {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # Handle text encoding
                response.encoding = response.apparent_encoding or "utf-8"
                text = response.text
                if text and len(text) > 1000:
                    # Write raw download to dest_path
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    print(f"[SUCCESS] Downloaded and saved {book_id} to {dest_path}")
                    return text
            print(f"[WARNING] URL failed with status code: {response.status_code}")
        except Exception as e:
            print(f"[WARNING] Error fetching from {url}: {e}")
            last_error = e

    raise RuntimeError(f"Failed to download book ID {book_id} from all sources. Last error: {last_error}")

def clean_gutenberg_text(text: str) -> str:
    """
    Remove Project Gutenberg headers, footers, and boilerplate text.
    """
    # Look for start markers
    start_patterns = [
        r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
        r"\*\*\*START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*",
        r"Content Start"
    ]
    
    # Look for end markers
    end_patterns = [
        r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
        r"\*\*\*END OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*",
        r"End of the Project Gutenberg EBook"
    ]

    start_idx = 0
    for pattern in start_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start_idx = match.end()
            break

    end_idx = len(text)
    for pattern in end_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            end_idx = match.start()
            break

    cleaned = text[start_idx:end_idx].strip()
    return cleaned

def split_by_chapter(text: str, prefix: str, dest_dir: str) -> List[str]:
    """
    Split a cleaned book text by chapter headings and save them as EP001.txt, EP002.txt etc.
    """
    # Regex to find chapter headings (like CHAPTER I, Chapter 1, CHAPTER THE FIRST, PROLOGUE, etc.)
    # and standalone Roman numerals (like I, II, III) on a line by themselves.
    chapter_regex = re.compile(
        r"^\s*(?:"
        r"(?:CHAPTER|Chapter|Book|BOOK|PROLOGUE|Prologue|EPILOGUE|Epilogue|Part|PART)\s+([IVXLCDM\d\-\w\s]+?)"
        r"|"
        r"([IVXLCDM]+)"
        r"|"
        r"_\d+_\."
        r"|"
        r"_\d+\._"
        r")(?:\.|\:|\n|\r|$)", 
        re.MULTILINE
    )

    matches = list(chapter_regex.finditer(text))
    
    os.makedirs(dest_dir, exist_ok=True)
    file_paths = []
    
    if not matches:
        print("[WARNING] No chapter markers found. Saving entire content as EP001.txt")
        ep_path = os.path.join(dest_dir, f"EP001.txt")
        with open(ep_path, "w", encoding="utf-8") as f:
            f.write(text)
        return [ep_path]

    # Process chunks
    chunks = []
    
    # Check if there is introductory text before the first chapter
    intro_text = text[:matches[0].start()].strip()
    if intro_text and len(intro_text) > 100:
        chunks.append(("Intro / Front Matter", intro_text))

    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i+1].start() if i + 1 < len(matches) else len(text)
        title = matches[i].group(0).strip()
        body = text[start:end].strip()
        chunks.append((title, body))

    for idx, (title, body) in enumerate(chunks, 1):
        ep_num = f"{idx:03d}"
        filename = f"EP{ep_num}.txt"
        ep_path = os.path.join(dest_dir, filename)
        
        with open(ep_path, "w", encoding="utf-8") as f:
            # Include chapter heading and title inside file content
            f.write(body)
            
        file_paths.append(ep_path)
        print(f"[INFO] Saved chapter {ep_num} ({title[:30]}...) to {ep_path}")

    return file_paths

def download_and_split(book_id: str, prefix: str, raw_dir: str, url_override: str = None) -> dict:
    """
    Downloads a Project Gutenberg ebook, cleans it, splits it by chapter,
    and returns a summary of the results.
    """
    temp_raw_file = os.path.join(raw_dir, f"raw_{book_id}.txt")
    
    # Download raw text
    raw_text = download_gutenberg(book_id, temp_raw_file, url_override)
    
    # Clean text
    cleaned_text = clean_gutenberg_text(raw_text)
    
    # Split by chapters
    ep_paths = split_by_chapter(cleaned_text, prefix, raw_dir)
    
    # Clean up the large temp file to save space if needed
    if os.path.exists(temp_raw_file):
        os.remove(temp_raw_file)

    return {
        "book_id": book_id,
        "prefix": prefix,
        "raw_dir": raw_dir,
        "chapters_count": len(ep_paths),
        "chapter_files": [os.path.basename(p) for p in ep_paths]
    }
