"""
db.py — SQLite database helpers for Sri Valmiki Ramayana corpus.

Tables:
  - verses    : structured verse data (7 fields + metadata)
  - verses_fts: FTS5 virtual table for full-text search
  - chapters  : chapter metadata
"""

import sqlite3
import os
from datetime import datetime


KANDA_NAMES = {
    1: "Bāla-kāṇḍa",
    2: "Ayodhyā-kāṇḍa",
    3: "Āraṇya-kāṇḍa",
    4: "Kiṣkindhā-kāṇḍa",
    5: "Sundara-kāṇḍa",
    6: "Yuddha-kāṇḍa",
    7: "Uttara-kāṇḍa",
}

KANDA_SLUGS = {
    1: "bala-kanda",
    2: "ayodhya-kanda",
    3: "aranya-kanda",
    4: "kishkindha-kanda",
    5: "sundara-kanda",
    6: "yuddha-kanda",
    7: "uttara-kanda",
}


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str) -> sqlite3.Connection:
    """Create all tables and FTS5 index. Safe to call on existing DB."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS chapters (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            kanda_num       INTEGER NOT NULL,
            kanda_name      TEXT    NOT NULL,
            chapter_num     INTEGER NOT NULL,
            chapter_title   TEXT,
            chapter_intro   TEXT,
            url             TEXT    NOT NULL,
            scraped_at      TEXT    NOT NULL,
            UNIQUE(kanda_num, chapter_num)
        );

        CREATE TABLE IF NOT EXISTS verses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            kanda_num       INTEGER NOT NULL,
            kanda_name      TEXT    NOT NULL,
            kanda_slug      TEXT    NOT NULL,
            chapter_num     INTEGER NOT NULL,
            chapter_title   TEXT,
            verse_ref       TEXT    NOT NULL,
            verse_num_start INTEGER NOT NULL,
            verse_num_end   INTEGER NOT NULL,
            sanskrit        TEXT,
            transliteration TEXT,
            word_meaning    TEXT,
            translation     TEXT,
            commentary      TEXT,
            quotations      TEXT,
            footnotes       TEXT,
            url             TEXT    NOT NULL,
            scraped_at      TEXT    NOT NULL,
            UNIQUE(kanda_num, chapter_num, verse_ref)
        );

        CREATE INDEX IF NOT EXISTS idx_verses_kanda ON verses(kanda_num);
        CREATE INDEX IF NOT EXISTS idx_verses_chapter ON verses(kanda_num, chapter_num);
        CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(verse_ref);
        CREATE INDEX IF NOT EXISTS idx_verses_range ON verses(kanda_num, chapter_num, verse_num_start, verse_num_end);
    """)

    # FTS5 — content table keeps data in sync with 'verses'
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS verses_fts USING fts5(
            verse_ref,
            kanda_name,
            chapter_title,
            sanskrit,
            transliteration,
            word_meaning,
            translation,
            commentary,
            content='verses',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        )
    """)

    # Triggers to keep FTS in sync
    cur.executescript("""
        CREATE TRIGGER IF NOT EXISTS verses_ai AFTER INSERT ON verses BEGIN
            INSERT INTO verses_fts(rowid, verse_ref, kanda_name, chapter_title,
                sanskrit, transliteration, word_meaning, translation, commentary)
            VALUES (new.id, new.verse_ref, new.kanda_name, new.chapter_title,
                new.sanskrit, new.transliteration, new.word_meaning, new.translation, new.commentary);
        END;

        CREATE TRIGGER IF NOT EXISTS verses_ad AFTER DELETE ON verses BEGIN
            INSERT INTO verses_fts(verses_fts, rowid, verse_ref, kanda_name, chapter_title,
                sanskrit, transliteration, word_meaning, translation, commentary)
            VALUES ('delete', old.id, old.verse_ref, old.kanda_name, old.chapter_title,
                old.sanskrit, old.transliteration, old.word_meaning, old.translation, old.commentary);
        END;

        CREATE TRIGGER IF NOT EXISTS verses_au AFTER UPDATE ON verses BEGIN
            INSERT INTO verses_fts(verses_fts, rowid, verse_ref, kanda_name, chapter_title,
                sanskrit, transliteration, word_meaning, translation, commentary)
            VALUES ('delete', old.id, old.verse_ref, old.kanda_name, old.chapter_title,
                old.sanskrit, old.transliteration, old.word_meaning, old.translation, old.commentary);
            INSERT INTO verses_fts(rowid, verse_ref, kanda_name, chapter_title,
                sanskrit, transliteration, word_meaning, translation, commentary)
            VALUES (new.id, new.verse_ref, new.kanda_name, new.chapter_title,
                new.sanskrit, new.transliteration, new.word_meaning, new.translation, new.commentary);
        END;
    """)

    conn.commit()
    return conn


def insert_chapter(conn: sqlite3.Connection, chapter: dict) -> None:
    conn.execute("""
        INSERT INTO chapters
            (kanda_num, kanda_name, chapter_num, chapter_title, chapter_intro, url, scraped_at)
        VALUES
            (:kanda_num, :kanda_name, :chapter_num, :chapter_title, :chapter_intro, :url, :scraped_at)
        ON CONFLICT(kanda_num, chapter_num)
        DO UPDATE SET
            chapter_title = excluded.chapter_title,
            chapter_intro = excluded.chapter_intro,
            scraped_at    = excluded.scraped_at
    """, chapter)
    conn.commit()


def insert_verse(conn: sqlite3.Connection, verse: dict) -> None:
    """Upsert a verse. FTS index is updated via trigger."""
    conn.execute("""
        INSERT INTO verses
            (kanda_num, kanda_name, kanda_slug, chapter_num, chapter_title,
             verse_ref, verse_num_start, verse_num_end,
             sanskrit, transliteration, word_meaning, translation,
             commentary, quotations, footnotes, url, scraped_at)
        VALUES
            (:kanda_num, :kanda_name, :kanda_slug, :chapter_num, :chapter_title,
             :verse_ref, :verse_num_start, :verse_num_end,
             :sanskrit, :transliteration, :word_meaning, :translation,
             :commentary, :quotations, :footnotes, :url, :scraped_at)
        ON CONFLICT(kanda_num, chapter_num, verse_ref)
        DO UPDATE SET
            sanskrit        = excluded.sanskrit,
            transliteration = excluded.transliteration,
            word_meaning    = excluded.word_meaning,
            translation     = excluded.translation,
            commentary      = excluded.commentary,
            quotations      = excluded.quotations,
            footnotes       = excluded.footnotes,
            scraped_at      = excluded.scraped_at
    """, verse)
    conn.commit()


def is_verse_scraped(conn: sqlite3.Connection, kanda_num: int, chapter_num: int, verse_ref: str) -> bool:
    """Return True if verse already exists in DB with non-empty translation."""
    row = conn.execute("""
        SELECT id FROM verses
        WHERE kanda_num=? AND chapter_num=? AND verse_ref=?
          AND translation IS NOT NULL AND translation != ''
    """, (kanda_num, chapter_num, verse_ref)).fetchone()
    return row is not None


def is_chapter_scraped(conn: sqlite3.Connection, kanda_num: int, chapter_num: int) -> bool:
    row = conn.execute("""
        SELECT id FROM chapters WHERE kanda_num=? AND chapter_num=?
    """, (kanda_num, chapter_num)).fetchone()
    return row is not None


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """Rebuild FTS5 index from scratch (use after bulk inserts bypassing triggers)."""
    conn.execute("INSERT INTO verses_fts(verses_fts) VALUES('rebuild')")
    conn.commit()


def get_verse_by_ref(conn: sqlite3.Connection, kanda_num: int, chapter_num: int, verse_num: int) -> sqlite3.Row | None:
    """
    Fetch a verse by numeric reference. Handles combined verses:
    e.g., verse_num=19 will match verse_ref='1.1.19-20'
    where verse_num_start <= 19 AND verse_num_end >= 19
    """
    return conn.execute("""
        SELECT * FROM verses
        WHERE kanda_num = ?
          AND chapter_num = ?
          AND verse_num_start <= ?
          AND verse_num_end   >= ?
        ORDER BY verse_num_start
        LIMIT 1
    """, (kanda_num, chapter_num, verse_num, verse_num)).fetchone()


def search_verses(
    conn: sqlite3.Connection,
    query: str,
    kanda_num: int | None = None,
    chapter_num: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """Full-text search using FTS5. Returns verse rows ranked by relevance."""
    # Escape special FTS5 chars
    safe_q = query.replace('"', '""')
    fts_query = f'"{safe_q}"'

    filters = ""
    params: list = [fts_query]
    if kanda_num is not None:
        filters += " AND v.kanda_num = ?"
        params.append(kanda_num)
    if chapter_num is not None:
        filters += " AND v.chapter_num = ?"
        params.append(chapter_num)

    params += [limit, offset]
    sql = f"""
        SELECT v.*,
               snippet(verses_fts, 6, '<mark>', '</mark>', '…', 32) AS matched_snippet
        FROM verses_fts
        JOIN verses v ON verses_fts.rowid = v.id
        WHERE verses_fts MATCH ?
          {filters}
        ORDER BY rank
        LIMIT ? OFFSET ?
    """
    return conn.execute(sql, params).fetchall()


def get_chapter_verses(conn: sqlite3.Connection, kanda_num: int, chapter_num: int) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT * FROM verses
        WHERE kanda_num=? AND chapter_num=?
        ORDER BY verse_num_start
    """, (kanda_num, chapter_num)).fetchall()


def get_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM verses").fetchone()[0]
    by_kanda = conn.execute("""
        SELECT kanda_num, kanda_name, COUNT(*) as cnt
        FROM verses GROUP BY kanda_num ORDER BY kanda_num
    """).fetchall()
    return {"total_verses": total, "by_kanda": [dict(r) for r in by_kanda]}
