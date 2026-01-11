#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate year-grouped HTML cards for publications from a BibTeX file.

Input : publications.bib
Output: publications_generated.html   (HTML sections only)

Usage:
  python tools/generate_publications.py publications.bib > publications_generated.html
"""

import re
import sys
from html import escape

def split_entries(bibtex: str):
    # Split by @...{...} blocks (very forgiving parser)
    entries = []
    buff = []
    depth = 0
    in_entry = False

    for line in bibtex.splitlines():
        if line.strip().startswith("@"):
            if buff:
                entries.append("\n".join(buff).strip())
                buff = []
            in_entry = True
            depth = 0

        if in_entry:
            buff.append(line)
            depth += line.count("{") - line.count("}")
            # naive end detection: depth <= 0 and line has "}"
            if depth <= 0 and line.strip().endswith("}"):
                entries.append("\n".join(buff).strip())
                buff = []
                in_entry = False

    if buff:
        entries.append("\n".join(buff).strip())
    return [e for e in entries if e.startswith("@")]

_field_re = re.compile(r'^\s*([a-zA-Z]+)\s*=\s*(.+?)\s*,?\s*$', re.MULTILINE)

def clean_value(v: str) -> str:
    v = v.strip()
    # Remove surrounding braces/quotes
    if v.startswith("{") and v.endswith("}"):
        v = v[1:-1]
    if v.startswith('"') and v.endswith('"'):
        v = v[1:-1]
    # Collapse whitespace
    v = re.sub(r"\s+", " ", v).strip()
    # Remove LaTeX braces used for capitalization
    v = v.replace("{", "").replace("}", "")
    return v

def parse_entry(entry: str) -> dict:
    header = entry.split("\n", 1)[0]
    m = re.match(r'^@(\w+)\s*{\s*([^,]+)\s*,', header.strip())
    etype = m.group(1).lower() if m else "misc"

    fields = {}
    for k, v in _field_re.findall(entry):
        fields[k.lower()] = clean_value(v)

    # Year fallback: try to find a 4-digit year anywhere
    year = fields.get("year", "")
    if not year:
        ym = re.search(r"\b(19\d{2}|20\d{2})\b", entry)
        year = ym.group(1) if ym else "Unknown"

    # Title, authors
    title = fields.get("title", "Untitled")
    author = fields.get("author", "").replace(" and ", ", ")

    # Venue: journal/booktitle
    venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""

    # Link priority: url > doi
    url = fields.get("url", "")
    doi = fields.get("doi", "")
    if not url and doi:
        url = f"https://doi.org/{doi}"

    # Optional: pages/volume/number
    volume = fields.get("volume", "")
    number = fields.get("number", "")
    pages = fields.get("pages", "")

    extra = []
    if venue:
        extra.append(venue)
    if volume:
        extra.append(f"vol. {volume}")
    if number:
        extra.append(f"no. {number}")
    if pages:
        extra.append(f"pp. {pages}")

    return {
        "type": etype,
        "key": (m.group(2) if m else ""),
        "year": year,
        "title": title,
        "author": author,
        "venue": venue,
        "url": url,
        "extra": ", ".join(extra),
    }

def sort_key(pub):
    # Sort by year desc, then title
    y = pub["year"]
    ynum = int(y) if y.isdigit() else -1
    return (-ynum, pub["title"].lower())

def format_li(pub: dict) -> str:
    title = escape(pub["title"])
    author = escape(pub["author"]) if pub["author"] else ""
    extra = escape(pub["extra"]) if pub["extra"] else ""

    if pub["url"]:
        t = f'<a href="{escape(pub["url"])}" target="_blank" rel="noopener noreferrer"><strong>{title}</strong></a>'
    else:
        t = f"<strong>{title}</strong>"

    parts = [t]
    if author:
        parts.append(f"— {author}.")
    if extra:
        parts.append(f"<em>{extra}</em>.")
    return " ".join(parts)

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/generate_publications.py publications.bib > publications_generated.html", file=sys.stderr)
        sys.exit(1)

    bib_path = sys.argv[1]
    bib = open(bib_path, "r", encoding="utf-8").read()

    pubs = [parse_entry(e) for e in split_entries(bib)]
    pubs.sort(key=sort_key)

    # Group by year
    grouped = {}
    for p in pubs:
        grouped.setdefault(p["year"], []).append(p)

    # Year order: numeric years desc, then 'Unknown'
    years = sorted(
        grouped.keys(),
        key=lambda y: (0, -int(y)) if y.isdigit() else (1, 0)
    )

    # Output HTML sections
    for i, year in enumerate(years):
        margin = "" if i == 0 else ' style="margin-top:14px;"'
        print(f'<section class="card"{margin}>')
        print(f"  <h2>{escape(year)}</h2>")
        print('  <ul class="pub-list">')
        for p in grouped[year]:
            print(f"    <li>{format_li(p)}</li>")
        print("  </ul>")
        print("</section>\n")

if __name__ == "__main__":
    main()
