# PDF Chapter Splitter

A Python command-line tool for detecting chapter boundaries in large PDF books and splitting them into separate chapter PDFs.

The tool is designed to help readers, students, researchers, and developers process large textbooks and reference books without manually calculating every page range.

## Features

- **Chapter detection:** Identify potential chapter starts using available PDF text, headings, and document structure.
- **JSON manifest:** Save detected chapters in an editable JSON file so boundaries can be reviewed or corrected before splitting.
- **PDF splitting:** Export individual chapter PDFs using the reviewed manifest.
- **Page-boundary control:** Specify the final physical page to include when a book contains appendices, indexes, or other material that should be excluded.
- **Command-line interface:** Run detection and splitting from a terminal or integrate the commands into a larger workflow.
- **Original-file preservation:** Create separate output PDFs instead of modifying the source PDF.
- **Reviewable results:** Keep chapter titles, page numbers, and other detection details in a manifest that can be inspected and corrected.

Detection quality depends on the PDF's text layer, document structure, page numbering, and chapter-heading format. Always review the generated manifest before splitting important documents.

## How it works

The workflow has three main stages:

1. **Inspect the PDF** to understand its page count and available document information.
2. **Detect chapter boundaries** and generate a JSON manifest.
3. **Review the manifest** and split the PDF into individual chapter files.

The manifest is an intermediate file: it allows you to correct chapter titles or page boundaries before generating the final PDFs.

## Requirements

- Python 3.10 or later is recommended. The project has not necessarily been tested across every Python version or operating system.
- `pypdf`, as listed in `requirements.txt`.
- A PDF file that you have permission to process.

Additional packages may be required for optional repair, diagnostics, or other functionality if those features are included in your local project version.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/myselfsaikrishna/pdf-chapter-splitter.git
cd pdf-chapter-splitter
```

### 2. Create a virtual environment

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell prevents activation, you can run the virtual environment's Python executable directly without activating it.

**Linux or macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Usage

Run commands from the project root, where `cli.py` is located.

### Inspect a PDF

```bash
python cli.py inspect "/path/to/book.pdf"
```

Use the inspection command to review the PDF before attempting chapter detection.

### Detect chapters

```bash
python cli.py detect "/path/to/book.pdf" --output chapters.json
```

This creates a JSON manifest containing the detected chapter information.

Review the manifest before proceeding. Check that:

- Chapter titles are correct.
- The start page of each chapter is correct.
- The page numbering refers to the expected physical PDF pages.
- The final chapter ends at the intended page.
- Any introductory material, appendices, indexes, or unwanted trailing pages are handled appropriately.

The detection output should be treated as a proposed set of boundaries, not as an infallible result.

### Audit the manifest before splitting

Run the audit command after detection and after making manual edits. It checks the manifest structure, chapter titles, chapter numbers when present, start/end page values, duplicate starts, overlapping ranges, gaps between explicitly assigned ranges, and page limits.

**Recommended: validate against the source PDF**

```bash
python cli.py audit --manifest chapters.json --pdf "/path/to/book.pdf"
```

On Windows PowerShell:

```powershell
.\\.venv\\Scripts\\python.exe cli.py audit --manifest chapters.json --pdf "C:\\path\\to\\book.pdf"
```

If the last chapter intentionally ends before the physical end of the PDF, pass the same boundary you plan to use for splitting:

```powershell
.\\.venv\\Scripts\\python.exe cli.py audit --manifest chapters.json --pdf "C:\\path\\to\\book.pdf" --last-end-page 2695
```

Replace the example path and page number with values for your own document. The audit command does not modify the manifest or PDF.

You can also audit without a source PDF:

```bash
python cli.py audit --manifest chapters.json
```

In this mode, the tool uses `page_count` from the manifest if present and warns that the page count was not independently verified. Passing `--pdf` is recommended.

**How to interpret the result**

- `RESULT: PASS` means no blocking structural or range errors were found. Read warnings and manually inspect chapter starts; a pass does not prove the headings are semantically correct.
- `RESULT: FAIL` means errors were found. The command exits with status code `1`, which is useful in scripts and CI.
- Gaps between explicitly specified chapter ranges are reported as warnings because some documents intentionally leave front matter, inserts, or other pages unassigned. Review each gap before splitting.
- Overlaps, duplicate chapter numbers, duplicate start pages, invalid ranges, and ranges beyond the known page count are errors.

The audit checks consistency and page ranges; it cannot confirm that a page visually contains the correct chapter heading. Always inspect representative pages in the source PDF and resulting chapter files.

### Split the PDF

```bash
python cli.py split "/path/to/book.pdf" --manifest chapters.json --output-dir "./output"
```

The command uses the manifest to generate individual chapter PDFs in the specified output directory.

### Specify the final page to include

If the PDF contains extra pages after the last chapter, you can explicitly set the last physical page to include:

```bash
python cli.py split "/path/to/book.pdf" --manifest chapters.json --output-dir "./output" --last-end-page 2695
```

Replace `2695` with the appropriate page number for your PDF. Do not copy this example value unless it applies to your document.

### Windows PowerShell example

If you are using the virtual environment created above, you can run the commands with its Python executable:

```powershell
.\.venv\Scripts\python.exe cli.py inspect "C:\path\to\book.pdf"

