"""Chapter detection from PDF bookmarks, contents pages, and chapter headings.

TOC parsing is deliberately tolerant of multi-line titles and PDF text-extraction
artifacts. Page numbers in the TOC are printed page numbers; start_page/end_page
in the manifest are physical PDF page numbers (1-based).
"""
from pathlib import Path
import re

from pypdf import PdfReader


def _flatten_outline(outline, reader, output):
    for item in outline:
        if isinstance(item, list):
            _flatten_outline(item, reader, output)
            continue
        title = getattr(item, "title", None)
        if not title:
            continue
        try:
            page_index = reader.get_destination_page_number(item)
        except Exception:
            continue
        if page_index is not None and page_index >= 0:
            output.append({"title": str(title).strip(), "start_page": page_index + 1})


def detect_bookmarks(pdf_path: str) -> dict:
    reader = PdfReader(pdf_path, strict=False)
    chapters = []
    try:
        _flatten_outline(reader.outline, reader, chapters)
    except Exception:
        chapters = []
    unique, seen = [], set()
    for chapter in chapters:
        key = (chapter["title"], chapter["start_page"])
        if key not in seen:
            seen.add(key)
            unique.append(chapter)
    unique.sort(key=lambda c: (c["start_page"], c["title"].casefold()))
    return {
        "source_pdf": str(Path(pdf_path).resolve()),
        "page_count": len(reader.pages),
        "detection_method": "pdf_bookmarks",
        "chapters": unique,
        "review_required": True,
    }


