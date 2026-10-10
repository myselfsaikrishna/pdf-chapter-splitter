"""Validate chapter page ranges and infer missing end pages."""
from models import Chapter


def prepare_chapters(raw_chapters, page_count: int) -> list[Chapter]:
    chapters = [
        Chapter(
            title=str(item.get("title", "")).strip(),
            start_page=int(item["start_page"]),
            end_page=(int(item["end_page"]) if item.get("end_page") is not None else None),
        )
        for item in raw_chapters
    ]
    if not chapters:
        raise ValueError("The manifest has no chapters.")

    chapters.sort(key=lambda c: c.start_page)
    for chapter in chapters:
        chapter.validate(page_count)

    # Do not allow two chapters to begin on the same page.
    starts = [c.start_page for c in chapters]
    if len(starts) != len(set(starts)):
        raise ValueError("Two or more chapters have the same start_page.")

    for i, chapter in enumerate(chapters):
        if chapter.end_page is None:
            if i + 1 < len(chapters):
                chapter.end_page = chapters[i + 1].start_page - 1
            else:
                raise ValueError(
                    "The final chapter has no end_page. Confirm its final PDF page "
                    "in the manifest or pass --last-end-page to the split command."
                )

        if i + 1 < len(chapters) and chapter.end_page >= chapters[i + 1].start_page:
            raise ValueError(
                f"Chapter {chapter.title!r} overlaps the next chapter. "
                "Review end_page values in the manifest."
            )
        chapter.validate(page_count)

    return chapters
