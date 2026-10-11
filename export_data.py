"""
export_data.py — Export all verses from SQLite → offline/data.js
Run this any time to refresh the offline app with latest scraped content.

Usage:  python export_data.py
"""

import sqlite3
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_PATH  = Path("data/ramayana.db")
OUT_DIR  = Path("offline")
OUT_FILE = OUT_DIR / "data.js"

OUT_DIR.mkdir(exist_ok=True)

if not DB_PATH.exists():
    print("❌ data/ramayana.db not found. Run the scraper first.")
    sys.exit(1)

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

print("📖 Reading verses from database…")
rows = conn.execute(
    "SELECT * FROM verses ORDER BY kanda_num, chapter_num, verse_num_start"
).fetchall()

verses = []
for r in rows:
    d = dict(r)
    verses.append({
        "id":              d["id"],
        "kanda_num":       d["kanda_num"],
        "kanda_name":      d["kanda_name"] or "",
        "chapter_num":     d["chapter_num"],
        "chapter_title":   d["chapter_title"] or "",
        "verse_ref":       d["verse_ref"] or "",
        "verse_num_start": d["verse_num_start"],
        "verse_num_end":   d["verse_num_end"],
        "sanskrit":        d["sanskrit"] or "",
        "transliteration": d["transliteration"] or "",
        "word_meaning":    d["word_meaning"] or "",
        "translation":     d["translation"] or "",
        "commentary":      d["commentary"] or "",
        "quotations":      d["quotations"] or "",
        "footnotes":       d["footnotes"] or "",
        "url":             d["url"] or "",
        "scraped_at":      d["scraped_at"] or "",
    })

print(f"   {len(verses):,} verses loaded")

# ── Build inverted index for offline FTS ─────────────────────────
print("🔍 Building search index…")

def tokenize(text: str) -> set:
    tokens = re.findall(
        r"[a-zA-ZāĀīĪūŪṛṝḷḹēōṃḥñṭḍṇśṣṁĀāĪīŪūṚṝḶḸĒŌṂḤÑṬḌṆŚṢṁ]+",
        text.lower()
    )
    return {t[:24] for t in tokens if len(t) >= 3}

inverted: dict[str, list[int]] = {}
for i, v in enumerate(verses):
    text = " ".join([
        v["translation"], v["commentary"], v["sanskrit"],
        v["transliteration"], v["word_meaning"], v["chapter_title"],
        v["kanda_name"], v["quotations"], v["footnotes"],
    ])
    for token in tokenize(text):
        inverted.setdefault(token, []).append(i)

print(f"   {len(inverted):,} index tokens")

# ── Stats ─────────────────────────────────────────────────────────
kanda_stats = {}
for v in verses:
    k = str(v["kanda_num"])
    if k not in kanda_stats:
        kanda_stats[k] = {"name": v["kanda_name"], "verses": 0, "chapters": set()}
    kanda_stats[k]["verses"] += 1
    kanda_stats[k]["chapters"].add(v["chapter_num"])
for k in kanda_stats:
    kanda_stats[k]["chapters"] = len(kanda_stats[k]["chapters"])

stats = {
    "total_verses":   len(verses),
    "total_chapters": sum(s["chapters"] for s in kanda_stats.values()),
    "kandas":         kanda_stats,
    "exported_at":    __import__("datetime").datetime.utcnow().isoformat() + "Z",
}

# ── Write data.js ─────────────────────────────────────────────────
print("💾 Writing offline/data.js…")
data = {"verses": verses, "index": inverted, "stats": stats}
json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
js = f"/* Sri Valmiki Ramayana — offline data bundle */\nwindow.RAMAYANA_DATA={json_str};\n"

with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write(js)

size_mb = OUT_FILE.stat().st_size / 1024 / 1024
print(f"\n✅ Done!")
print(f"   File  : {OUT_FILE}")
print(f"   Size  : {size_mb:.1f} MB")
print(f"   Verses: {len(verses):,}")
print(f"\n   Open offline/index.html in your browser to use the app.")
conn.close()
