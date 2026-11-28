"""A label that shortens long text instead of widening its container."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    """A label that shortens its text instead of widening the window.

    The full text is always available through :meth:`full_text` and is shown
    in the tooltip, so elision never hides information from the user.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.setText(text)

    def full_text(self) -> str:
        """Return the text before elision (useful for tests and tooltips)."""
        return self._full_text

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        self._update_elided()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self) -> None:
        if self.width() <= 0:
            QLabel.setText(self, self._full_text)
            return
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideMiddle, self.width()
        )
        QLabel.setText(self, elided)
