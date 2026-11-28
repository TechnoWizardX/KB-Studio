"""A square, borderless push button with an icon."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget


class IconButton(QPushButton):
    """A compact icon-only button used in toolbars and sidebars.

    It centralises the repeated setup (object name, fixed square size, icon
    size and size policy) so the shared ``QPushButton#IconButton`` stylesheet
    applies consistently everywhere.
    """

    def __init__(
        self,
        icon: QIcon | None = None,
        tooltip: str = "",
        parent: QWidget | None = None,
        *,
        size: int = 30,
        icon_size: int = 24,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedSize(QSize(size, size))
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.setToolTip(tooltip)
        if icon is not None:
            self.setIcon(icon)
