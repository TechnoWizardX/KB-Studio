from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.signals import signals
from src.gui.code_editor import CodeEditor, DevPanelWidget
from src.gui.graph_editor import GraphEditorWidget
from src.resources.icons import Icons
from src.utils.config_manager import ConfigManager
from src.utils.security import get_project_root, safe_path


class EditorWorkspace(QFrame):
    """One tab bar for every open document.

    Text documents open in :class:`CodeEditor`, graphs in
    :class:`GraphEditorWidget`. The active tab decides which editor the user
    sees, so files no longer need to be routed through a separate editor
    switcher.
    """

    kind_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent=parent)
        self.setObjectName("editorWorkspace")
        self._dev_panel_height = 300
        self._dev_panel_visible = bool(ConfigManager.get("show_bottom_bar"))
        self._restoring = True
        self._dev_panel_sizes_applied = False

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.main_layout.addWidget(self.splitter)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("documentTabs")
        self.tabs.setTabsClosable(False)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        tab_bar = self.tabs.tabBar()
        tab_bar.setExpanding(False)
        tab_bar.setUsesScrollButtons(True)
        tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        tab_bar.setDrawBase(False)
        self.splitter.addWidget(self.tabs)

        self.dev_panel_widget = DevPanelWidget()
        self.splitter.addWidget(self.dev_panel_widget)
        self.splitter.setSizes([700, self._dev_panel_height])

        self.tabs.currentChanged.connect(self._on_current_changed)
        signals.theme_changed.connect(self._refresh_close_icons)
        signals.show_bottom_bar.connect(self.set_dev_panel_visible)
        signals.selected_new_project_folder.connect(self.clear_workspace)

        self._restore_session()
        self._restoring = False
        self._on_current_changed(self.tabs.currentIndex())

    # ------------------------------------------------------------------
    # Opening documents
    # ------------------------------------------------------------------
    def apply_file(self, file_path: str | Path, activate: bool = True):
        """Open *file_path* in the editor that matches its extension."""
        if not file_path:
            return None
        try:
            safe_file = safe_path(get_project_root(), str(file_path))
            if not safe_file.is_file():
                raise FileNotFoundError(f"Not a file: {safe_file}")
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot open file", str(error))
            return None

        existing_index = self._index_of_path(safe_file)
        if existing_index >= 0:
            if activate:
                self.tabs.setCurrentIndex(existing_index)
            return self.tabs.widget(existing_index)

        if safe_file.suffix.lower() == ".gwf":
            editor = GraphEditorWidget()
            editor.apply_file(safe_file)
            if editor.file_path is None:
                editor.deleteLater()
                return None
            self._add_graph_tab(editor)
        else:
            try:
                editor = CodeEditor(safe_file)
            except (OSError, UnicodeError, ValueError) as error:
                QMessageBox.warning(
                    self, "Cannot open file", f"{safe_file}\n\n{error}"
                )
                return None
            self._add_code_tab(editor)

        if activate:
            self.tabs.setCurrentWidget(editor)
        self._persist_open_tabs()
        return editor

    def new_graph(self) -> GraphEditorWidget:
        """Open an empty graph in a new tab."""
        editor = GraphEditorWidget()
        editor.new_graph()
        self._add_graph_tab(editor)
        self.tabs.setCurrentWidget(editor)
        self._persist_open_tabs()
        return editor

    # ------------------------------------------------------------------
    # Tab bookkeeping
    # ------------------------------------------------------------------
    def _add_code_tab(self, editor: CodeEditor) -> None:
        safe_file = editor.abs_path
        index = self.tabs.addTab(editor, safe_file.name if safe_file else "Untitled")
        if safe_file is not None:
            self.tabs.setTabToolTip(index, str(safe_file))
        editor.syntax_status_changed.connect(
            lambda error, current_editor=editor: self._on_code_diagnostics(
                current_editor, error
            )
        )
        editor.document().modificationChanged.connect(
            lambda modified, current_editor=editor: self._update_code_title(
                current_editor, modified
            )
        )
        self._set_close_button(index, editor)

    def _add_graph_tab(self, editor: GraphEditorWidget) -> None:
        index = self.tabs.addTab(editor, self._graph_tab_title(editor))
        self.tabs.setTabToolTip(index, self._graph_tooltip(editor))
        editor.modified_changed.connect(
            lambda modified, current_editor=editor: self._update_graph_title(
                current_editor, modified
            )
        )
        editor.file_changed.connect(
            lambda _path, current_editor=editor: self._on_graph_file_changed(
                current_editor
            )
        )
        editor.new_graph_requested.connect(self.new_graph)
        self._set_close_button(index, editor)

    def _set_close_button(self, index: int, widget: QWidget) -> None:
        close_button = QPushButton()
        close_button.setObjectName("editorTabCloseButton")
        close_button.setIcon(Icons.cross())
        close_button.setIconSize(QSize(12, 12))
        close_button.setFixedSize(16, 16)
        close_button.setToolTip("Close tab")
        close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_button.clicked.connect(lambda *_: self._close_widget(widget))
        self.tabs.tabBar().setTabButton(
            index, self.tabs.tabBar().ButtonPosition.RightSide, close_button
        )

    def _refresh_close_icons(self, _theme: str = "") -> None:
        for index in range(self.tabs.count()):
            self._set_close_button(index, self.tabs.widget(index))

    def _close_widget(self, widget: QWidget) -> None:
        index = self.tabs.indexOf(widget)
        if index >= 0:
            self.close_tab(index)

    def close_tab(self, index: int) -> bool:
        widget = self.tabs.widget(index)
        if widget is None or not self._confirm_close(widget):
            return False
        self._remove_tab(index)
        self._persist_open_tabs()
        return True

    def confirm_close_all(self) -> bool:
        """Ask about every modified document, without closing anything yet."""
        for index in range(self.tabs.count()):
            if not self._confirm_close(self.tabs.widget(index)):
                return False
        return True

    def _confirm_close(self, widget: QWidget) -> bool:
        if isinstance(widget, GraphEditorWidget):
            return widget.confirm_close()
        if not isinstance(widget, CodeEditor):
            return True
        if not widget.document().isModified():
            return True
        name = Path(widget.abs_path).name if widget.abs_path else "Untitled"
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            f"Save changes to '{name}' before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return widget.save_changes()
        return True

    def _remove_tab(self, index: int) -> None:
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        self._dispose(widget)

    def _dispose(self, widget: QWidget | None) -> None:
        if isinstance(widget, CodeEditor):
            widget.parse_timer.stop()
            widget.save_timer.stop()
        if isinstance(widget, GraphEditorWidget):
            widget.save_timer.stop()
        if widget is not None:
            widget.deleteLater()

    def clear_workspace(self, _new_dir: str | None = None) -> None:
        if not self.confirm_close_all():
            return
        self._restoring = True
        try:
            while self.tabs.count():
                self._remove_tab(0)
        finally:
            self._restoring = False
        ConfigManager.set("last_viewed_file", "")
        ConfigManager.set("last_viewed_files", [])
        self._persist_open_tabs()
        self.kind_changed.emit("")

    # ------------------------------------------------------------------
    # Active document
    # ------------------------------------------------------------------
    def _on_current_changed(self, index: int) -> None:
        editor = self.tabs.widget(index)
        self.kind_changed.emit(self._kind_of(editor))
        self._apply_dev_panel_visibility()
        if isinstance(editor, CodeEditor):
            self.dev_panel_widget.problems_wgt.show_diagnostics(
                editor.syntax_error
            )
        if not self._restoring:
            self._persist_open_tabs()

    def current_kind(self) -> str:
        return self._kind_of(self.tabs.currentWidget())

    @staticmethod
    def _kind_of(widget: QWidget | None) -> str:
        if isinstance(widget, GraphEditorWidget):
            return "gwf"
        if isinstance(widget, CodeEditor):
            return "scs"
        return ""

    def _on_code_diagnostics(
        self, editor: CodeEditor, error: str | None
    ) -> None:
        if self.tabs.currentWidget() is editor:
            self.dev_panel_widget.problems_wgt.show_diagnostics(error)

    def _update_code_title(self, editor: CodeEditor, modified: bool) -> None:
        index = self.tabs.indexOf(editor)
        if index < 0:
            return
        name = Path(editor.abs_path).name if editor.abs_path else "Untitled"
        self.tabs.setTabText(index, f"{name} *" if modified else name)

    def _update_graph_title(
        self, editor: GraphEditorWidget, _modified: bool
    ) -> None:
        index = self.tabs.indexOf(editor)
        if index < 0:
            return
        self.tabs.setTabText(index, self._graph_tab_title(editor))

    def _on_graph_file_changed(self, editor: GraphEditorWidget) -> None:
        index = self.tabs.indexOf(editor)
        if index < 0:
            return
        self.tabs.setTabText(index, self._graph_tab_title(editor))
        self.tabs.setTabToolTip(index, self._graph_tooltip(editor))
        self._persist_open_tabs()

    def _graph_tab_title(self, editor: GraphEditorWidget) -> str:
        title = self._graph_title(editor)
        return f"{title} *" if editor.is_modified else title

    @staticmethod
    def _graph_title(editor: GraphEditorWidget) -> str:
        return editor.file_path.name if editor.file_path else "Untitled graph"

    @staticmethod
    def _graph_tooltip(editor: GraphEditorWidget) -> str:
        return str(editor.file_path) if editor.file_path else "Unsaved graph"

    def _index_of_path(self, file_path: Path) -> int:
        target = Path(file_path).resolve()
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            path = None
            if isinstance(widget, CodeEditor):
                path = widget.abs_path
            elif isinstance(widget, GraphEditorWidget):
                path = widget.file_path
            if path is not None and Path(path).resolve() == target:
                return index
        return -1

    # ------------------------------------------------------------------
    # Problems panel
    # ------------------------------------------------------------------
    def set_dev_panel_visible(self, visible: bool) -> None:
        """Remember the panel preference and apply it to the active tab."""
        self._dev_panel_visible = bool(visible)
        self._apply_dev_panel_visibility()

    def _apply_dev_panel_visibility(self) -> None:
        show = self._dev_panel_visible and isinstance(
            self.tabs.currentWidget(), CodeEditor
        )
        if show:
            if self.dev_panel_widget.isHidden():
                self.dev_panel_widget.show()
                self._resize_dev_panel()
            return

        if not self.dev_panel_widget.isHidden():
            sizes = self.splitter.sizes()
            if len(sizes) == 2 and sizes[1] > 0:
                self._dev_panel_height = sizes[1]
        self.dev_panel_widget.hide()

    def _resize_dev_panel(self) -> None:
        total = sum(self.splitter.sizes())
        if total <= 0:
            return
        height = min(self._dev_panel_height, max(1, total - 120))
        self.splitter.setSizes([max(1, total - height), height])

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

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------
    def _restore_session(self) -> None:
        paths = ConfigManager.get("last_viewed_files")
        if not isinstance(paths, list):
            paths = []
        last_viewed = ConfigManager.get("last_viewed_file")
        ordered = list(
            dict.fromkeys(
                [path for path in paths if isinstance(path, str)]
                + (
                    [last_viewed]
                    if isinstance(last_viewed, str) and last_viewed
                    else []
                )
            )
        )
        try:
            project_root = get_project_root()
        except ValueError:
            return
        for path in ordered:
            try:
                candidate = safe_path(project_root, path)
            except (OSError, ValueError):
                continue
            if not candidate.is_file():
                continue
            self.apply_file(candidate, activate=False)
        if isinstance(last_viewed, str) and last_viewed:
            try:
                last_path = safe_path(project_root, last_viewed)
            except (OSError, ValueError):
                return
            index = self._index_of_path(last_path)
            if index >= 0:
                self.tabs.setCurrentIndex(index)

    def _persist_open_tabs(self) -> None:
        if self._restoring:
            return
        open_files = []
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if isinstance(widget, CodeEditor) and widget.abs_path is not None:
                open_files.append(str(widget.abs_path))
            elif isinstance(widget, GraphEditorWidget) and widget.file_path is not None:
                open_files.append(str(widget.file_path))

        current = self.tabs.currentWidget()
        if isinstance(current, CodeEditor) and current.abs_path is not None:
            current_file = str(current.abs_path)
        elif isinstance(current, GraphEditorWidget) and current.file_path is not None:
            current_file = str(current.file_path)
        else:
            current_file = ""

        ConfigManager.set("selected_file", current_file)
        ConfigManager.set("last_viewed_files", open_files)
        ConfigManager.set("last_viewed_file", current_file)
