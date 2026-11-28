"""Reusable custom widgets shared across the application.

Keep small, presentation-only widgets here when they are (or are likely to
be) used in more than one place. Feature-specific widgets stay in their own
packages (``code_editor``, ``graph_editor``, ``left_sidebar``, ...).
"""

from src.gui.widgets.elided_label import ElidedLabel
from src.gui.widgets.icon_button import IconButton

__all__ = ["ElidedLabel", "IconButton"]