def _normalize(text: str) -> str:
    text = text.lower().replace("\u00ad", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _repair_extracted_spacing(text: str) -> str:
    """Join common PDF artifacts like 'M ilestones' -> 'Milestones'."""
    text = text.replace("\u00ad", "")
    # Only join a single alphabetic character to a following lowercase word.
    # Punctuation-protected initials such as "A. Grippi" remain unchanged.
    text = re.sub(r"\b([A-Za-z])\s+([a-z]{2,})\b", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _chapter_entries_from_toc(text: str) -> list[dict]:
    """Parse numbered TOC entries, including titles wrapped across lines.

    A chapter begins on a line whose first token is a plausible chapter number.
    Its printed page is normally the final numeric token on a title line (often
    preceded by dotted leaders). Author lines are ignored after the page number.
    """
    raw_lines = [line.replace("\u00ad", " ").strip() for line in text.splitlines()]
    lines = [re.sub(r"\s+", " ", line) for line in raw_lines]

    # Extract chapter starts first, then collect title lines until a printed page
    # number is found or another chapter start begins.
    start_re = re.compile(r"^\s*(\d{1,3})\s+(.+?)\s*$")
    page_re = re.compile(r"^(.*?)\s*(?:\.{2,}\s*)?(\d{1,4})\s*$")
    starts = []
    for i, line in enumerate(lines):
        m = start_re.match(line)
        if not m:
            continue
        number = int(m.group(1))
        rest = m.group(2).strip()
        if not (1 <= number <= 300) or not rest:
            continue
        # Ignore obvious page furniture and dates; numbered chapter lines in
        # this book have a title after the number.
        if rest.lower().startswith(("contents", "part ", "section ", "appendix", "index")):
            continue
        starts.append((i, number, rest))

    entries = []
    for pos, (line_idx, number, first_text) in enumerate(starts):
        next_start_idx = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        title_parts = []
        printed_page = None

        for j in range(line_idx, next_start_idx):
            candidate = first_text if j == line_idx else lines[j]
            if not candidate:
                continue
            # The first line has already had its chapter number removed.
            # A trailing number after dotted leaders is a strong TOC page marker.
            pm = page_re.match(candidate)
            if pm:
                before, page_token = pm.groups()
                before = before.strip(" .\t")
                page_value = int(page_token)
                # A page number should follow some title text; avoid interpreting
                # a standalone short numeric line as a title/page pair.
                if before and 1 <= page_value <= 9999:
                    title_parts.append(before)
                    printed_page = page_value
                    break
            # Continuation lines can be part of a wrapped title. Do not absorb
            # likely author names indefinitely; the next chapter boundary caps it.
            title_parts.append(candidate.strip(" .\t"))

        if printed_page is None:
            continue

        title = " ".join(title_parts)
        # Remove dotted leaders, then repair split initial letters from extraction.
        title = re.sub(r"\.{2,}", " ", title)
        title = _repair_extracted_spacing(title)
        title = re.sub(r"\s+", " ", title).strip(" .\t")
        # If a line's author text was accidentally included before a later page
        # number, prefer the portion before common author separators when possible.
        title = re.sub(r"\s{2,}", " ", title)
        if len(title) < 4:
            continue
        entries.append({
            "chapter_number": number,
            "title": title,
            "printed_page": printed_page,
        })

    # One entry per chapter number. Prefer the title with the most useful text.
    unique = {}
    for entry in entries:
        n = entry["chapter_number"]
        if n not in unique or len(entry["title"]) > len(unique[n]["title"]):
            unique[n] = entry
    return [unique[n] for n in sorted(unique)]


def _find_contents_pages(reader, max_pages: int = 50) -> list[dict]:
    candidates = []
    for i in range(min(max_pages, len(reader.pages))):
        try:
            text = reader.pages[i].extract_text() or ""
        except Exception:
            continue
        norm = _normalize(text)
        if "contents" in norm and re.search(r"(?m)^\s*\d{1,3}\s+\S", text):
            entries = _chapter_entries_from_toc(text)
            if len(entries) >= 3:
                candidates.append({
                    "pdf_page": i + 1,
                    "text": text,
                    "entries": entries,
                })
    return candidates


def _title_matches_page(title: str, page_text: str) -> bool:
    title_norm = _normalize(_repair_extracted_spacing(title))
    page_norm = _normalize(_repair_extracted_spacing(page_text))
    if not title_norm or not page_norm:
        return False

    # First use ordinary word-aware matching.
    if title_norm in page_norm:
        return True
    words = title_norm.split()
    if len(words) >= 4:
        core = " ".join(words[:min(7, len(words))])
        if core in page_norm:
            return True

    # Some PDFs insert spaces *inside* words at arbitrary positions, e.g.
    # "Muc ociliary", "Br onchiectasis", or "Unc ommon". Compare compact
    # alphanumeric forms as a fallback. Shorter chapter titles are safe to
    # match compactly when the exact compact string is present on a nearby page;
    # the caller separately prefers pages containing the chapter-number marker.
    title_compact = re.sub(r"[^a-z0-9]+", "", title_norm)
    page_compact = re.sub(r"[^a-z0-9]+", "", page_norm)
    if len(title_compact) >= 10 and title_compact in page_compact:
        return True

    # Also check a substantial compact prefix for long titles where extraction
    # differs at the end of the heading or includes a subtitle variation.
    if len(title_compact) >= 40:
        prefix = title_compact[:min(55, len(title_compact))]
        if prefix in page_compact:
            return True
    return False


def _has_chapter_number_heading(chapter_number: int, page_text: str) -> bool:
    """Return True when extracted page text contains this chapter's heading marker."""
    text = _repair_extracted_spacing(page_text)
    # Allow whitespace/punctuation between CHAPTER and the number, but avoid
    # matching a mere TOC row such as "7 The Genetic Basis ... 118".
    return bool(re.search(
        rf"\bchapter\s*{chapter_number}\b",
        text,
        flags=re.IGNORECASE,
    ))


def _find_chapter_title_pages(reader, entry: dict, expected_page: int | None,
                              page_count: int, radius: int = 4,
                              lower_bound: int = 1) -> list[int]:
    """Search near an expected page, preferring a page with both title and chapter marker."""
    if expected_page is None:
        return []
    lo = max(lower_bound, expected_page - radius)
    hi = min(page_count, expected_page + radius)
    strong, title_only = [], []
    for page_num in range(lo, hi + 1):
        try:
            page_text = reader.pages[page_num - 1].extract_text() or ""
        except Exception:
            continue
        if _title_matches_page(entry["title"], page_text):
            if _has_chapter_number_heading(entry["chapter_number"], page_text):
                strong.append(page_num)
            else:
                title_only.append(page_num)
    # A chapter-number + title match is the strongest signal. Only fall back to
    # title-only matches if no numbered heading was found in the local window.
    return strong if strong else title_only


def detect_contents(pdf_path: str, max_contents_pages: int = 50, search_pages: int = 80) -> dict:
    """Detect chapter starts using actual title pages, not only a fixed TOC offset.

    The TOC page number and a first-chapter anchor establish an initial offset.
    Each chapter is then searched around its predicted location. When the actual
    chapter title is found, that physical PDF page becomes start_page. A heading
    match containing both the chapter number and title is preferred over a
    title-only match. Results remain flagged for review.
    """
    source = Path(pdf_path)
    reader = PdfReader(str(source), strict=False)
    toc_pages = _find_contents_pages(reader, max_contents_pages)
    if not toc_pages:
        return {
            "source_pdf": str(source.resolve()),
            "page_count": len(reader.pages),
            "detection_method": "contents_text",
            "chapters": [],
            "contents_pages": [],
            "review_required": True,
            "message": "No parseable contents page found in the first pages. OCR or a manual manifest may be needed.",
        }

    merged = {}
    for toc in toc_pages:
        for entry in toc["entries"]:
            num = entry["chapter_number"]
            if num not in merged or len(entry["title"]) > len(merged[num]["title"]):
                merged[num] = entry
    entries = [merged[n] for n in sorted(merged)]
    contents_end = max(t["pdf_page"] for t in toc_pages)

    # Find the first actual chapter opener. Merely finding the title is not enough:
    # the title can appear in the TOC immediately before the chapter begins.
    first_entry = entries[0] if entries else None
    anchor_page = None
    if first_entry:
        anchor_search_end = min(len(reader.pages), contents_end + max(search_pages, 31))
        for page_num in range(contents_end + 1, anchor_search_end + 1):
            try:
                page_text = reader.pages[page_num - 1].extract_text() or ""
            except Exception:
                continue
            if (_has_chapter_number_heading(first_entry["chapter_number"], page_text)
                    and _title_matches_page(first_entry["title"], page_text)):
                anchor_page = page_num
                break

    page_offset = (anchor_page - first_entry["printed_page"]
                   if first_entry and anchor_page else None)

    chapters = []
    for entry in entries:
        predicted_page = entry["printed_page"] + page_offset if page_offset is not None else None
        if predicted_page is not None and not (1 <= predicted_page <= len(reader.pages)):
            predicted_page = None

        candidates = _find_chapter_title_pages(
            reader, entry, predicted_page, len(reader.pages), radius=4,
            lower_bound=contents_end + 1,
        )
        # Use actual matched title page as the start; use offset prediction only
        # when no local title match can be found, and explicitly flag that case.
        actual_start = candidates[0] if candidates else predicted_page
        if candidates:
            validation = "chapter_heading_found" if any(
                _has_chapter_number_heading(entry["chapter_number"],
                    (reader.pages[p - 1].extract_text() or ""))
                for p in candidates
            ) else "title_found_without_chapter_number"
            confidence = "high" if validation == "chapter_heading_found" else "review"
        else:
            validation = "not_confirmed_by_title_text_using_offset_fallback"
            confidence = "low"

        chapters.append({
            "chapter_number": entry["chapter_number"],
            "title": entry["title"],
            "printed_page": entry["printed_page"],
            "predicted_start_page": predicted_page,
            "start_page": actual_start,
            "matched_candidates": candidates,
            "page_offset_used": page_offset,
            "validation": validation,
            "confidence": confidence,
        })

    # End pages are inclusive and derived from the next chapter's actual start.
    for idx, chapter in enumerate(chapters):
        if idx + 1 < len(chapters):
            next_start = chapters[idx + 1].get("start_page")
            chapter["end_page"] = next_start - 1 if next_start is not None else None
            chapter["end_page_status"] = (
                "calculated_from_next_chapter" if chapter["end_page"] is not None
                else "needs_review_due_to_missing_next_start"
            )
        else:
            chapter["end_page"] = None
            chapter["end_page_status"] = "manual_confirmation_required_for_final_chapter"

    detected_numbers = {c["chapter_number"] for c in chapters}
    missing_numbers = sorted(set(range(1, max(detected_numbers, default=0) + 1)) - detected_numbers)
    return {
        "source_pdf": str(source.resolve()),
        "page_count": len(reader.pages),
        "detection_method": "contents_text_plus_local_chapter_heading_search",
        "contents_pages": [t["pdf_page"] for t in toc_pages],
        "first_chapter_anchor_page": anchor_page,
        "page_offset_used": page_offset,
        "chapters": chapters,
        "detected_chapter_count": len(chapters),
        "missing_chapter_numbers": missing_numbers,
        "review_required": True,
        "notes": [
            "start_page and end_page are 1-based physical PDF page numbers, not printed page numbers.",
            "End pages are inclusive and are calculated as the page before the next chapter starts.",
            "Actual title matches override the initial printed-page offset prediction.",
            "Entries using offset fallback or title-only matches require manual review.",
            "The final chapter end_page is deliberately null and must be confirmed manually before splitting.",
        ],
    }
