"""PDF extraction routines."""
import json
import re
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from page_mapper import prepare_chapters


def safe_filename(title: str, max_length: int = 100) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", title)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = re.sub(r"_+", "_", cleaned)
    return (cleaned[:max_length].rstrip("._ ") or "chapter")


def split_pdf(pdf_path: str, manifest_path: str, output_dir: str, last_end_page: int | None = None) -> dict:
    source = Path(pdf_path)
    manifest_file = Path(manifest_path)
    out_dir = Path(output_dir)
    if not source.is_file():
        raise FileNotFoundError(f"PDF not found: {source}")
    if not manifest_file.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_file}")

    reader = PdfReader(str(source), strict=False)
    if reader.is_encrypted:
        raise ValueError("This PDF is encrypted. Decrypt it locally before splitting.")

    data = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    raw_chapters = data.get("chapters", [])

    # Apply the CLI override before range preparation, so a deliberately-null
    # final end_page in the manifest can be resolved by --last-end-page.
    if last_end_page is not None and raw_chapters:
        raw_chapters[-1]["end_page"] = last_end_page

    chapters = prepare_chapters(raw_chapters, len(reader.pages))

    # Optional override for the final chapter, useful when the PDF contains an
    # index, glossary, references, or other back matter after the final chapter.
    if last_end_page is not None:
        if last_end_page < chapters[-1].start_page:
            raise ValueError(
                f"last_end_page ({last_end_page}) is before the final chapter start "
                f"({chapters[-1].start_page})."
            )
        if last_end_page > len(reader.pages):
            raise ValueError(
                f"last_end_page ({last_end_page}) exceeds PDF page count ({len(reader.pages)})."
            )
        chapters[-1].end_page = last_end_page

    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "source_pdf": str(source.resolve()),
        "source_page_count": len(reader.pages),
        "output_directory": str(out_dir.resolve()),
        "last_end_page_override": last_end_page,
        "chapters": [],
    }
    used_names = set()
    for number, chapter in enumerate(chapters, start=1):
        stem = safe_filename(chapter.title)
        candidate = f"{number:03d}_{stem}.pdf"
        suffix = 2
        while candidate.casefold() in used_names or (out_dir / candidate).exists():
            candidate = f"{number:03d}_{stem}_{suffix}.pdf"
            suffix += 1
        used_names.add(candidate.casefold())

        writer = PdfWriter()
        # Manifest page numbers are 1-based and end_page is inclusive.
        for page_index in range(chapter.start_page - 1, chapter.end_page):
            writer.add_page(reader.pages[page_index])

        destination = out_dir / candidate
        with destination.open("wb") as handle:
            writer.write(handle)

        report["chapters"].append({
            "title": chapter.title,
            "start_page": chapter.start_page,
            "end_page": chapter.end_page,
            "page_count": chapter.end_page - chapter.start_page + 1,
            "output_file": str(destination.resolve()),
        })

    (out_dir / "split_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report
