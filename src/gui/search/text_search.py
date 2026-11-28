"""Qt adapter for project-wide text search.

The pure parsing, filtering, ranking and scanning engine lives in
:mod:`src.utils.search.text_search`.  This module keeps only QObject/QRunnable
integration and generation cancellation for the GUI.
"""

from __future__ import annotations

import re
import threading

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from src.utils.search.file_index import IndexedFile
from src.utils.search.text_search import (
    MAX_RESULTS,
    TextMatch,
    compile_query,
    is_probably_text,
    make_snippet,
    rank_text_matches,
    scan_text_files,
    text_files,
)


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
        try:
            matches = scan_text_files(
                self.pattern,
                self.files,
                cancelled=self._cancelled,
                max_results=self.max_results,
            )
            if self._cancelled.is_set():
                return
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
