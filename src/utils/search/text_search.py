from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.utils.search.file_index import MAX_TEXT_FILE_BYTES, TEXT_SUFFIXES, IndexedFile
from src.utils.search.fuzzy import fuzzy_match

MAX_RESULTS = 200
SNIPPET_WIDTH = 140


@dataclass(frozen=True)
class TextMatch:
    path: Path
    rel: str
    line: int
    column: int
    length: int
    line_text: str


def compile_query(
    query: str,
    *,
    case_sensitive: bool = False,
    regex: bool = False,
    whole_word: bool = False,
) -> re.Pattern:
    pattern = query if regex else re.escape(query)
    if whole_word:
        pattern = rf"(?<!\w)(?:{pattern})(?!\w)"
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(pattern, flags)


def is_probably_text(path: Path, suffix: str) -> bool:
    if suffix in TEXT_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            chunk = handle.read(4096)
    except OSError:
        return False
    return b"\x00" not in chunk


def text_files(index) -> list[IndexedFile]:
    return [
        item
        for item in index.files
        if item.size <= MAX_TEXT_FILE_BYTES
        and is_probably_text(item.path, item.suffix)
    ]


def make_snippet(
    line_text: str, column: int, length: int, width: int = SNIPPET_WIDTH
) -> tuple[str, tuple[int, int] | None]:
    text = line_text.rstrip("\r\n")
    start = max(0, column - 1)
    end = min(len(text), start + max(1, length))
    if len(text) <= width:
        return text, (start, max(1, end - start))

    left = max(0, start - width // 3)
    right = min(len(text), left + width)
    if right - left < width:
        left = max(0, right - width)
    snippet = text[left:right]
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(text) else ""
    return (
        f"{prefix}{snippet}{suffix}",
        (len(prefix) + start - left, max(1, end - start)),
    )


def rank_text_matches(
    matches: list[TextMatch], query: str, *, limit: int = MAX_RESULTS
) -> list[TextMatch]:
    by_file: dict[Path, list[TextMatch]] = {}
    for match in matches:
        by_file.setdefault(match.path, []).append(match)

    def file_key(path: Path):
        first_line = min(item.line for item in by_file[path])
        name_match = fuzzy_match(query, path.name)
        name_score = name_match.score if name_match is not None else 0.0
        return (
            -name_score,
            -len(by_file[path]),
            first_line,
            str(path).casefold(),
        )

    ordered: list[TextMatch] = []
    for path in sorted(by_file, key=file_key):
        ordered.extend(
            sorted(by_file[path], key=lambda item: (item.line, item.column))
        )
        if len(ordered) >= limit:
            break
    return ordered[:limit]


def scan_text_files(
    pattern: re.Pattern,
    files: Iterable[IndexedFile],
    *,
    cancelled: threading.Event | None = None,
    max_results: int = MAX_RESULTS,
) -> list[TextMatch]:
    matches: list[TextMatch] = []
    cancel_event = cancelled or threading.Event()

    for item in files:
        if cancel_event.is_set():
            return matches
        try:
            with item.path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle, 1):
                    if cancel_event.is_set():
                        return matches
                    for match in pattern.finditer(line):
                        matches.append(
                            TextMatch(
                                path=item.path,
                                rel=item.rel,
                                line=line_number,
                                column=match.start() + 1,
                                length=max(1, match.end() - match.start()),
                                line_text=line.rstrip("\r\n"),
                            )
                        )
                        if len(matches) >= max_results:
                            return matches
        except OSError:
            continue
    return matches
