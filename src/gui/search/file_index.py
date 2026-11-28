"""In-memory index of project files.

The index stores metadata only, never file contents. It is built once when a
project is opened and refreshed after create/rename/delete operations. File
name search then runs entirely in memory, so it stays instant even for large
projects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "build",
    "dist",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

MAX_INDEXED_FILES = 50_000
MAX_TEXT_FILE_BYTES = 1_000_000

# Extensions that are always treated as text. Files with other extensions
# are probed for a NUL byte before content search.
TEXT_SUFFIXES = {
    ".scs",
    ".gwf",
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".qss",
    ".css",
    ".html",
    ".xml",
    ".csv",
    ".js",
    ".ts",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".java",
    ".rs",
    ".go",
    ".sh",
    ".bat",
    ".ps1",
}


@dataclass(frozen=True)
class IndexedFile:
    path: Path
    rel: str
    name: str
    suffix: str
    size: int
    mtime: float

    @property
    def directory(self) -> str:
        parent = Path(self.rel).parent.as_posix()
        return "" if parent == "." else parent


def skip_dir(name: str) -> bool:
    """Return True for dependency, build and hidden directories."""
    return name in IGNORED_DIRS or name.startswith(".")


def iter_project_files(root: Path):
    """Yield files below *root* without following symlinks.

    ``os.scandir`` is used instead of ``os.walk`` because it avoids extra
    ``stat`` calls and makes skipping symlinked loops explicit.
    """
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if not skip_dir(entry.name):
                                stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            yield Path(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue


class FileIndex:
    """Metadata snapshot of the project tree."""

    def __init__(self) -> None:
        self._root: Path | None = None
        self._files: list[IndexedFile] = []
        self._by_path: dict[Path, IndexedFile] = {}

    @property
    def root(self) -> Path | None:
        return self._root

    @property
    def files(self) -> list[IndexedFile]:
        return self._files

    def __len__(self) -> int:
        return len(self._files)

    def clear(self) -> None:
        self._root = None
        self._files = []
        self._by_path = {}

    def refresh(self, root: Path) -> None:
        """Rebuild the index for *root*."""
        root = Path(root).resolve()
        files: list[IndexedFile] = []
        for path in iter_project_files(root):
            try:
                stat = path.stat()
            except OSError:
                continue
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            files.append(
                IndexedFile(
                    path=path,
                    rel=rel,
                    name=path.name,
                    suffix=path.suffix.lower(),
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                )
            )
            if len(files) >= MAX_INDEXED_FILES:
                break

        files.sort(key=lambda item: item.rel.casefold())
        self._root = root
        self._files = files
        self._by_path = {item.path: item for item in files}

    def get(self, path: Path) -> IndexedFile | None:
        try:
            return self._by_path.get(Path(path).resolve())
        except OSError:
            return None

    def contains(self, path: Path) -> bool:
        return self.get(path) is not None
