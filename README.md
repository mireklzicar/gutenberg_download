# Gutenberg Download

A Python script to download Project Gutenberg e-books in EPUB format with clean filenames and optional metadata.

- Download the **top N** most‑popular Project Gutenberg e‑books in EPUB format
- Support for multiple sorting options: popularity, title, author, ID, or random selection
- Clean, filesystem-friendly filenames and optional metadata JSON files
- Fully resumable downloads with progress tracking

### Simple Example

```bash
python gutenberg_download.py 3 -o top3_gutenberg_books
```

This creates:
```
top3_gutenberg_books/
├── Frankenstein_Or_The_Modern_Prometheus.epub
├── Frankenstein_Or_The_Modern_Prometheus.json
├── Moby_Dick_Or_The_Whale.epub
├── Moby_Dick_Or_The_Whale.json
├── The_History_of_the_Peloponnesian_War.epub
└── The_History_of_the_Peloponnesian_War.json
```

## Features

- **Smart Format Selection**: Prefers the *noimages* EPUB when available; falls back to plain EPUB, then images EPUB if necessary
- **Clean Filenames**: Saves each book with a neat, sanitized title (e.g., `Frankenstein_Or_The_Modern_Prometheus.epub`) inside your chosen folder
- **Metadata Access**: Optionally writes a matching JSON file containing the full Gutendex record (e.g., `Frankenstein_Or_The_Modern_Prometheus.json`)
- **Fully Resumable**: Already‑present EPUBs and JSONs are skipped automatically
- **Progress Tracking**: Shows download progress with percentage updates and file sizes
- **Flexible Sorting**: Sort books by popularity, ID (ascending/descending), title, author, or random selection
- **Intelligent Selection**: For title/author sorting, fetches a larger pool (3x requested) for better variety
- **Random Sampling**: For random selection, builds a pool of up to 1000 books for true randomization
- **Minimal Dependencies**: Only requires `requests`


```bash
usage: gutenberg_download.py [-h] [-o OUTPUT_DIR] [--save-json | --no-json] [--retries RETRIES] [--chunk-size CHUNK_SIZE] [--sort {popular,ascending,descending,title,author,random}] [count]

Download top N most popular Project Gutenberg e-books in EPUB format.

positional arguments:
  count                 Number of books to download (default: 10)

options:
  -h, --help            show this help message and exit
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output directory for downloaded books (default: output)
  --save-json           Save book metadata as JSON alongside EPUB files (default: True)
  --no-json             Don't save book metadata as JSON (default: True)
  --retries RETRIES     Maximum number of download retries per file (default: 3)
  --chunk-size CHUNK_SIZE
                        Chunk size in bytes for streaming downloads (default: 65536)
  --sort {popular,ascending,descending,title,author,random}
                        Sort books by: popular (download count), ascending (ID), descending (ID), title, author, or random (default: popular)
```

## Requirements

- Python 3.6+
- `requests` library

Install the dependency:
```bash
pip install requests
```

## Usage

### Basic Usage

```bash
# Download top 10 books (default) to ./output/ directory
python gutenberg_download.py

# Download top 100 books
python gutenberg_download.py 100
```

### Advanced Options

```bash
# Show help and all available options
python gutenberg_download.py --help

# Download top 50 books to a custom directory
python gutenberg_download.py 50 --output-dir my_books

# Download without saving JSON metadata
python gutenberg_download.py --no-json

# Increase download retries for unreliable connections
python gutenberg_download.py --retries 5

# Adjust chunk size for streaming (in bytes)
python gutenberg_download.py --chunk-size 131072

# Sort books by title (client-side sorting)
python gutenberg_download.py --sort title

# Sort books by author (client-side sorting)
python gutenberg_download.py --sort author

# Sort books by Project Gutenberg ID (ascending)
python gutenberg_download.py --sort ascending

# Sort books by Project Gutenberg ID (descending)
python gutenberg_download.py --sort descending

# Download random books
python gutenberg_download.py --sort random

# Download 20 books sorted by title without JSON metadata
python gutenberg_download.py 20 --sort title --no-json

# Download 5 random books with increased retries and custom chunk size
python gutenberg_download.py 5 --sort random --retries 5 --chunk-size 131072
```

## Sorting Options

The script supports several sorting methods:

- **`popular`** (default): Downloads books sorted by popularity (download count) from Gutendx API
- **`ascending`**: Downloads books sorted by Project Gutenberg ID in ascending order
- **`descending`**: Downloads books sorted by Project Gutenberg ID in descending order
- **`title`**: Fetches a larger pool of popular books and sorts them alphabetically by title (client-side)
- **`author`**: Fetches a larger pool of popular books and sorts them by author name (client-side)
- **`random`**: Builds a pool of up to 1000 popular books and randomly selects the requested number

**Note**: Title and author sorting fetch 3x the requested number of books to provide better variety, while random selection builds a larger pool for true randomization.

## About

This script uses [Gutendex](https://gutendx.com/), a JSON web API for Project Gutenberg e-book metadata. It downloads books based on your specified sorting criteria.

## License

MIT