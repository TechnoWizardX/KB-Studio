"""Project-wide text search.

Content search is the only part of quick open that touches every file, so it
runs on a worker thread. Each request gets a generation number: results from
an older generation are dropped, which is a lock-free way to cancel a search
when the user keeps typing.

Limits are deliberate:

- files larger than :data:`MAX_TEXT_FILE_BYTES` are skipped;
- binary files (a NUL byte in the first block) are skipped;
- the scan stops at :data:`MAX_RESULTS` matches;
- ignored directories never reach the scan because they are filtered by
  :class:`~src.gui.search.file_index.FileIndex`.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from src.gui.search.file_index import (
    MAX_TEXT_FILE_BYTES,
    TEXT_SUFFIXES,
    FileIndex,
    IndexedFile,
)
from src.gui.search.fuzzy import fuzzy_match

MAX_RESULTS = 200
SNIPPET_WIDTH = 140


@dataclass(frozen=True)
class TextMatch:
    path: Path
    rel: str
    line: int  # 1-based
    column: int  # 1-based
    length: int
    line_text: str


def compile_query(
    query: str,
    *,
    case_sensitive: bool = False,
    regex: bool = False,
    whole_word: bool = False,
) -> re.Pattern:
    """Compile a search query into a regular expression."""
    pattern = query if regex else re.escape(query)
    if whole_word:
        pattern = rf"(?<!\w)(?:{pattern})(?!\w)"
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(pattern, flags)


def is_probably_text(path: Path, suffix: str) -> bool:
    """Decide whether a file can be scanned as text."""
    if suffix in TEXT_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            chunk = handle.read(4096)
    except OSError:
        return False
    return b"\x00" not in chunk


def text_files(index: FileIndex) -> list[IndexedFile]:
    """Files eligible for content search, in index order."""
    return [
        item
        for item in index.files
        if item.size <= MAX_TEXT_FILE_BYTES
        and is_probably_text(item.path, item.suffix)
    ]


def make_snippet(
    line_text: str, column: int, length: int, width: int = SNIPPET_WIDTH
) -> tuple[str, tuple[int, int] | None]:
    """Trim a long line around a match and return highlight offsets.

    ``column`` is 1-based in the original line. The returned span is relative
    to the returned snippet, so the popup can highlight the exact match.
    """
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
    """Order matches by file relevance, then by position inside the file."""
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


class TextSearchSignals(QObject):
    finished = Signal(int, list)  # generation, list[TextMatch]
    failed = Signal(int, str)  # generation, error


class TextSearchJob(QRunnable):
    """Scan a fixed file list for one compiled pattern."""

    def __init__(
        self,
        generation: int,
        pattern: re.Pattern,
        files: list[IndexedFile],
        *,
        max_results: int = MAX_RESULTS,
    ) -> None:
        super().__init__()
        self.generation = generation
        self.pattern = pattern
        self.files = files
        self.max_results = max_results
        self.signals = TextSearchSignals()
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    @Slot()
    def run(self) -> None:
        matches: list[TextMatch] = []
        try:
            for item in self.files:
                if self._cancelled.is_set():
                    return
                try:
                    with item.path.open(
                        "r", encoding="utf-8", errors="replace"
                    ) as handle:
                        for line_number, line in enumerate(handle, 1):
                            if self._cancelled.is_set():
                                return
                            for match in self.pattern.finditer(line):
                                matches.append(
                                    TextMatch(
                                        path=item.path,
                                        rel=item.rel,
                                        line=line_number,
                                        column=match.start() + 1,
                                        length=max(
                                            1, match.end() - match.start()
                                        ),
                                        line_text=line.rstrip("\r\n"),
                                    )
                                )
                                if len(matches) >= self.max_results:
                                    self.signals.finished.emit(
                                        self.generation, matches
                                    )
                                    return
                except OSError:
                    continue
            self.signals.finished.emit(self.generation, matches)
        except Exception as error:  # pragma: no cover - defensive
            self.signals.failed.emit(self.generation, str(error))


class TextSearchController(QObject):
    """Owns the worker pool and keeps only the newest request alive."""

    results_ready = Signal(int, list)  # generation, list[TextMatch]
    failed = Signal(int, str)

    def __init__(
        self,
        pool: QThreadPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pool = pool or QThreadPool.globalInstance()
        self._generation = 0
        self._job: TextSearchJob | None = None

    @property
    def generation(self) -> int:
        return self._generation

    def cancel(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self._job = None
        self._generation += 1

    def search(
        self,
        query: str,
        files: list[IndexedFile],
        *,
        case_sensitive: bool = False,
        regex: bool = False,
        whole_word: bool = False,
    ) -> int:
        """Start a search and return its generation number."""
        self._generation += 1
        generation = self._generation

        if self._job is not None:
            self._job.cancel()

        try:
            pattern = compile_query(
                query,
                case_sensitive=case_sensitive,
                regex=regex,
                whole_word=whole_word,
            )
        except re.error as error:
            self._job = None
            self.failed.emit(generation, str(error))
            return generation

        job = TextSearchJob(generation, pattern, files)
        job.signals.finished.connect(self.results_ready)
        job.signals.failed.connect(self.failed)
        self._job = job
        self._pool.start(job)
        return generation
