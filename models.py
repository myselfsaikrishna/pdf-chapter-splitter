"""Shared data structures for the PDF chapter splitter."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Chapter:
    title: str
    start_page: int
    end_page: Optional[int] = None

    def validate(self, page_count: int) -> None:
        if not self.title.strip():
            raise ValueError("Chapter title cannot be empty.")
        if self.start_page < 1 or self.start_page > page_count:
            raise ValueError(
                f"Chapter {self.title!r}: start_page {self.start_page} "
                f"is outside 1..{page_count}."
            )
        if self.end_page is not None:
            if self.end_page < self.start_page:
                raise ValueError(
                    f"Chapter {self.title!r}: end_page is before start_page."
                )
            if self.end_page > page_count:
                raise ValueError(
                    f"Chapter {self.title!r}: end_page {self.end_page} "
                    f"is outside 1..{page_count}."
                )
