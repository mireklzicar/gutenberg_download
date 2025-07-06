#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sys
import time
import argparse
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

# ────────────────────────────────────────────────────────────────────────────────
# Default configuration
# ────────────────────────────────────────────────────────────────────────────────
TOP_N_DEFAULT: int = 10                    # Default book count when none supplied on CLI
OUTPUT_DIR_DEFAULT: Path = Path("output")  # Default destination folder
MAX_RETRIES_DEFAULT: int = 3               # Default network retries per file
CHUNK_SIZE_DEFAULT: int = 64 * 1024        # Default bytes per streamed read
SAVE_JSON_DEFAULT: bool = True             # Default for saving metadata as .json

API_ROOT: str = "https://gutendex.com/books"  # Gutendex base URL

# ────────────────────────────────────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────────────────────────────────────

def slugify(title: str, max_len: int = 120) -> str:
    """Return a filesystem‑friendly slug based on *title*."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
    return slug[:max_len] or "untitled"


def fetch_books(n: int, sort_by: str, client_sort: str = None) -> List[dict]:
    """Return *n* book‑records ordered by the specified criteria."""
    books: List[dict] = []
    
    if sort_by == "random":
        # For random selection, we need to fetch more books and then randomly select
        print(f"Fetching random {n} books...")
        # Fetch a larger pool to select from (at least 10x the requested amount or 1000, whichever is smaller)
        pool_size = min(max(n * 10, 100), 1000)
        url: Optional[str] = f"{API_ROOT}?sort=popular"  # Use popular as base for random selection
        
        while url and len(books) < pool_size:
            print(f"  Fetching page... ({len(books)}/{pool_size} books so far)")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            payload: Dict = resp.json()
            page = payload["results"]
            books.extend(page)
            url = payload["next"]
        
        # Randomly select n books from the pool
        if len(books) >= n:
            books = random.sample(books, n)
        else:
            random.shuffle(books)
        
        print(f"Randomly selected {len(books)} books from pool of {min(len(books), pool_size)}.")
        return books[:n]
    
    elif client_sort in ["title", "author"]:
        # For title/author sorting, we need to fetch more books to have a good selection
        # then sort them client-side
        fetch_size = max(n * 3, 100)  # Fetch 3x more books to sort from
        print(f"Fetching {fetch_size} books for client-side sorting by {client_sort}...")
        
        url: Optional[str] = f"{API_ROOT}?sort=popular"  # Use popular as base
        
        while url and len(books) < fetch_size:
            print(f"  Fetching page... ({len(books)}/{fetch_size} books so far)")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            payload: Dict = resp.json()
            page = payload["results"]
            books.extend(page)
            url = payload["next"]
        
        # Sort the books client-side
        if client_sort == "title":
            books.sort(key=lambda book: book["title"].lower())
            print(f"Sorted {len(books)} books by title.")
        elif client_sort == "author":
            def get_author_name(book):
                if book["authors"]:
                    return book["authors"][0]["name"].lower()
                return "zzz_unknown"  # Put books without authors at the end
            books.sort(key=get_author_name)
            print(f"Sorted {len(books)} books by author.")
        
        return books[:n]
    
    else:
        # Use API sorting for supported options: popular, ascending, descending
        url: Optional[str] = f"{API_ROOT}?{sort_by}" if sort_by else API_ROOT
        print(f"Fetching metadata for {n} books...")
        
        while url and len(books) < n:
            print(f"  Fetching page... ({len(books)}/{n} books so far)")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            payload: Dict = resp.json()
            page = payload["results"]
            books.extend(page)
            url = payload["next"]

        print(f"Metadata fetched for {min(len(books), n)} books.")
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
                total_mb = total / (1024 * 1024) if total > 0 else "unknown"
                
                print(f"  Downloading {dest.name} ({total_mb:.1f} MB)" if isinstance(total_mb, float) else f"  Downloading {dest.name} (size: {total_mb})")
                
                with open(dest, "wb") as fh:
                    downloaded = 0
                    last_percent = -1
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            fh.write(chunk)
                            downloaded += len(chunk)
                            
                            # Show progress every 10%
                            if total > 0:
                                percent = int((downloaded / total) * 100)
                                if percent // 10 > last_percent // 10:
                                    print(f"    {percent}% complete ({downloaded/(1024*1024):.1f}/{total_mb:.1f} MB)")
                                    last_percent = percent
                
                print(f"  Download complete: {dest.name}")
            return True
        except Exception as exc:
            print(f"⚠️  Attempt {attempt}/{MAX_RETRIES} failed for {url}: {exc}")

            time.sleep(2)
    return False


# ────────────────────────────────────────────────────────────────────────────────
# Main routine
# ────────────────────────────────────────────────────────────────────────────────

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Download top N most popular Project Gutenberg e-books in EPUB format.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "count",
        nargs="?",
        type=int,
        default=TOP_N_DEFAULT,
        help="Number of books to download (default: %(default)s)"
    )
    
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=OUTPUT_DIR_DEFAULT,
        help="Output directory for downloaded books"
    )
    
    json_group = parser.add_mutually_exclusive_group()
    json_group.add_argument(
        "--save-json",
        action="store_true",
        dest="save_json",
        default=SAVE_JSON_DEFAULT,
        help="Save book metadata as JSON alongside EPUB files"
    )
    
    json_group.add_argument(
        "--no-json",
        action="store_false",
        dest="save_json",
        help="Don't save book metadata as JSON"
    )
    
    parser.add_argument(
        "--retries",
        type=int,
        default=MAX_RETRIES_DEFAULT,
        help="Maximum number of download retries per file"
    )
    
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE_DEFAULT,
        help="Chunk size in bytes for streaming downloads"
    )
    
    parser.add_argument(
        "--sort",
        choices=["popular", "ascending", "descending", "title", "author", "random"],
        default="popular",
        help="Sort books by: popular (download count), ascending (ID), descending (ID), title, author, or random"
    )
    
    return parser.parse_args()


def main() -> None:
    """Main program execution."""
    args = parse_args()
    
    # Create the output directory if it doesn't exist
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set global variables based on arguments
    global MAX_RETRIES, CHUNK_SIZE
    MAX_RETRIES = args.retries
    CHUNK_SIZE = args.chunk_size
    
    # Determine sort parameter for API and client-side sorting
    sort_param = ""
    client_sort = None
    
    if args.sort == "popular":
        sort_param = "sort=popular"
    elif args.sort == "ascending":
        sort_param = "sort=ascending"
    elif args.sort == "descending":
        sort_param = "sort=descending"
    elif args.sort in ["title", "author"]:
        # These require client-side sorting
        client_sort = args.sort
        sort_param = "popular"  # Will be handled in fetch_books
    elif args.sort == "random":
        sort_param = "random"  # Special case handled in fetch_books
    
    books = fetch_books(args.count, sort_param, client_sort)

    print(f"\nDownloading {len(books)} books to {args.output_dir}/")
    for idx, book in enumerate(books, 1):
        epub_url = pick_best_epub(book["formats"])
        if not epub_url:
            print(f"⏭️  [{idx}/{args.count}] Skipping ID {book['id']} – no EPUB available")

            continue

        slug = slugify(book["title"])
        dest_epub = args.output_dir / f"{slug}.epub"

        # Ensure we don't clobber an existing different book with the same title
        if dest_epub.exists():
            # If the file already belongs to this ID, we're good – otherwise add ID suffix
            if dest_epub.stat().st_size > 0:
                print(f"✔️  [{idx}/{args.count}] Already downloaded: {dest_epub.name}")
                continue
            dest_epub = args.output_dir / f"{slug}_{book['id']}.epub"

        print(f"⬇️  [{idx}/{args.count}] {book['title']} → {dest_epub.name}")
        success = download_stream(epub_url, dest_epub)
        if not success:
            print("❌  Giving up after retries – moving on…")
            continue

        # Save JSON sidecar if requested
        if args.save_json:
            dest_json = dest_epub.with_suffix(".json")
            if not dest_json.exists():
                with open(dest_json, "w", encoding="utf-8") as jf:
                    json.dump(book, jf, ensure_ascii=False, indent=2)

    print("\n✅ All done!  Happy reading.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted by user – exiting…")
