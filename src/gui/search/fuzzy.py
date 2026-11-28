"""Backward-compatible imports for fuzzy search helpers.

New code should import from :mod:`src.utils.search.fuzzy`.
"""

from src.utils.search.fuzzy import FuzzyMatch, SEPARATORS, fuzzy_match, highlight_spans

__all__ = ["FuzzyMatch", "SEPARATORS", "fuzzy_match", "highlight_spans"]
