"""Audit a chapter manifest before splitting a PDF."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def audit_manifest(
    manifest_path: str,
    pdf_path: str | None = None,
    last_end_page: int | None = None,
) -> dict[str, Any]:
    """Return a structured audit report. Page numbers are 1-based and inclusive."""
    manifest_file = Path(manifest_path)
    if not manifest_file.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_file}")

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in manifest at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Manifest root must be a JSON object.")
    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        raise ValueError("Manifest must contain a non-empty 'chapters' array.")

    pdf_page_count = None
    if pdf_path:
        source = Path(pdf_path)
        if not source.is_file():
            raise FileNotFoundError(f"PDF not found: {source}")
        from pypdf import PdfReader
        reader = PdfReader(str(source), strict=False)
        if reader.is_encrypted:
            raise ValueError("The PDF is encrypted. Decrypt it locally before auditing.")
        pdf_page_count = len(reader.pages)
    else:
        value = data.get("page_count")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            pdf_page_count = value

    errors: list[str] = []
    warnings: list[str] = []
    normalized: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    seen_starts: set[int] = set()

    for index, item in enumerate(chapters, start=1):
        label = f"Chapter entry {index}"
        if not isinstance(item, dict):
            errors.append(f"{label} must be a JSON object.")
            continue

        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{label} has a missing or empty title.")
            title = f"entry {index}"

        number = item.get("chapter_number")
        if number is not None:
            if isinstance(number, bool) or not isinstance(number, int) or number < 1:
                errors.append(f"{label} ({title!r}) has invalid chapter_number {number!r}.")
            elif number in seen_numbers:
                errors.append(f"Duplicate chapter_number {number}: {title!r}.")
            else:
                seen_numbers.add(number)

        start = item.get("start_page")
        end = item.get("end_page")
        if isinstance(start, bool) or not isinstance(start, int) or start < 1:
            errors.append(f"{label} ({title!r}) has invalid start_page {start!r}; expected an integer >= 1.")
            continue
        if start in seen_starts:
            errors.append(f"Duplicate start_page {start} ({title!r}).")
        seen_starts.add(start)

        if end is not None and (
            isinstance(end, bool) or not isinstance(end, int) or end < start
        ):
            errors.append(
                f"{label} ({title!r}) has invalid end_page {end!r}; "
                f"expected null or an integer >= start_page ({start})."
            )
            continue
        if pdf_page_count is not None:
            if start > pdf_page_count:
                errors.append(
                    f"{label} ({title!r}) starts at page {start}, beyond PDF page count {pdf_page_count}."
                )
            if end is not None and end > pdf_page_count:
                errors.append(
                    f"{label} ({title!r}) ends at page {end}, beyond PDF page count {pdf_page_count}."
                )
        normalized.append({
            "index": index, "title": title.strip(), "start_page": start,
            "end_page": end, "chapter_number": number,
        })

    normalized.sort(key=lambda c: (c["start_page"], c["index"]))
    if not normalized:
        errors.append("No valid chapter start pages were found.")
    else:
        for i, chapter in enumerate(normalized):
            next_chapter = normalized[i + 1] if i + 1 < len(normalized) else None
            expected_end = next_chapter["start_page"] - 1 if next_chapter else last_end_page
            end = chapter["end_page"]

            if next_chapter and chapter["start_page"] >= next_chapter["start_page"]:
                # Duplicate starts are also reported above; avoid making a confusing gap message.
                continue

            if next_chapter and end is not None:
                if end < expected_end:
                    warnings.append(
                        f"Gap between {chapter['title']!r} (ends {end}) and "
                        f"{next_chapter['title']!r} (starts {next_chapter['start_page']}); "
                        f"pages {end + 1}-{expected_end} are not assigned to a chapter."
                    )
                elif end > expected_end:
                    errors.append(
                        f"Overlap: {chapter['title']!r} ends at {end}, but "
                        f"{next_chapter['title']!r} starts at {next_chapter['start_page']}."
                    )
            elif next_chapter and end is None:
                warnings.append(
                    f"{chapter['title']!r} has no end_page; the splitter can infer "
                    f"{expected_end} from the next chapter start."
                )

        final = normalized[-1]
        if final["end_page"] is None and last_end_page is None:
            warnings.append(
                f"Final chapter {final['title']!r} has no end_page. Confirm it in the manifest "
                "or pass --last-end-page."
            )
        elif last_end_page is not None:
            if last_end_page < final["start_page"]:
                errors.append(
                    f"--last-end-page ({last_end_page}) is before final chapter start "
                    f"({final['start_page']})."
                )
            if pdf_page_count is not None and last_end_page > pdf_page_count:
                errors.append(
                    f"--last-end-page ({last_end_page}) exceeds PDF page count ({pdf_page_count})."
                )
            if final["end_page"] is not None and final["end_page"] != last_end_page:
                warnings.append(
                    f"--last-end-page overrides final manifest end_page "
                    f"{final['end_page']} with {last_end_page} for splitting."
                )

    if pdf_page_count is None:
        warnings.append(
            "PDF page count was not independently verified. Pass --pdf to validate ranges "
            "against the actual source PDF."
        )

    return {
        "manifest": str(manifest_file.resolve()),
        "pdf": str(Path(pdf_path).resolve()) if pdf_path else None,
        "pdf_page_count": pdf_page_count,
        "chapter_entries": len(chapters),
        "valid_entries": len(normalized),
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


def print_audit_report(report: dict[str, Any]) -> None:
    print("PDF Chapter Splitter — Manifest Audit")
    print(f"Manifest: {report['manifest']}")
    if report["pdf"]:
        print(f"PDF: {report['pdf']}")
    print(f"PDF page count: {report['pdf_page_count'] if report['pdf_page_count'] is not None else 'not verified'}")
    print(f"Chapter entries: {report['chapter_entries']}")
    print(f"Valid entries: {report['valid_entries']}")
    print(f"Errors: {len(report['errors'])}")
    for message in report["errors"]:
        print(f"  ERROR: {message}")
    print(f"Warnings: {len(report['warnings'])}")
    for message in report["warnings"]:
        print(f"  WARNING: {message}")
    print("RESULT: " + ("PASS" if report["passed"] else "FAIL"))
