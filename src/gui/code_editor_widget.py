from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QSplitter, QVBoxLayout, QWidget

from src.gui.code_editor import CodeEditor, CodeEditorWorkspace, DevPanelWidget


class CodeEditorWidget(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("codeEditorWidget")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(5)
        self.main_layout.addWidget(self.splitter)

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
        self.splitter.setSizes([700, 300])

    def apply_file(self, file_path: str | Path) -> None:
        self.code_editor_workspace.apply_file(file_path)

    def set_active(self, active: bool) -> None:
        self.code_editor_workspace.set_active(active)

    def _show_current_editor_diagnostics(self, index: int) -> None:
        editor = self.code_editor_workspace.widget(index)
        error = editor.syntax_error if isinstance(editor, CodeEditor) else None
        self.dev_panel_widget.problems_wgt.show_diagnostics(error)

    def _show_editor_diagnostics(
        self, editor: CodeEditor, error: str | None
    ) -> None:
        if self.code_editor_workspace.currentWidget() is editor:
            self.dev_panel_widget.problems_wgt.show_diagnostics(error)
