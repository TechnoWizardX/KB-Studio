"""Backward-compatible imports for search file indexing.

New code should import from :mod:`src.utils.search.file_index`.
"""

from src.utils.search.file_index import (
    IGNORED_DIRS,
    MAX_INDEXED_FILES,
    MAX_TEXT_FILE_BYTES,
    TEXT_SUFFIXES,
    FileIndex,
    IndexedFile,
    iter_project_files,
    skip_dir,
)

__all__ = [
    "IGNORED_DIRS",
    "MAX_INDEXED_FILES",
    "MAX_TEXT_FILE_BYTES",
    "TEXT_SUFFIXES",
    "FileIndex",
    "IndexedFile",
    "iter_project_files",
    "skip_dir",
]
