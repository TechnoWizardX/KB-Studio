"""Unified project search: quick open, text search and graph node search.

The package is split into small, testable pieces:

- :mod:`query` parses the prefix grammar (``%``, ``#``, ``@``, ``>``);
- :mod:`file_index` keeps an in-memory list of project files;
- :mod:`fuzzy` ranks fuzzy file-name matches;
- :mod:`text_search` scans file contents in a worker thread;
- :mod:`graph_search` searches SCg nodes and node classes;
- :mod:`providers` turns the raw engines into ordered result rows;
- :mod:`quick_search` is the toolbar field plus its result popup;
- :mod:`find_bar` is the in-editor ``Ctrl+F`` / ``Ctrl+H`` panel.
"""

from src.gui.search.file_index import FileIndex, IndexedFile
from src.gui.search.query import ParsedQuery, parse_query
from src.gui.search.providers import SearchContext, SearchResult

__all__ = [
    "FileIndex",
    "IndexedFile",
    "ParsedQuery",
    "SearchContext",
    "SearchResult",
    "parse_query",
]
