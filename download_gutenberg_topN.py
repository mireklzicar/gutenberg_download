#!/usr/bin/env python3
"""
Download the **top N** most‑popular Project Gutenberg e‑books in EPUB‑no‑images format, with tidy file‑names and optional metadata sidecars.

Highlights
──────────
* **Prefers** the *…noimages* EPUB when available; falls back to the cleanest alternative.
* Saves each book as a neat, sanitised title – e.g. `Frankenstein.epub` – inside the chosen folder.
* **Optionally** (default ✅) writes a matching JSON file containing the full Gutendex record – `Frankenstein.json` – so you can explore metadata locally.
* Fully resumable: already‑present EPUBs / JSONs are skipped.
* Minimal deps: `requests` + `tqdm`.

Usage
─────
```bash
pip install requests tqdm
python download_gutenberg_topN.py      # downloads 10 books into ./gutenberg_topN/
python download_gutenberg_topN.py 500  # limit to 500
```

You can tweak the constants below or pass a different number on the command line.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
from tqdm import tqdm

# ────────────────────────────────────────────────────────────────────────────────
# Configuration – adjust to taste
# ────────────────────────────────────────────────────────────────────────────────
TOP_N_DEFAULT: int = 10                 # Default book count when none supplied on CLI
OUTPUT_DIR: Path = Path("samples")  # Destination folder
MAX_RETRIES: int = 3                       # Network retries per file
CHUNK_SIZE: int = 64 * 1024                # Bytes per streamed read
SAVE_JSON: bool = True                     # Also save metadata as .json next to the EPUB

API_ROOT: str = "https://gutendex.com/books"  # Gutendex base URL

# Create the output directory if it doesn’t exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ────────────────────────────────────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────────────────────────────────────

def slugify(title: str, max_len: int = 120) -> str:
    """Return a filesystem‑friendly slug based on *title*."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
    return slug[:max_len] or "untitled"


def fetch_top_books(n: int) -> List[dict]:
    """Return *n* book‑records ordered by popularity (download_count ↓)."""
    books: List[dict] = []
    url: Optional[str] = f"{API_ROOT}?sort=popular"

    with tqdm(total=n, unit="book", desc="Fetching metadata", leave=False) as bar:
        while url and len(books) < n:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            payload: Dict = resp.json()
            page = payload["results"]
            books.extend(page)
            bar.update(len(page))
            url = payload["next"]

    return books[:n]


def pick_best_epub(formats: Dict[str, str]) -> Optional[str]:
    """Return the best EPUB URL following the preference: noimages → plain → images."""
    candidates = [url for mime, url in formats.items() if mime.startswith("application/epub")]
    if not candidates:
        return None

    def score(u: str) -> int:
        if ".noimages" in u:
            return 0
        if ".images" in u:
            return 2
        return 1  # plain EPUB (usually .epub3 or .epub)

    candidates.sort(key=score)
    return candidates[0]


def download_stream(url: str, dest: Path) -> bool:
    """Stream *url* to *dest* with retries.  Returns True on success."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0))
                with open(dest, "wb") as fh, tqdm(
                    total=total,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=dest.name,
                    leave=False,
                ) as bar:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            fh.write(chunk)
                            bar.update(len(chunk))
            return True
        except Exception as exc:
            tqdm.write(f"⚠️  Attempt {attempt}/{MAX_RETRIES} failed for {url}: {exc}")
            time.sleep(2)
    return False


# ────────────────────────────────────────────────────────────────────────────────
# Main routine
# ────────────────────────────────────────────────────────────────────────────────

def main() -> None:
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else TOP_N_DEFAULT

    books = fetch_top_books(top_n)

    for idx, book in enumerate(books, 1):
        epub_url = pick_best_epub(book["formats"])
        if not epub_url:
            tqdm.write(f"⏭️  Skipping ID {book['id']} – no EPUB available")
            continue

        slug = slugify(book["title"])
        dest_epub = OUTPUT_DIR / f"{slug}.epub"

        # Ensure we don’t clobber an existing different book with the same title
        if dest_epub.exists():
            # If the file already belongs to this ID, we’re good – otherwise add ID suffix
            if dest_epub.stat().st_size > 0:
                tqdm.write(f"✔️  [{idx}/{top_n}] Already downloaded: {dest_epub.name}")
                continue
            dest_epub = OUTPUT_DIR / f"{slug}_{book['id']}.epub"

        tqdm.write(f"⬇️  [{idx}/{top_n}] {book['title']} → {dest_epub.name}")
        success = download_stream(epub_url, dest_epub)
        if not success:
            tqdm.write("❌  Giving up after retries – moving on…")
            continue

        # Save JSON sidecar if requested
        if SAVE_JSON:
            dest_json = dest_epub.with_suffix(".json")
            if not dest_json.exists():
                with open(dest_json, "w", encoding="utf-8") as jf:
                    json.dump(book, jf, ensure_ascii=False, indent=2)

    print("✅ All done!  Happy reading.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted by user – exiting…")
