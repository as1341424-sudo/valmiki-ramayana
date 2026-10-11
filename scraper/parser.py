"""
parser.py — HTML parsers for srivalmikiramayana.com pages.

Handles:
  - Kanda index pages  → list of chapter URLs
  - Chapter pages      → list of verse URLs + chapter metadata
  - Verse pages        → all verse fields (Sanskrit, transliteration, etc.)
"""

import re
from datetime import datetime
from bs4 import BeautifulSoup

BASE_URL = "https://srivalmikiramayana.com"

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


def _clean_text(element) -> str:
    """Extract clean text from a BeautifulSoup element, preserving newlines."""
    if element is None:
        return ""
    # Replace <br> with newline
    for br in element.find_all("br"):
        br.replace_with("\n")
    return element.get_text(separator=" ").strip()


def _clean_html(element) -> str:
    """Return inner HTML as string (for fields where we want to preserve markup)."""
    if element is None:
        return ""
    return str(element).strip()


def parse_kanda_page(html: str, kanda_num: int) -> dict:
    """
    Parse a kanda index page (/en/{kanda_num}/).
    Returns:
        {
            'kanda_num': int,
            'kanda_name': str,
            'chapters': [
                {'num': int, 'title': str, 'url': str, 'intro': str},
                ...
            ]
        }
    """
    soup = BeautifulSoup(html, "lxml")
    chapters = []

    # Chapter links are inside .canto_structure ul li a
    structure = soup.find("div", class_="canto_structure")
    if not structure:
        return {"kanda_num": kanda_num, "kanda_name": KANDA_NAMES.get(kanda_num, ""), "chapters": []}

    for li in structure.find_all("li"):
        a = li.find("a")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        # Match numeric chapter links like /en/1/5/
        m = re.match(r"^/en/\d+/(\d+)/$", href)
        if not m:
            continue
        chapter_num = int(m.group(1))

        # Chapter title is inside <span> within the <a>
        span = a.find("span")
        title = span.get_text(strip=True) if span else a.get_text(strip=True)

        # Remove "Chapter N: " prefix from title if present
        title = re.sub(r"^Chapter\s+\d+[:\s]+", "", title).strip()

        # Chapter intro is in .cs_chapter_introduction
        intro_div = li.find("div", class_="cs_chapter_introduction")
        intro = _clean_text(intro_div) if intro_div else ""

        chapters.append({
            "num": chapter_num,
            "title": title,
            "url": BASE_URL + href,
            "intro": intro,
        })

    return {
        "kanda_num": kanda_num,
        "kanda_name": KANDA_NAMES.get(kanda_num, ""),
        "chapters": chapters,
    }


def parse_chapter_page(html: str, kanda_num: int, chapter_num: int, chapter_url: str) -> dict:
    """
    Parse a chapter index page (/en/{kanda}/{chapter}/).
    Returns:
        {
            'kanda_num': int,
            'chapter_num': int,
            'chapter_title': str,
            'chapter_intro': str,
            'url': str,
            'verse_links': [
                {'verse_ref': '1.1.1', 'url': str},
                ...
            ]
        }
    """
    soup = BeautifulSoup(html, "lxml")

    # Title from .division_title
    title_div = soup.find("div", class_="division_title")
    chapter_title = ""
    if title_div:
        t1s = title_div.find_all("div", class_="t1")
        if t1s:
            # Replace <br> with newline first, then get text
            last_t1 = t1s[-1]
            for br in last_t1.find_all("br"):
                br.replace_with("\n")
            raw = last_t1.get_text(separator="\n", strip=False)
            # Strip "Chapter N" prefix line, keep just the title
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            # Remove any line that is purely "Chapter N" or "Canto N..."
            lines = [l for l in lines if not re.match(r'^(Chapter|Canto)\s+\d+$', l)]
            chapter_title = lines[0] if lines else ""

    # Verse links from .canto_structure li .txt_title a
    structure = soup.find("div", class_="canto_structure")
    verse_links = []
    if structure:
        for li in structure.find_all("li"):
            title_el = li.find("div", class_="txt_title")
            if not title_el:
                continue
            a = title_el.find("a")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            # Match /en/1/1/1/ or /en/1/1/19-20/
            m = re.match(r"^/en/(\d+)/(\d+)/([\d\-]+)/?$", href)
            if m:
                verse_ref_raw = m.group(3)
                verse_ref = f"{kanda_num}.{chapter_num}.{verse_ref_raw}"
            else:
                # Also handle ?pid= links like Text 3.1.1 or Text 3.1.4-5
                text_label = a.get_text(strip=True)
                m2 = re.search(r"(\d+)\.(\d+)\.([\d\-]+)", text_label)
                if m2:
                    verse_ref = f"{m2.group(1)}.{m2.group(2)}.{m2.group(3)}"
                else:
                    continue

            full_url = BASE_URL + href if href.startswith("/") else href
            verse_links.append({
                "verse_ref": verse_ref,
                "url": full_url,
            })

    return {
        "kanda_num": kanda_num,
        "chapter_num": chapter_num,
        "chapter_title": chapter_title,
        "chapter_intro": "",
        "url": chapter_url,
        "verse_links": verse_links,
    }


