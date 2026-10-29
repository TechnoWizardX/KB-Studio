"""SCg canvas palette resolved from the active application theme.

Regular widgets restyle through the global QSS, but the canvas paints
itself: this module resolves the graph vocabulary (node interior, glyph
side colours, markers...) per ThemeManager theme. The dark table keeps
the historical canvas values, the light table adjusts them for a bright
canvas; ``canvas_bg`` follows the theme's ``bg_alt`` token when present.
"""
from __future__ import annotations

from PySide6.QtGui import QColor

from src.core.signals import signals
from src.utils.theme_manager import ThemeManager

_DARK = {
    "canvas_bg": "#1e1e1e",
    "node_fill": "#2b313a",
    "selection_fg": "#ffa657",
    "node_meta": "#d2a8ff",
    "node_var": "#79c0ff",
    "node_const": "#e6e6e6",
    "node_undefined": "#d4d4d4",
    "label_fg": "#d4d4d4",
    "content_fg": "#c9d1d9",
    "content_marker": "#cc66ff",
    "edge_fg": "#c9d1d9",
    "edge_token_fg": "#d4d4d4",
    "waypoint_fill": "#ffffff",
    "bus_fg": "#c9d1d9",
    "contour_fg": "#8b949e",
    "preview_fg": "#00ffff",
    "preview_snapping": "#44dd66",
}

_LIGHT = {
    "canvas_bg": "#f3f3f3",
    "node_fill": "#ffffff",
    "selection_fg": "#b85c00",
    "node_meta": "#7a2fbf",
    "node_var": "#0b64c8",
    "node_const": "#3c3f44",
    "node_undefined": "#9a9a9a",
    "label_fg": "#1e1e1e",
    "content_fg": "#1e1e1e",
    "content_marker": "#a040d0",
    "edge_fg": "#333333",
    "edge_token_fg": "#333333",
    "waypoint_fill": "#ffffff",
    "bus_fg": "#333333",
    "contour_fg": "#6a6a6a",
    "preview_fg": "#007acc",
    "preview_snapping": "#16825d",
}

_tables = {"dark": _DARK, "light": _LIGHT}
_tokens = {"canvas_bg": "bg_alt"}
_cache: dict[str, QColor] = {}


def theme_name() -> str:
    return "light" if ThemeManager.last_used_theme == "light" else "dark"


def color(key: str) -> QColor:
    """Colour of a graph palette slot for the current theme (cached until
    the next theme change)."""
    resolved = _cache.get(key)
    if resolved is None:
        token = _tokens.get(key)
        value = (
            ThemeManager.colors.get(token) if token and ThemeManager.colors else None
        )
        if not value:
            value = _tables[theme_name()][key]
        resolved = QColor(value)
        _cache[key] = resolved
    return resolved


def reset_cache() -> None:
    _cache.clear()


signals.theme_changed.connect(lambda _theme: reset_cache())
