"""
scrape.py — Main scraper for srivalmikiramayana.com

Usage:
  python scrape.py                     # scrape all available kandas
  python scrape.py --kanda 1           # scrape only Bala-kanda
  python scrape.py --kanda 1 --chapter 1   # scrape only chapter 1 of Bala-kanda
  python scrape.py --kanda 1 --chapter 1 --verse 1   # scrape single verse
  python scrape.py --force             # re-scrape even if already in DB

Rate: 3–5 second random delay per request (polite crawling).
Resume: skips verses already stored with non-empty translation.
"""

import os
import sys
import time
import random
import argparse
import json
import logging
from pathlib import Path

import requests
from tqdm import tqdm

# Add parent dir to path so we can import from scraper/ regardless of cwd
sys.path.insert(0, str(Path(__file__).parent))

from db import (
    init_db, insert_verse, insert_chapter,
    is_verse_scraped, is_chapter_scraped,
    KANDA_NAMES, KANDA_SLUGS,
)
from parser import (
    parse_kanda_page, parse_chapter_page, parse_verse_page,
)

# ── Config ──────────────────────────────────────────────────────────────────
BASE_URL   = "https://srivalmikiramayana.com"
DB_PATH    = str(Path(__file__).parent.parent / "data" / "ramayana.db")
JSON_DIR   = Path(__file__).parent.parent / "data" / "json"
LOG_FILE   = str(Path(__file__).parent.parent / "data" / "scrape.log")

RATE_MIN   = 0.6   # seconds
RATE_MAX   = 1.2   # seconds
MAX_RETRIES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Kandas 1–3 are currently published; 4–7 will 404 gracefully
ALL_KANDAS = [1, 2, 3, 4, 5, 6, 7]

# ── Logging ─────────────────────────────────────────────────────────────────
# Force UTF-8 on Windows console to handle non-ASCII log messages
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_file_handler   = logging.FileHandler(LOG_FILE, encoding="utf-8")
_stream_handler = logging.StreamHandler(sys.stdout)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_file_handler.setFormatter(_fmt)
_stream_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _stream_handler])
log = logging.getLogger(__name__)


# ── HTTP helpers ─────────────────────────────────────────────────────────────
session = requests.Session()
session.headers.update(HEADERS)


def fetch(url: str, retries: int = MAX_RETRIES) -> str | None:
    """Fetch a URL with retry + exponential backoff. Returns HTML or None."""
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 404:
                log.debug(f"  -> 404 for {url}")
                return None
            elif resp.status_code in (301, 302):
                # Follow redirect manually if needed
                log.debug(f"  -> {resp.status_code} for {url}")
                return None
            else:
                log.warning(f"  -> HTTP {resp.status_code} for {url} (attempt {attempt})")
        except requests.exceptions.ConnectionError as e:
            log.warning(f"  -> Connection error for {url}: {type(e).__name__} (attempt {attempt})")
        except requests.exceptions.Timeout:
            log.warning(f"  -> Timeout for {url} (attempt {attempt})")
        except requests.RequestException as e:
            log.warning(f"  -> Request error for {url}: {e} (attempt {attempt})")

        # Exponential backoff before retry
        wait = 2 ** attempt + random.uniform(1, 3)
        log.debug(f"  -> Waiting {wait:.1f}s before retry...")
        time.sleep(wait)

    log.error(f"  -> Failed after {retries} attempts: {url}")
    return None


def polite_sleep():
    """Wait 3-5 seconds between requests (polite crawling)."""
    delay = random.uniform(RATE_MIN, RATE_MAX)
    time.sleep(delay)


# ── JSON backup ──────────────────────────────────────────────────────────────
def save_json(verse: dict) -> None:
    """Save verse as JSON file backup."""
    k, c = verse["kanda_num"], verse["chapter_num"]
    ref = verse["verse_ref"].split(".")[-1]  # e.g. "1" or "19-20"
    out_dir = JSON_DIR / str(k) / str(c)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{ref}.json", "w", encoding="utf-8") as f:
        json.dump(verse, f, ensure_ascii=False, indent=2)


# ── Core crawlers ────────────────────────────────────────────────────────────
def scrape_verse(conn, kanda_num: int, chapter_num: int, verse_info: dict,
                 chapter_title: str, force: bool = False) -> bool:
    """Fetch and store a single verse. Returns True if stored."""
    verse_ref = verse_info["verse_ref"]
    url       = verse_info["url"]

    if not force and is_verse_scraped(conn, kanda_num, chapter_num, verse_ref):
        log.debug(f"  [ok] Already scraped: {verse_ref}")
        return False

    html = fetch(url)
    polite_sleep()

    if html is None:
        log.warning(f"  [skip] Could not fetch verse {verse_ref}: {url}")
        return False

    verse = parse_verse_page(html, url, kanda_num, chapter_num, verse_ref, chapter_title)
    if not verse:
        log.warning(f"  [skip] Could not parse verse {verse_ref}: {url}")
        return False

    insert_verse(conn, verse)
    save_json(verse)
    log.info(f"  [saved] {verse_ref}")
    return True


