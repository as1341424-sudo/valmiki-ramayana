# 🕉 Śrī Vālmīki Rāmāyaṇa — Searchable Digital Corpus

A local full-text searchable corpus of the Śrī Vālmīki Rāmāyaṇa, scraped from
[srivalmikiramayana.com](https://srivalmikiramayana.com).

Each verse is stored with:
- **Sanskrit** (Devanāgarī)
- **Transliteration** (IAST)
- **Word-by-word meaning**
- **English translation**
- **Commentary** (detailed)
- **Quotations & Footnotes**

---

## Folder Structure

```
Sri Valmiki Ramayana/
├── scraper/
│   ├── scrape.py          ← Main crawler
│   ├── parser.py          ← HTML parser
│   ├── db.py              ← SQLite + FTS5 helpers
│   └── requirements.txt
├── data/
│   ├── ramayana.db        ← SQLite database (auto-created)
│   ├── scrape.log         ← Scraping progress log
│   └── json/              ← Per-verse JSON backups
│       └── {kanda}/{chapter}/{verse}.json
├── server/
│   └── api.py             ← Flask search API
├── search/
│   ├── index.html         ← Search UI
│   ├── style.css
│   └── app.js
└── exports/               ← Optional HTML/EPUB exports
```

---

## Quick Start

### 1. Install Python dependencies

```bash
cd "Sri Valmiki Ramayana/scraper"
pip install -r requirements.txt
```

### 2. Run the scraper

```bash
# Scrape all available kāṇḍas (currently 1–3)
python scraper/scrape.py

# Scrape only Bāla-kāṇḍa
python scraper/scrape.py --kanda 1

# Scrape only Chapter 1 of Bāla-kāṇḍa
python scraper/scrape.py --kanda 1 --chapter 1

# Scrape a single verse
python scraper/scrape.py --kanda 1 --chapter 1 --verse 1

# Re-scrape (overwrite existing data)
python scraper/scrape.py --kanda 1 --force
```

> **Rate limiting**: 3–5 second delay per request.
> ~24,000 total verses → ~24–34 hours for a full scrape across all kāṇḍas.
> Currently only Kāṇḍas 1–3 are published on the site.

### 3. Start the search API

```bash
python server/api.py
```

The API starts at `http://localhost:5000`.

### 4. Open the search UI

Navigate to `http://localhost:5000` in your browser.

---

## Verse Reference Lookup

Type `1.1.1` in the search box to fetch **Kāṇḍa 1, Chapter 1, Verse 1**.

| Input | Fetches |
|-------|---------|
| `1.1.1` | Verse 1 of Ch.1, Bāla-kāṇḍa |
| `1.1.8` | Verse 8 — the famous Rāma-description verse |
| `1.1.19` | Returns the combined verse **1.1.19–20** |
| `1.1.20` | Returns the same combined verse **1.1.19–20** |
| `2.3.5` | Verse 5 of Ch.3, Ayodhyā-kāṇḍa |

The system handles **combined verses** (e.g., `19-20`) automatically —
querying either `19` or `20` will return the combined entry.

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Search UI |
| `GET /stats` | DB statistics |
| `GET /verse/1.1.1` | Fetch verse by reference |
| `GET /verse/1.1.19` | Fetches combined 1.1.19-20 |
| `GET /chapter/1/1` | All verses in Kāṇḍa 1, Ch.1 |
| `GET /search?q=Narada` | Full-text search |
| `GET /search?q=Narada&kanda=1` | Search within Bāla-kāṇḍa |
| `GET /search?q=...&limit=50&offset=30` | Paginated search |
| `GET /kandas` | List all kāṇḍas with verse counts |
| `GET /chapters/1` | Chapter list for Bāla-kāṇḍa |

---

## Database Schema

```sql
-- Main verse table
verses (
    kanda_num, kanda_name, kanda_slug,
    chapter_num, chapter_title,
    verse_ref,          -- "1.1.1" or "1.1.19-20"
    verse_num_start,    -- 1  (or 19 for "19-20")
    verse_num_end,      -- 1  (or 20 for "19-20")
    sanskrit, transliteration, word_meaning,
    translation, commentary, quotations, footnotes,
    url, scraped_at
)

-- FTS5 full-text search (auto-synced via triggers)
verses_fts (
    verse_ref, kanda_name, chapter_title,
    sanskrit, transliteration, word_meaning,
    translation, commentary
)

-- Chapter metadata
chapters (kanda_num, chapter_num, chapter_title, chapter_intro, url)
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search box |
| `Esc` | Close verse modal / clear search |
| `Enter` | Run search immediately |

---

## Available Kāṇḍas

| # | Name | Status |
|---|------|--------|
| 1 | Bāla-kāṇḍa | ✅ Available |
| 2 | Ayodhyā-kāṇḍa | ✅ Available |
| 3 | Āraṇya-kāṇḍa | ✅ Available |
| 4 | Kiṣkindhā-kāṇḍa | ⏳ Not yet published |
| 5 | Sundara-kāṇḍa | ⏳ Not yet published |
| 6 | Yuddha-kāṇḍa | ⏳ Not yet published |
| 7 | Uttara-kāṇḍa | ⏳ Not yet published |

---

## JSON Backup

Every scraped verse is also saved as a JSON file at:
```
data/json/{kanda_num}/{chapter_num}/{verse}.json
```

Example `data/json/1/1/1.json`:
```json
{
  "kanda_num": 1,
  "kanda_name": "Bāla-kāṇḍa",
  "chapter_num": 1,
  "chapter_title": "Contents of the Rāmāyaṇa Summarized",
  "verse_ref": "1.1.1",
  "verse_num_start": 1,
  "verse_num_end": 1,
  "sanskrit": "तपःस्वाध्यायनिरतं ...",
  "transliteration": "tapaḥ-svādhyāya-nirataṁ ...",
  "word_meaning": "tapaḥ-svādhyāya-niratam = ...",
  "translation": "The ascetic Vālmīki ...",
  "commentary": "...",
  "url": "https://srivalmikiramayana.com/en/1/1/1/"
}
```

---

*Content © Rūpa Raghunātha Vāṇī Publications. For personal research and study only.*
