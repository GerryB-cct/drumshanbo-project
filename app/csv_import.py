"""CSV book import: read the file, guess the column mapping, preview, import."""
import csv
import io
import re

from .extensions import db
from .models import Book

# (field, label, required)
FIELDS = [
    ("title", "Title", True),
    ("author", "Author / compiler", False),
    ("book_type", "Type", False),
    ("isbn", "ISBN", False),
    ("notes", "Notes", False),
    ("cover_url", "Cover image URL", False),
]

SYNONYMS = {
    "title": ["title", "book title", "book", "name", "book name"],
    "author": ["author", "authors", "compiler", "compiled by", "author/compiler", "author / compiler", "editor", "by"],
    "book_type": ["type", "book type", "category", "kind", "format"],
    "isbn": ["isbn", "isbn13", "isbn-13", "isbn10", "isbn-10", "isbn number"],
    "notes": ["notes", "note", "comments", "comment", "description", "remarks"],
    "cover_url": ["cover", "cover url", "cover image", "image", "image url", "cover_url"],
}

TYPE_WORDS = {
    "tune book": ["tune book", "tunebook", "tune", "tunes", "tune books", "music", "instrumental"],
    "songbook": ["songbook", "song book", "songs", "song", "songbooks", "ballads"],
    "reference": ["reference", "ref", "history", "reference book", "book about"],
}


def decode(raw_bytes):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def read_csv(text):
    """Return (headers, rows) where rows are lists of strings."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    return headers, rows[1:]


def _clean_header(h):
    return re.sub(r"\s+", " ", h.strip().lower().replace("_", " "))


def guess_mapping(headers):
    """{field: column index or None}"""
    mapping = {}
    cleaned = [_clean_header(h) for h in headers]
    used = set()
    for field, _label, _req in FIELDS:
        mapping[field] = None
        for i, h in enumerate(cleaned):
            if i not in used and h in SYNONYMS[field]:
                mapping[field] = i
                used.add(i)
                break
    return mapping


def normalise_type(value):
    v = _clean_header(value or "")
    if not v:
        return None
    for book_type, words in TYPE_WORDS.items():
        if v in words:
            return book_type
    return False  # present but not recognised


def normalise_isbn(value):
    v = re.sub(r"[^0-9Xx]", "", value or "").upper()
    return v or None


def map_row(row, mapping, default_type):
    """Return (data dict, None) or (None, reason)."""
    def cell(field):
        idx = mapping.get(field)
        if idx is None or idx >= len(row):
            return ""
        return row[idx].strip()

    title = cell("title")
    if not title:
        return None, "no title"
    if len(title) > 300:
        return None, "title is too long"
    raw_type = cell("book_type")
    book_type = normalise_type(raw_type)
    if book_type is False:
        return None, f"type \"{raw_type}\" not recognised (use tune book, songbook or reference)"
    isbn = normalise_isbn(cell("isbn"))
    if isbn and len(isbn) not in (10, 13):
        return None, f"ISBN \"{cell('isbn')}\" is not 10 or 13 digits"
    cover = cell("cover_url")
    if cover and not cover.lower().startswith(("http://", "https://")):
        cover = ""
    return {
        "title": title,
        "author": cell("author")[:200],
        "book_type": book_type or default_type,
        "isbn": isbn,
        "notes": cell("notes") or None,
        "cover_url": cover or None,
    }, None


def preview(rows, mapping, default_type, limit=10):
    out = []
    for i, row in enumerate(rows[:limit], start=2):
        data, error = map_row(row, mapping, default_type)
        out.append({"line": i, "data": data, "error": error})
    return out


def import_rows(rows, mapping, default_type):
    """Import every row. Returns (imported count, [(line number, reason)])."""
    imported = 0
    skipped = []
    seen_isbns = {b.isbn for b in Book.query.filter(Book.isbn.isnot(None)).all()}
    seen_titles = {
        (b.title.lower(), (b.author or "").lower()) for b in Book.query.with_entities(Book.title, Book.author)
    }
    for line, row in enumerate(rows, start=2):  # line 1 is the header
        data, error = map_row(row, mapping, default_type)
        if error:
            skipped.append((line, error))
            continue
        if data["isbn"] and data["isbn"] in seen_isbns:
            skipped.append((line, f"a book with ISBN {data['isbn']} is already in the catalogue"))
            continue
        key = (data["title"].lower(), data["author"].lower())
        if key in seen_titles:
            skipped.append((line, "the same title and author is already in the catalogue"))
            continue
        db.session.add(Book(status="available", **data))
        imported += 1
        seen_titles.add(key)
        if data["isbn"]:
            seen_isbns.add(data["isbn"])
    db.session.commit()
    return imported, skipped