def scrape_chapter(conn, kanda_num: int, chapter_info: dict, force: bool = False) -> int:
    """Fetch all verses in a chapter. Returns count of newly scraped verses."""
    chapter_num   = chapter_info["num"]
    chapter_url   = chapter_info["url"]
    chapter_title = chapter_info.get("title", "")

    log.info(f"  Chapter {chapter_num}: {chapter_title}")

    html = fetch(chapter_url)
    polite_sleep()

    if html is None:
        log.warning(f"  [skip] Could not fetch chapter {kanda_num}.{chapter_num}: {chapter_url}")
        return 0

    chapter_data = parse_chapter_page(html, kanda_num, chapter_num, chapter_url)
    if not chapter_data["verse_links"]:
        log.warning(f"  [skip] No verse links found in chapter {kanda_num}.{chapter_num}")
        return 0

    # Store chapter metadata
    insert_chapter(conn, {
        "kanda_num":     kanda_num,
        "kanda_name":    KANDA_NAMES.get(kanda_num, ""),
        "chapter_num":   chapter_num,
        "chapter_title": chapter_data["chapter_title"] or chapter_title,
        "chapter_intro": chapter_data["chapter_intro"],
        "url":           chapter_url,
        "scraped_at":    __import__("datetime").datetime.utcnow().isoformat(),
    })

    verse_links = chapter_data["verse_links"]
    resolved_title = chapter_data["chapter_title"] or chapter_title
    count = 0

    for vinfo in tqdm(verse_links, desc=f"    K{kanda_num}.C{chapter_num}", unit="verse", leave=False):
        ok = scrape_verse(conn, kanda_num, chapter_num, vinfo, resolved_title, force)
        if ok:
            count += 1

    return count


def scrape_kanda(conn, kanda_num: int, target_chapter: int | None = None,
                 target_verse: int | None = None, force: bool = False) -> int:
    """Fetch all chapters in a kanda. Returns total verse count."""
    kanda_url = f"{BASE_URL}/en/{kanda_num}/"
    log.info(f"{'='*60}")
    log.info(f"Kanda {kanda_num}: {KANDA_NAMES.get(kanda_num, '')} - {kanda_url}")

    html = fetch(kanda_url)
    polite_sleep()

    if html is None:
        log.info(f"  Kanda {kanda_num} not available yet - skipping")
        return 0

    kanda_data = parse_kanda_page(html, kanda_num)
    chapters   = kanda_data["chapters"]

    if not chapters:
        log.warning(f"  [skip] No chapters found for kanda {kanda_num}")
        return 0

    log.info(f"  Found {len(chapters)} chapters")

    # Filter to specific chapter if requested
    if target_chapter is not None:
        chapters = [c for c in chapters if c["num"] == target_chapter]
        if not chapters:
            log.error(f"  ✗ Chapter {target_chapter} not found in kanda {kanda_num}")
            return 0

    total = 0
    for chapter_info in tqdm(chapters, desc=f"  Kanda {kanda_num}", unit="chapter"):
        if target_verse is not None and target_chapter is not None:
            # Scrape a single verse only
            chapter_url  = chapter_info["url"]
            chapter_html = fetch(chapter_url)
            polite_sleep()
            if chapter_html is None:
                continue
            ch_data = parse_chapter_page(chapter_html, kanda_num, chapter_info["num"], chapter_url)
            # Find the verse link that covers target_verse (handles ranges)
            for vinfo in ch_data["verse_links"]:
                verse_ref = vinfo["verse_ref"]
                parts = verse_ref.split(".")
                v_part = parts[-1]
                if "-" in v_part:
                    vs, ve = map(int, v_part.split("-"))
                else:
                    vs = ve = int(v_part)
                if vs <= target_verse <= ve:
                    ok = scrape_verse(conn, kanda_num, chapter_info["num"], vinfo,
                                      ch_data["chapter_title"], force)
                    if ok:
                        total += 1
                    break
        else:
            count = scrape_chapter(conn, kanda_num, chapter_info, force)
            total += count

    return total


# ── Entry point ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Scrape Sri Valmiki Ramayana into SQLite database"
    )
    parser.add_argument("--kanda",   type=int, help="Scrape a specific kanda (1–7)")
    parser.add_argument("--chapter", type=int, help="Scrape a specific chapter")
    parser.add_argument("--verse",   type=int, help="Scrape a specific verse number")
    parser.add_argument("--force",   action="store_true", help="Re-scrape already stored verses")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = init_db(DB_PATH)
    log.info(f"Database: {DB_PATH}")

    kandas = [args.kanda] if args.kanda else ALL_KANDAS
    grand_total = 0

    for k in kandas:
        count = scrape_kanda(
            conn, k,
            target_chapter=args.chapter,
            target_verse=args.verse,
            force=args.force,
        )
        grand_total += count

    log.info(f"{'='*60}")
    log.info(f"Done! Newly scraped/updated: {grand_total} verses")
    log.info(f"Database: {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