.\.venv\Scripts\python.exe cli.py detect "C:\path\to\book.pdf" --output chapters.json

.\.venv\Scripts\python.exe cli.py split "C:\path\to\book.pdf" --manifest chapters.json --output-dir "C:\path\to\output"
```

To see the exact commands and options supported by your installed version, run:

```powershell
.\.venv\Scripts\python.exe cli.py --help
.\.venv\Scripts\python.exe cli.py inspect --help
.\.venv\Scripts\python.exe cli.py detect --help
.\.venv\Scripts\python.exe cli.py split --help
```

## Understanding page numbers

PDFs may contain more than one numbering system:

- **Physical page number:** The page's position in the PDF file.
- **Printed page number:** The number printed on the book page.
- **PDF viewer page label:** A label displayed by a PDF viewer, which may differ from the physical position.

For splitting, the manifest must use the page-number convention expected by the implementation. Check the actual pages in the PDF when validating a chapter boundary, especially when front matter or unnumbered divider pages are present.

## Reviewing and correcting the manifest

Automated chapter detection can make mistakes because books use different layouts. For example, a chapter title might appear on a separate page, be split across lines, or contain unusual spacing in extracted text.

Before splitting:

1. Open the JSON manifest.
2. Compare representative chapter starts with the source PDF.
3. Correct any incorrect chapter titles or page boundaries.
4. Confirm that the final chapter ends at the intended page.
5. Run the split command.
6. Open a few output PDFs and confirm their contents.

A practical validation approach is to inspect the first chapter, several chapters from different parts of the book, and the last chapter.

## Troubleshooting

### The chapter title contains missing or unusual spaces

Some PDFs have text extraction issues caused by embedded fonts, character encoding, or the way text is positioned on the page. The extracted title may not match the printed title exactly.

Review the manifest and correct the title if necessary. If the issue is widespread, inspect the extracted text and improve the title-normalization logic.

### A chapter starts on the wrong page

Do not rely only on the detected confidence score. Check the source PDF and correct the chapter's start page in the manifest before splitting.

### The PDF cannot be opened or processed

The file may be malformed, encrypted, damaged, or restricted. Check that you can open it in a PDF viewer and that you have permission to process it. Any repair step should be performed on a copy, leaving the original unchanged.

### The output folder contains unexpected pages

Check the manifest's chapter start pages, calculated end pages, and the `--last-end-page` argument. Confirm that the last page number uses the convention expected by the CLI.

## Development and tests

Install the runtime dependency:

```bash
python -m pip install -r requirements.txt
```

The audit tests use Python's built-in `unittest`, so no test framework needs to be installed:

```bash
python -m unittest discover -s tests -v
```

Check available CLI commands with:

```bash
python cli.py --help
python cli.py audit --help
```


## Current limitations

- Chapter detection is heuristic and may require manual corrections.
- Results depend on the structure and quality of the source PDF.
- Scanned PDFs without a usable text layer may require OCR before reliable chapter detection is possible.
- Printed page numbers and physical PDF page positions may differ.
- A successful split does not guarantee that every chapter boundary is correct; review the output files.

OCR support, a graphical interface, and other future enhancements should be considered planned work unless they are explicitly implemented in the current version.

## Privacy and copyright

The tool is intended for PDFs that you own, created, or are authorized to process.

- Do not commit copyrighted textbooks, private documents, or other source PDFs to this public repository without permission.
- Do not commit generated chapter PDFs from copyrighted books.
- Do not publish personal data, access tokens, credentials, or private file paths in examples or logs.
- Keep large generated outputs and local virtual environments out of version control.

The source code and the documents processed with it are separate: publishing this tool does not grant permission to redistribute the PDFs processed using it.

## Contributing

Contributions are welcome. Useful improvements include:

- Better chapter-heading detection.
- More robust handling of PDF text extraction.
- Automated tests for page boundaries and manifest validation.
- Clear error messages and additional CLI options.
- Documentation and examples using public-domain or openly licensed PDFs.

For substantial changes, consider opening an issue first to discuss the proposed improvement.

## License

No license is specified by this README. Before inviting others to reuse or modify the code, add a license file and update this section with the license you choose.

## Acknowledgements

This project uses the Python PDF-processing ecosystem, including `pypdf`.

If you find a problem or have a suggestion, please open an issue in the repository.
