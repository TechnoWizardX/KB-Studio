"""Fuzzy subsequence matching used by quick open.

VS Code style: ``mw`` finds ``main_window.py``. A direct substring match is
always ranked above a scattered subsequence, and matches at a word or path
segment boundary get a bonus. The returned ``positions`` let the popup
highlight the matched characters.
"""

from __future__ import annotations

from dataclasses import dataclass

SEPARATORS = "/\\_-. "


@dataclass(frozen=True)
class FuzzyMatch:
    score: float
    positions: tuple[int, ...]


def fuzzy_match(query: str, candidate: str) -> FuzzyMatch | None:
    """Rank *candidate* against *query*, or return ``None`` if it cannot match."""
    q = query.casefold()
    c = candidate.casefold()
    if not q:
        return FuzzyMatch(0.0, ())
    if not c:
        return None

    # Fast path: the whole query is present as one run of characters.
    direct = c.find(q)
    if direct >= 0:
        score = 100.0
        if direct == 0:
            score += 50.0
        elif c[direct - 1] in SEPARATORS:
            score += 30.0
        score -= direct * 0.2
        score -= len(c) * 0.05
        return FuzzyMatch(score, tuple(range(direct, direct + len(q))))

    # Slow path: characters appear in order, possibly with gaps.
    positions: list[int] = []
    cursor = 0
    last = -2
    score = 0.0
    for char in q:
        found = c.find(char, cursor)
        if found < 0:
            return None
        positions.append(found)
        score += 10.0
        if found == last + 1:
            score += 8.0  # consecutive characters
        if found == 0 or c[found - 1] in SEPARATORS:
            score += 15.0  # start of a word or path segment
        last = found
        cursor = found + 1

    score -= (cursor - len(q)) * 0.5  # penalty for gaps
    score -= len(c) * 0.05  # prefer shorter candidates
    return FuzzyMatch(score, tuple(positions))


def highlight_spans(
    query: str, candidate: str
) -> tuple[int, ...]:
    """Convenience wrapper returning only the matched positions."""
    match = fuzzy_match(query, candidate)
    return match.positions if match is not None else ()
