"""Prefix grammar for the unified search field.

The field behaves like the VS Code command centre: the first character picks
a search provider, and everything after it is the query.

================  ====================================================
Prefix            Mode
================  ====================================================
(none)            Project files by name
``%``             Text in all project files; in an active SCg graph it
                  searches graph nodes instead
``#``             SCg nodes filtered by class (``#var``, ``#nrel``, ...)
``@``             Symbols in the active document
``>``             Application commands
================  ====================================================

Keeping the grammar in one module means adding a new mode is a one-line
change here plus a provider registration; the UI never parses prefixes
itself.
"""

from __future__ import annotations

from dataclasses import dataclass

MODE_FILES = "files"
MODE_TEXT = "text"
MODE_GRAPH = "graph"
MODE_NODE_CLASS = "node_class"
MODE_SYMBOLS = "symbols"
MODE_COMMANDS = "commands"

PREFIX_FILES = ""
PREFIX_TEXT = "%"
PREFIX_NODE_CLASS = "#"
PREFIX_SYMBOLS = "@"
PREFIX_COMMANDS = ">"

PREFIXES = (
    PREFIX_TEXT,
    PREFIX_NODE_CLASS,
    PREFIX_SYMBOLS,
    PREFIX_COMMANDS,
)


@dataclass(frozen=True)
class ParsedQuery:
    """A raw field value split into a mode and a search term."""

    mode: str
    text: str
    prefix: str = ""
    has_prefix: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.text

    @property
    def is_mode_only(self) -> bool:
        """True when the user typed just a prefix (``%``, ``#``...)."""
        return self.has_prefix and not self.text


def parse_query(raw: str, active_kind: str = "") -> ParsedQuery:
    """Split *raw* into a provider mode and a search term.

    ``%`` is context sensitive: on an SCg tab it searches the graph, on an
    SCs tab (or with no tab open) it searches project file contents.
    """
    if raw.startswith(PREFIX_TEXT):
        mode = MODE_GRAPH if active_kind == "gwf" else MODE_TEXT
        return ParsedQuery(mode, raw[1:].strip(), PREFIX_TEXT, True)
    if raw.startswith(PREFIX_NODE_CLASS):
        return ParsedQuery(
            MODE_NODE_CLASS, raw[1:].strip(), PREFIX_NODE_CLASS, True
        )
    if raw.startswith(PREFIX_SYMBOLS):
        return ParsedQuery(
            MODE_SYMBOLS, raw[1:].strip(), PREFIX_SYMBOLS, True
        )
    if raw.startswith(PREFIX_COMMANDS):
        return ParsedQuery(
            MODE_COMMANDS, raw[1:].strip(), PREFIX_COMMANDS, True
        )
    return ParsedQuery(MODE_FILES, raw.strip())


def mode_for_prefix(prefix: str, active_kind: str = "") -> str:
    """Return the provider mode a prefix selects in the current context."""
    return parse_query(prefix, active_kind).mode
