"""Search providers and their shared result model.

A provider is a small object with ``id`` and ``search(text, context)``. The
quick-search controller only knows this interface, so a new mode is added by
writing a provider and registering it — the popup, keyboard handling and
ordering code stay untouched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QIcon

from src.utils.search.file_index import FileIndex
from src.utils.search.fuzzy import fuzzy_match
from src.utils.search.text_search import (
    MAX_RESULTS,
    TextMatch,
    make_snippet,
    rank_text_matches,
)

IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
MAX_FILE_RESULTS = 50
MAX_SYMBOL_RESULTS = 100


@dataclass
class SearchResult:
    """One row in the quick-search popup.

    ``kind`` tells the controller how to activate the row:

    - ``file`` / ``text`` / ``node`` / ``symbol`` / ``command`` / ``filter``
    - ``header`` and ``info`` are non-selectable display rows.
    """

    title: str
    subtitle: str = ""
    detail: str = ""
    payload: object = None
    score: float = 0.0
    kind: str = "file"
    group: str = ""
    title_spans: tuple[int, ...] = ()
    subtitle_spans: tuple[int, ...] = ()
    detail_spans: tuple[int, int] | None = None
    icon: QIcon | None = None

    @property
    def selectable(self) -> bool:
        return self.kind not in {"header", "info"}


@dataclass
class SearchContext:
    """Everything providers may need to know about the current window."""

    project_root: Path | None = None
    active_kind: str = ""
    active_widget: object = None
    recent_files: list[Path] = field(default_factory=list)


def header(title: str) -> SearchResult:
    return SearchResult(title=title, kind="header")


def info(title: str, detail: str = "") -> SearchResult:
    return SearchResult(title=title, detail=detail, kind="info")


class FileSearchProvider:
    """Rank project files by fuzzy match against name and relative path."""

    id = "files"

    def __init__(self, index: FileIndex) -> None:
        self.index = index

    def search(
        self, text: str, context: SearchContext, *, limit: int = MAX_FILE_RESULTS
    ) -> list[SearchResult]:
        query = text.strip()
        if not query:
            return self._recent_or_project(context, limit=limit)

        ranked: list[tuple[float, str, object, object, str]] = []
        for item in self.index.files:
            name_match = fuzzy_match(query, item.name)
            path_match = fuzzy_match(query, item.rel)
            if name_match is None and path_match is None:
                continue

            if name_match is not None and (
                path_match is None
                or name_match.score >= path_match.score * 0.85
            ):
                match, field_name = name_match, "name"
            else:
                match, field_name = path_match, "path"

            score = match.score - item.rel.count("/") * 0.75
            ranked.append((score, item.rel.casefold(), item, match, field_name))

        ranked.sort(key=lambda row: (-row[0], row[1]))

        results: list[SearchResult] = []
        for score, _rel, item, match, field_name in ranked[:limit]:
            if field_name == "name":
                subtitle = item.directory
                subtitle_spans: tuple[int, ...] = ()
                title_spans = match.positions
            else:
                subtitle = item.rel
                subtitle_spans = match.positions
                title_spans = ()
            results.append(
                SearchResult(
                    title=item.name,
                    subtitle=subtitle,
                    payload=("file", item.path),
                    score=score,
                    kind="file",
                    group="Project files",
                    title_spans=title_spans,
                    subtitle_spans=subtitle_spans,
                )
            )
        if len(ranked) > limit:
            results.append(
                info(
                    f"{len(ranked) - limit} more files",
                    "Refine the query to narrow the results.",
                )
            )
        return results

    def _recent_or_project(
        self, context: SearchContext, *, limit: int
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen: set[Path] = set()
        for raw in context.recent_files:
            try:
                path = Path(raw).resolve()
            except OSError:
                continue
            item = self.index.get(path)
            if item is None or item.path in seen:
                continue
            seen.add(item.path)
            results.append(
                SearchResult(
                    title=item.name,
                    subtitle=item.directory,
                    payload=("file", item.path),
                    kind="file",
                    group="Recent files",
                )
            )
            if len(results) >= 10:
                break

        if results:
            return results

        # No history yet: show the first files so the popup is not empty.
        for item in self.index.files[:limit]:
            results.append(
                SearchResult(
                    title=item.name,
                    subtitle=item.directory,
                    payload=("file", item.path),
                    kind="file",
                    group="Project files",
                )
            )
        return results


class CommandsProvider:
    """Fuzzy-filter a list of application commands."""

    id = "commands"

    def __init__(self, commands: list["SearchCommand"]) -> None:
        self.commands = commands

    def search(
        self, text: str, context: SearchContext, *, limit: int = 30
    ) -> list[SearchResult]:
        query = text.strip()
        ranked: list[tuple[float, str, SearchCommand]] = []
        for command in self.commands:
            if not query:
                ranked.append((0.0, command.title.casefold(), command))
                continue
            title_match = fuzzy_match(query, command.title)
            hint_match = fuzzy_match(query, command.hint)
            match = title_match or hint_match
            if match is None:
                continue
            score = match.score + (5.0 if title_match is not None else 0.0)
            ranked.append((score, command.title.casefold(), command))

        ranked.sort(key=lambda row: (-row[0], row[1]))
        results: list[SearchResult] = []
        for _score, _title, command in ranked[:limit]:
            subtitle = command.hint
            if command.shortcut:
                subtitle = f"{subtitle}  ·  {command.shortcut}".strip()
            results.append(
                SearchResult(
                    title=command.title,
                    subtitle=subtitle,
                    payload=("command", command),
                    kind="command",
                    group="Commands",
                )
            )
        return results


@dataclass(frozen=True)
class SearchCommand:
    title: str
    hint: str = ""
    shortcut: str = ""
    run: Callable[[], None] | None = None


class SymbolsProvider:
    """Identifiers in the active document (``@``)."""

    id = "symbols"

    def search(
        self, text: str, context: SearchContext, *, limit: int = MAX_SYMBOL_RESULTS
    ) -> list[SearchResult]:
        widget = context.active_widget
        if widget is None:
            return []
        scene = getattr(widget, "scene", None)
        if scene is not None and hasattr(scene, "nodes"):
            return self._graph_symbols(widget, text, limit=limit)
        if hasattr(widget, "toPlainText"):
            return self._text_symbols(widget, text, limit=limit)
        return []

    def _text_symbols(
        self, editor, text: str, *, limit: int
    ) -> list[SearchResult]:
        query = text.strip()
        seen: set[str] = set()
        rows: list[tuple[float, int, str, int]] = []
        content = editor.toPlainText()
        for match in IDENTIFIER_RE.finditer(content):
            identifier = match.group(0)
            if identifier in seen:
                continue
            seen.add(identifier)
            if query:
                fuzzy = fuzzy_match(query, identifier)
                if fuzzy is None:
                    continue
                score = fuzzy.score
                spans = fuzzy.positions
            else:
                score = 0.0
                spans = ()
            rows.append((score, match.start(), identifier, spans))

        rows.sort(key=lambda row: (-row[0], row[1], row[2].casefold()))
        results: list[SearchResult] = []
        for _score, start, identifier, spans in rows[:limit]:
            line = content.count("\n", 0, start) + 1
            results.append(
                SearchResult(
                    title=identifier,
                    subtitle=f"Line {line}",
                    payload=("text_range", start, len(identifier)),
                    kind="symbol",
                    group="Symbols in file",
                    title_spans=spans,
                )
            )
        return results

    def _graph_symbols(
        self, editor, text: str, *, limit: int
    ) -> list[SearchResult]:
        from src.gui.search.graph_search import score_node

        query = text.strip()
        rows: list[tuple[float, float, float, str, object]] = []
        for node in editor.scene.nodes.values():
            if query:
                score = score_node(node, query)
                if score <= 0:
                    continue
            else:
                score = 0.0
            position = node.scenePos()
            rows.append(
                (
                    -score,
                    position.y(),
                    position.x(),
                    node.identifier.casefold(),
                    node,
                )
            )
        rows.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
        return [
            SearchResult(
                title=node.identifier,
                subtitle=node.gwf_type,
                payload=("node", editor, node),
                kind="node",
                group="Nodes in graph",
            )
            for *_rest, node in rows[:limit]
        ]


def text_results(
    matches: list[TextMatch], query: str, *, limit: int = MAX_RESULTS
) -> list[SearchResult]:
    """Group raw content matches into header + row results."""
    ordered = rank_text_matches(matches, query, limit=limit)
    results: list[SearchResult] = []
    current_group = ""
    for match in ordered:
        group = match.rel
        if group != current_group:
            results.append(header(group))
            current_group = group
        snippet, span = make_snippet(
            match.line_text, match.column, match.length
        )
        results.append(
            SearchResult(
                title=f"{match.path.name}:{match.line}",
                subtitle="",
                detail=snippet,
                detail_spans=span,
                payload=(
                    "text",
                    match.path,
                    match.line,
                    match.column,
                    match.length,
                ),
                kind="text",
                group=group,
            )
        )
    remaining = len(matches) - len(ordered)
    if remaining > 0:
        results.append(info(f"{remaining} more matches", "Refine the query to narrow the results."))
    return results
