"""Turn files into clean Documents.

Every loader produces Markdown-like text: headings start with '#', blocks are separated by
blank lines. The chunker relies on that shape.
"""

from __future__ import annotations

import re
from pathlib import Path

from ragent.models import Document

SUPPORTED = {".md", ".markdown", ".txt", ".html", ".htm"}
_H1 = re.compile(r"^#\s+(.*\S)\s*$", re.MULTILINE)
_BLANKS = re.compile(r"\n{3,}")
# Elements that never hold article text.
_DROP = ["script", "style", "nav", "header", "footer", "aside", "noscript", "form", "svg", "button"]
_BLOCKS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "tr", "dt", "dd"]


def _tidy(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    return _BLANKS.sub("\n\n", "\n".join(lines)).strip()


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, text). Keeps headings, paragraphs, list items, code and table rows."""
    from bs4 import BeautifulSoup  # lazy: only needed for HTML input

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_DROP):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    blocks: list[str] = []
    for element in root.find_all(_BLOCKS):
        # Skip blocks nested in another kept block (e.g. <p> inside <li>) to avoid duplicates.
        if element.find_parent(["li", "tr", "pre", "dd"]) is not None:
            continue
        if element.name == "pre":
            body = element.get_text().strip("\n")
            if body:
                blocks.append(f"```\n{body}\n```")
            continue
        if element.name == "tr":
            cells = [c.get_text(" ", strip=True) for c in element.find_all(["th", "td"])]
            text = " | ".join(c for c in cells if c)
        else:
            text = " ".join(element.get_text(" ", strip=True).split())
        if not text:
            continue
        if element.name[0] == "h" and element.name[1:].isdigit():
            blocks.append("#" * int(element.name[1]) + " " + text)
        elif element.name == "li":
            blocks.append("- " + text)
        else:
            blocks.append(text)
    text = _tidy("\n\n".join(blocks))
    title_tag = soup.find("title")
    h1 = _H1.search(text)
    title = (h1.group(1) if h1 else "") or (title_tag.get_text(strip=True) if title_tag else "")
    return title, text


def load_path(path: Path, url: str = "") -> Document:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"unsupported file type: {path}")
    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        title, text = html_to_text(raw)
    else:
        text = _tidy(raw)
        match = _H1.search(text)
        title = match.group(1) if match else ""
    if not text:
        raise ValueError(f"no text extracted from {path}")
    return Document(
        source=path.stem,
        title=title or path.stem,
        text=text,
        metadata={"path": str(path), "url": url},
    )


def load_dir(directory: Path, urls: dict[str, str] | None = None) -> list[Document]:
    """Load every supported file under a directory, sorted by path. `urls` maps a file
    stem to its original URL (see data/sources.yaml)."""
    urls = urls or {}
    paths = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    documents = [load_path(p, urls.get(p.stem, "")) for p in paths]
    stems = [d.source for d in documents]
    duplicates = {s for s in stems if stems.count(s) > 1}
    if duplicates:
        raise ValueError(
            f"duplicate document names (file stems must be unique): {sorted(duplicates)}"
        )
    return documents