def _parse_verse_range(verse_ref: str) -> tuple[int, int]:
    """
    Parse verse_ref like '1.1.19-20' → (19, 20).
    Single verse '1.1.8' → (8, 8).
    """
    parts = verse_ref.split(".")
    verse_part = parts[-1]  # e.g. "19-20" or "8"
    if "-" in verse_part:
        start, end = verse_part.split("-", 1)
        return int(start), int(end)
    return int(verse_part), int(verse_part)


def parse_verse_page(html: str, url: str, kanda_num: int, chapter_num: int,
                     verse_ref: str, chapter_title: str = "") -> dict:
    """
    Parse a single verse page.
    Returns a dict matching the 'verses' table schema.
    """
    soup = BeautifulSoup(html, "lxml")

    # Check for 404 / "not found"
    main = soup.find("div", class_="mainpage_content")
    if main and "not found" in main.get_text().lower():
        return {}

    dts = soup.find("div", class_="division_text_structure")
    if not dts:
        return {}

    def get_field(css_class: str) -> str:
        el = dts.find("div", class_=css_class)
        return _clean_text(el) if el else ""

    def get_field_html(css_class: str) -> str:
        el = dts.find("div", class_=css_class)
        if not el:
            return ""
        # Return inner text content but preserve paragraph structure
        paras = [p.get_text(separator="\n").strip() for p in el.find_all("p")]
        return "\n\n".join(p for p in paras if p)

    sanskrit       = get_field("dts_devanagari")
    transliteration = get_field("dts_text")
    word_meaning   = get_field("dts_wordbyword")
    translation    = get_field("dts_translation")
    commentary     = get_field_html("dts_comment")

    # Quotations section (outside dts)
    quotes_div = soup.find("div", class_="division_quotes")
    quotations = _clean_text(quotes_div) if quotes_div else ""

    # Footnotes section
    notes_div = soup.find("div", class_="division_notes")
    footnotes = _clean_text(notes_div) if notes_div else ""

    # Get chapter title from page if not passed in
    if not chapter_title:
        title_div = soup.find("div", class_="division_title")
        if title_div:
            t1s = title_div.find_all("div", class_="t1")
            if t1s:
                last_t1 = t1s[-1]
                for br in last_t1.find_all("br"):
                    br.replace_with("\n")
                raw = last_t1.get_text(separator="\n", strip=False)
                lines = [l.strip() for l in raw.split("\n") if l.strip()]
                lines = [l for l in lines if not re.match(r'^(Chapter|Canto)\s+\d+$', l)]
                chapter_title = lines[0] if lines else ""

    verse_num_start, verse_num_end = _parse_verse_range(verse_ref)

    return {
        "kanda_num":        kanda_num,
        "kanda_name":       KANDA_NAMES.get(kanda_num, ""),
        "kanda_slug":       KANDA_SLUGS.get(kanda_num, ""),
        "chapter_num":      chapter_num,
        "chapter_title":    chapter_title,
        "verse_ref":        verse_ref,
        "verse_num_start":  verse_num_start,
        "verse_num_end":    verse_num_end,
        "sanskrit":         sanskrit,
        "transliteration":  transliteration,
        "word_meaning":     word_meaning,
        "translation":      translation,
        "commentary":       commentary,
        "quotations":       quotations,
        "footnotes":        footnotes,
        "url":              url,
        "scraped_at":       datetime.utcnow().isoformat(),
    }
