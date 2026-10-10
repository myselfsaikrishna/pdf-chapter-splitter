"""Command-line interface for the PDF chapter splitter."""
import argparse
import json
from pathlib import Path
from pypdf import PdfReader
from detector import detect_bookmarks, detect_contents
from splitter import split_pdf


def cmd_inspect(args):
    path = Path(args.pdf)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")
    reader = PdfReader(str(path), strict=False)
    print(f"PDF: {path.resolve()}")
    print(f"Pages: {len(reader.pages)}")
    print(f"Encrypted: {reader.is_encrypted}")
    try:
        outline = reader.outline
        print(f"Has bookmarks: {'yes' if outline else 'no'}")
        if outline:
            detected = detect_bookmarks(str(path))
            print(f"Bookmark destinations found: {len(detected['chapters'])}")
            for item in detected["chapters"][:30]:
                print(f"  PDF page {item['start_page']:>5}: {item['title']}")
            if len(detected["chapters"]) > 30:
                print(f"  ... and {len(detected['chapters']) - 30} more")
    except Exception as exc:
        print(f"Could not read bookmarks: {exc}")


def cmd_detect(args):
    data = detect_contents(args.pdf, max_contents_pages=args.max_contents_pages)
    if not data.get("chapters"):
        data = detect_bookmarks(args.pdf)
        data["message"] = "No contents entries were detected; bookmark detection was attempted."
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    found = sum(1 for chapter in data.get("chapters", []) if chapter.get("start_page"))
    print(f"PDF pages: {data['page_count']}")
    print(f"Detection method: {data.get('detection_method')}")
    print(f"Chapter entries: {len(data.get('chapters', []))}")
    print(f"Chapter start pages found: {found}")
    print(f"Manifest written to: {output.resolve()}")
    print("Review the manifest before splitting; null start_page values must be corrected.")


def cmd_split(args):
    report = split_pdf(args.pdf, args.manifest, args.output_dir, last_end_page=args.last_end_page)
    print(f"Split {len(report['chapters'])} chapters into: {report['output_directory']}")
    for item in report["chapters"]:
        print(f"  {item['title']}: PDF pages {item['start_page']}-{item['end_page']} -> {Path(item['output_file']).name}")


def cmd_batch(args):
    failures = 0
    for job in args.jobs:
        parts = job.split("|")
        if len(parts) != 3 or not all(part.strip() for part in parts):
            print(f"Invalid job {job!r}. Expected PDF_PATH|MANIFEST_JSON_PATH|OUTPUT_DIRECTORY")
            failures += 1
            continue
        try:
            report = split_pdf(parts[0], parts[1], parts[2])
            print(f"OK: {parts[0]} -> {report['output_directory']} ({len(report['chapters'])} chapters)")
        except Exception as exc:
            print(f"FAILED: {parts[0]}: {exc}")
            failures += 1
    if failures:
        raise SystemExit(1)


def build_parser():
    parser = argparse.ArgumentParser(description="Split large local PDF textbooks into chapter PDFs.")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Show PDF page count and bookmarks.")
    inspect.add_argument("pdf")
    inspect.set_defaults(func=cmd_inspect)
    detect = sub.add_parser("detect", help="Detect chapters from contents text or bookmarks.")
    detect.add_argument("pdf")
    detect.add_argument("--output", default="chapters.json")
    detect.add_argument("--max-contents-pages", type=int, default=50)
    detect.set_defaults(func=cmd_detect)
    split = sub.add_parser("split", help="Split a PDF using a reviewed JSON manifest.")
    split.add_argument("pdf")
    split.add_argument("--manifest", required=True)
    split.add_argument("--output-dir", required=True)
    split.add_argument(
        "--last-end-page",
        type=int,
        default=None,
        help="Optional inclusive PDF page number where the final chapter should end."
    )
    split.set_defaults(func=cmd_split)
    batch = sub.add_parser("batch", help="Split multiple PDFs using reviewed manifests.")
    batch.add_argument("--jobs", nargs="+", required=True)
    batch.set_defaults(func=cmd_batch)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
