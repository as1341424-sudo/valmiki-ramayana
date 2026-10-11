"""verify_db.py — Quick database integrity check."""
import sqlite3, json, os, sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = "data/ramayana.db"
if not os.path.exists(DB):
    print("ERROR: Database not found. Run the scraper first.")
    sys.exit(1)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# ── Stats ────────────────────────────────────────────────────────────
total = conn.execute("SELECT COUNT(*) FROM verses").fetchone()[0]
print(f"{'='*55}")
print(f"  Total verses in DB : {total}")
print(f"{'='*55}")

# ── Verse 1.1.1 ──────────────────────────────────────────────────────
v = conn.execute("SELECT * FROM verses WHERE verse_ref=?", ("1.1.1",)).fetchone()
if v:
    d = dict(v)
    print("\n[PASS] Verse 1.1.1")
    print(f"  kanda_name      : {d['kanda_name']}")
    print(f"  chapter_title   : {d['chapter_title']}")
    print(f"  sanskrit        : {d['sanskrit'][:60] if d['sanskrit'] else 'MISSING'}")
    print(f"  transliteration : {d['transliteration'][:60] if d['transliteration'] else 'MISSING'}")
    print(f"  word_meaning    : {str(d['word_meaning'])[:60] if d['word_meaning'] else 'MISSING'}")
    print(f"  translation     : {d['translation'][:80] if d['translation'] else 'MISSING'}")
    print(f"  commentary len  : {len(d['commentary']) if d['commentary'] else 0} chars")
    print(f"  url             : {d['url']}")
else:
    print("[FAIL] Verse 1.1.1 NOT found")

# ── Combined verse lookup: 1.1.19 -> 1.1.19-20 ───────────────────────
print()
for qv in [19, 20]:
    row = conn.execute(
        "SELECT verse_ref, verse_num_start, verse_num_end FROM verses "
        "WHERE kanda_num=1 AND chapter_num=1 AND verse_num_start<=? AND verse_num_end>=?",
        (qv, qv)
    ).fetchone()
    if row:
        d = dict(row)
        status = "[PASS]" if d["verse_ref"] == "1.1.19-20" else "[WARN]"
        print(f"{status} Lookup verse {qv} -> ref={d['verse_ref']} "
              f"(start={d['verse_num_start']}, end={d['verse_num_end']})")
    else:
        print(f"[SKIP] Verse {qv} not yet scraped")

# ── Recent verses ────────────────────────────────────────────────────
print()
rows = conn.execute(
    "SELECT verse_ref FROM verses ORDER BY id DESC LIMIT 8"
).fetchall()
print(f"Last 8 saved : {[dict(r)['verse_ref'] for r in rows]}")

# ── FTS5 smoke test ──────────────────────────────────────────────────
try:
    fts = conn.execute(
        "SELECT verse_ref FROM verses_fts WHERE verses_fts MATCH ? LIMIT 3",
        ("Narada",)
    ).fetchall()
    print(f"\n[PASS] FTS5 search 'Narada' -> {[dict(r)['verse_ref'] for r in fts]}")
except Exception as e:
    print(f"[FAIL] FTS5 error: {e}")

# ── JSON backup ──────────────────────────────────────────────────────
json_path = os.path.join("data", "json", "1", "1", "1.json")
if os.path.exists(json_path):
    with open(json_path, encoding="utf-8") as f:
        j = json.load(f)
    print(f"\n[PASS] JSON backup: {json_path}")
    print(f"  Fields: {list(j.keys())}")
else:
    print(f"\n[SKIP] JSON backup not found at {json_path}")

print(f"\n{'='*55}")
conn.close()
