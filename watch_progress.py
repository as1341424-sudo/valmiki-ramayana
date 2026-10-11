"""
watch_progress.py — Live progress monitor for the scraper.
Shows real-time verse count, current chapter, and estimated time.

Run: python watch_progress.py
"""
import sqlite3
import time
import os
import sys

DB = "data/ramayana.db"
LOG = "data/scrape.log"

KANDA_NAMES = {
    1: "Bāla-kāṇḍa       (77 ch)",
    2: "Ayodhyā-kāṇḍa    (119 ch)",
    3: "Āraṇya-kāṇḍa     (75 ch)",
    4: "Kiṣkindhā-kāṇḍa  (67 ch)",
    5: "Sundara-kāṇḍa    (68 ch)",
    6: "Yuddha-kāṇḍa     (131 ch)",
    7: "Uttara-kāṇḍa     (111 ch)",
}

def get_stats():
    try:
        conn = sqlite3.connect(DB)
        rows = conn.execute(
            "SELECT kanda_num, count(DISTINCT chapter_num), count(*) "
            "FROM verses GROUP BY kanda_num ORDER BY kanda_num"
        ).fetchall()
        total = conn.execute("SELECT count(*) FROM verses").fetchone()[0]
        conn.close()
        return rows, total
    except:
        return [], 0

def last_log_lines(n=5):
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [l.rstrip() for l in lines[-n:]]
    except:
        return []

def bar(pct, width=30):
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)

os.system("cls" if os.name == "nt" else "clear")
print("🕉  Sri Valmiki Ramayana — Scraper Progress Monitor")
print("   Press Ctrl+C to stop watching (scraper keeps running)\n")

try:
    while True:
        rows, total = get_stats()
        lines = last_log_lines(4)

        os.system("cls" if os.name == "nt" else "clear")
        print("🕉  Sri Valmiki Ramayana — Live Scraper Progress")
        print("=" * 60)
        print(f"  Total verses in DB : {total:,}")
        print()

        for row in rows:
            k, ch, v = row
            name = KANDA_NAMES.get(k, f"Kanda {k}")
            print(f"  Kanda {k} · {name}")
            print(f"          {ch} chapters · {v} verses scraped")

        print()
        print("  Recent activity:")
        for line in lines:
            tag = ""
            if "[saved]"   in line: tag = "✅ "
            elif "[WARNING]" in line: tag = "⚠  "
            elif "[ERROR]"   in line: tag = "❌ "
            elif "Chapter"   in line: tag = "📖 "
            elif "Kanda"     in line: tag = "📚 "
            # Extract timestamp + message
            parts = line.split("] ", 1)
            msg = parts[-1] if len(parts) > 1 else line
            print(f"    {tag}{msg[:70]}")

        print()
        print(f"  Refreshing in 10s… (Ctrl+C to exit monitor)")
        time.sleep(10)
except KeyboardInterrupt:
    print("\n  Monitor stopped. Scraper is still running in background.")
    print(f"  Final count: {get_stats()[1]:,} verses")
