"""Registry of search modes shown in the empty popup and in hints.

This is the extension point users are most likely to touch. To add a mode:

1. add a :class:`SearchOption` here;
2. register its provider in ``QuickSearchController.register``;
3. teach ``query.parse_query`` about the prefix.

Everything else (suggestions, placeholder text, keyboard activation) is
driven by this tuple.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.gui.search.providers import SearchContext


def _always(_context: SearchContext) -> bool:
    return True


def _graph_only(context: SearchContext) -> bool:
    return context.active_kind == "gwf"


@dataclass(frozen=True)
class SearchOption:
    prefix: str
    title: str
    hint: str
    placeholder: str
    enabled: Callable[[SearchContext], bool] = _always
    graph_title: str = ""
    graph_hint: str = ""

    def title_for(self, context: SearchContext) -> str:
        if context.active_kind == "gwf" and self.graph_title:
            return self.graph_title
        return self.title

    def hint_for(self, context: SearchContext) -> str:
        if context.active_kind == "gwf" and self.graph_hint:
            return self.graph_hint
        return self.hint


SEARCH_OPTIONS: tuple[SearchOption, ...] = (
    SearchOption(
        prefix="%",
        title="Text in project files",
        hint="Search the contents of every text file",
        placeholder="Search text in files…",
        graph_title="Nodes in this graph",
        graph_hint="Search node names, labels and content",
    ),
    SearchOption(
        prefix="#",
        title="Node class",
        hint="Filter SCg nodes by class: #var, #nrel, #rrel, #prefix:…",
        placeholder="Filter nodes: var, nrel, concept…",
        enabled=_graph_only,
    ),
    SearchOption(
        prefix="@",
        title="Symbols in the current file",
        hint="Jump to an identifier in the active editor",
        placeholder="Search symbols in the current file…",
    ),
    SearchOption(
        prefix=">",
        title="Commands",
        hint="Run an application command",
        placeholder="Run a command…",
    ),
)

OPTIONS_BY_PREFIX = {option.prefix: option for option in SEARCH_OPTIONS}


def options_for(context: SearchContext) -> list[SearchOption]:
    return [option for option in SEARCH_OPTIONS if option.enabled(context)]
