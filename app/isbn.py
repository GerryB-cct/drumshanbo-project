"""ISBN lookup using the Open Library API (no key needed)."""
import logging
import re

import requests

log = logging.getLogger(__name__)

BASE = "https://openlibrary.org"
HEADERS = {"User-Agent": "DrumshanboMusicLibrary/0.1 (library catalogue PoC)"}
TIMEOUT = 8


def clean_isbn(isbn):
    return re.sub(r"[^0-9Xx]", "", isbn or "").upper()


def _get_json(path):
    resp = requests.get(BASE + path, headers=HEADERS, timeout=TIMEOUT)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _author_names(keys):
    names = []
    for key in keys[:3]:
        try:
            data = _get_json(f"{key}.json")
        except requests.RequestException:
            continue
        if data and data.get("name"):
            names.append(data["name"])
    return names


def lookup(isbn):
    """Return {"title", "author", "cover_url", "isbn"} or None if not found.

    Raises requests.RequestException if Open Library can't be reached.
    """
    isbn = clean_isbn(isbn)
    if len(isbn) not in (10, 13):
        return None
    data = _get_json(f"/isbn/{isbn}.json")
    if not data or not data.get("title"):
        return None

    title = data["title"]
    if data.get("subtitle"):
        title = f"{title}: {data['subtitle']}"

    author_keys = [a["key"] for a in data.get("authors", []) if isinstance(a, dict) and a.get("key")]
    if not author_keys and data.get("works"):
        try:
            work = _get_json(f"{data['works'][0]['key']}.json") or {}
            author_keys = [
                a["author"]["key"] for a in work.get("authors", [])
                if isinstance(a, dict) and isinstance(a.get("author"), dict)
            ]
        except (requests.RequestException, KeyError, IndexError):
            author_keys = []
    names = _author_names(author_keys)
    author = ", ".join(names) or (data.get("by_statement") or "").strip()

    covers = [c for c in data.get("covers", []) if isinstance(c, int) and c > 0]
    cover_url = f"https://covers.openlibrary.org/b/id/{covers[0]}-M.jpg" if covers else ""

    return {"isbn": isbn, "title": title, "author": author, "cover_url": cover_url}
