"""Shared status bar shown at the bottom of the main window.

The bar only displays state. Document state is pushed by
:class:`~src.gui.editor_workspace.EditorWorkspace`, transient notifications
arrive through ``signals.status_message``.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QStatusBar


class ElidedLabel(QLabel):
    """A label that shortens its text instead of widening the window."""

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


class AppStatusBar(QStatusBar):
    """Status bar for the whole window: document, cursor, save and zoom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("appStatusBar")
        # Keep the bar flat and VS Code-like: the window is still resizable
        # from its edges, so the grip is only visual noise here.
        self.setSizeGripEnabled(False)

        self.path_label = ElidedLabel("No file open")
        self.path_label.setObjectName("statusPath")
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.addWidget(self.path_label, 1)

        self.kind_label = self._make_label("statusKind")
        self.addPermanentWidget(self.kind_label)

        self.cursor_label = self._make_label("statusCursor")
        self.cursor_label.setMinimumWidth(110)
        self.cursor_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.addPermanentWidget(self.cursor_label)

        self.zoom_label = self._make_label("statusZoom")
        self.zoom_label.setMinimumWidth(52)
        self.zoom_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.addPermanentWidget(self.zoom_label)

        self.problems_label = self._make_label("statusProblems")
        self.addPermanentWidget(self.problems_label)

        self.save_label = self._make_label("statusSave")
        self.addPermanentWidget(self.save_label)

        self.set_document("", "")

    @staticmethod
    def _make_label(object_name: str) -> QLabel:
        label = QLabel("")
        label.setObjectName(object_name)
        return label

    # ------------------------------------------------------------------
    # Document state
    # ------------------------------------------------------------------
    def set_document(self, path: str, kind: str) -> None:
        """Show the active document path and the editor kind."""
        self.path_label.setText(path or "No file open")
        self.kind_label.setText({"scs": "SCS", "gwf": "SCg"}.get(kind, ""))
        self.kind_label.setVisible(bool(kind))
        self.cursor_label.setVisible(kind == "scs")
        self.zoom_label.setVisible(kind == "gwf")
        self.save_label.setVisible(bool(kind))
        if kind != "scs":
            self.cursor_label.clear()
        if kind != "gwf":
            self.zoom_label.clear()
        if not kind:
            self.set_save_state(False)
            self.set_problems(False)

    def set_cursor(self, line: int, column: int) -> None:
        """Show the 1-based cursor position of the active text editor."""
        self.cursor_label.setText(f"Ln {line}, Col {column}")

    def set_save_state(self, modified: bool) -> None:
        """Show whether the active document has unsaved changes."""
        self.save_label.setText("Unsaved" if modified else "Saved")
        self.save_label.setToolTip(
            "The active document has unsaved changes"
            if modified
            else "The active document is saved"
        )
        if bool(self.save_label.property("modified")) != modified:
            self.save_label.setProperty("modified", modified)
            self._repolish(self.save_label)

    def set_problems(self, has_problems: bool) -> None:
        """Show a syntax problem indicator for the active text editor."""
        self.problems_label.setText("1 problem" if has_problems else "")
        self.problems_label.setToolTip(
            "The active file has a syntax problem" if has_problems else ""
        )
        self.problems_label.setVisible(has_problems)

    def set_zoom(self, percent: int) -> None:
        """Show the graph zoom level in percent (hidden for text files)."""
        self.zoom_label.setText(f"{percent}%" if percent > 0 else "")

    # ------------------------------------------------------------------
    # Transient messages
    # ------------------------------------------------------------------
    def flash(self, message: str, timeout: int = 2000) -> None:
        """Show a temporary message without hiding the permanent sections."""
        if message:
            self.showMessage(message, timeout)

    @staticmethod
    def _repolish(widget: QLabel) -> None:
        """Apply a changed dynamic property to the widget's stylesheet."""
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
