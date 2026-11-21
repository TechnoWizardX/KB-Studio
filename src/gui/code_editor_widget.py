from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QSplitter, QVBoxLayout, QWidget

from src.core.signals import signals
from src.gui.code_editor import CodeEditor, CodeEditorWorkspace, DevPanelWidget
from src.utils.config_manager import ConfigManager


class CodeEditorWidget(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("codeEditorWidget")
        self._dev_panel_height = 300
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.main_layout.addWidget(self.splitter)
        self._dev_panel_sizes_applied = False

        self.code_editor_workspace = CodeEditorWorkspace()
        self.splitter.addWidget(self.code_editor_workspace)

        self.dev_panel_widget = DevPanelWidget()
        self.splitter.addWidget(self.dev_panel_widget)
        self.code_editor_workspace.currentChanged.connect(
            self._show_current_editor_diagnostics
        )
        self.code_editor_workspace.syntax_status_changed.connect(
            self._show_editor_diagnostics
        )
        self.splitter.setSizes([700, self._dev_panel_height])
        self.set_dev_panel_visible(bool(ConfigManager.get("show_bottom_bar")))
        signals.show_bottom_bar.connect(self.set_dev_panel_visible)

    def set_dev_panel_visible(self, visible: bool) -> None:
        """Collapse or restore the Problems panel below the editor."""
        if visible:
            self.dev_panel_widget.show()
            total = sum(self.splitter.sizes())
            if total <= 0:
                return
            height = min(self._dev_panel_height, max(1, total - 120))
            self.splitter.setSizes([max(1, total - height), height])
            return

        sizes = self.splitter.sizes()
        if len(sizes) == 2 and sizes[1] > 0:
            self._dev_panel_height = sizes[1]
        self.dev_panel_widget.hide()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._dev_panel_sizes_applied:
            return
        self._dev_panel_sizes_applied = True
        if not self.dev_panel_widget.isVisible():
            return
        total = max(self.splitter.height(), sum(self.splitter.sizes()))
        if total <= 0:
            return
        height = min(self._dev_panel_height, max(1, total - 120))
        self.splitter.setSizes([max(1, total - height), height])

    def apply_file(self, file_path: str | Path) -> None:
        self.code_editor_workspace.apply_file(file_path)

    def _show_current_editor_diagnostics(self, index: int) -> None:
        editor = self.code_editor_workspace.widget(index)
        error = editor.syntax_error if isinstance(editor, CodeEditor) else None
        self.dev_panel_widget.problems_wgt.show_diagnostics(error)

    def _show_editor_diagnostics(
        self, editor: CodeEditor, error: str | None
    ) -> None:
        if self.code_editor_workspace.currentWidget() is editor:
            self.dev_panel_widget.problems_wgt.show_diagnostics(error)
