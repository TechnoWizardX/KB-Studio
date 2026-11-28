from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
import sys

from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import ThemeManager

from src.gui.editor_workspace import EditorWorkspace

from src.gui.left_sidebar_widget import LeftSidebarWidget
from src.gui.right_sidebar_widget import RightSidebarWidget

from src.gui.toolbar import ToolBar
from src.gui.status_bar import AppStatusBar
from src.gui.search.providers import SearchCommand
from src.gui.search.quick_search import QuickSearchController
from src.core.signals import signals

class MainWindow(QMainWindow):
    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager
        self.setWindowTitle("KB Studio")

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        
        self.editor_workspace = EditorWorkspace()
        self.topbar = ToolBar(self.editor_workspace.new_graph)
        self.main_layout.addWidget(self.topbar)
        self.editor_workspace.kind_changed.connect(self.topbar.set_editor_mode)
        self.topbar.set_editor_mode(self.editor_workspace.current_kind())

        self.search_controller = QuickSearchController(
            self,
            self.topbar.search_field,
            self.editor_workspace,
            commands=self._search_commands(),
        )
        self._install_search_shortcuts()

        show_left_bar = ConfigManager.get("show_left_bar")
        show_right_bar = ConfigManager.get("show_right_bar")
        self.last_project = ConfigManager.get("project_dir")
        self.left_bar = LeftSidebarWidget(root_path=self.last_project, show = show_left_bar)
        self.right_bar = RightSidebarWidget(show = show_right_bar)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_layout.addWidget(self.main_splitter)

        self.main_splitter.addWidget(self.left_bar)
        self.main_splitter.addWidget(self.editor_workspace)
        self.main_splitter.addWidget(self.right_bar)
        self.main_splitter.setSizes([200, 500, 200])

        signals.error_occured.connect(self.show_error)
        signals.selected_new_file.connect(self._on_file_selected)

        self.status_bar = AppStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.editor_workspace.document_changed.connect(
            self.status_bar.set_document
        )
        self.editor_workspace.cursor_moved.connect(self.status_bar.set_cursor)
        self.editor_workspace.save_state_changed.connect(
            self.status_bar.set_save_state
        )
        self.editor_workspace.problems_changed.connect(
            self.status_bar.set_problems
        )
        self.editor_workspace.zoom_changed.connect(self.status_bar.set_zoom)
        signals.status_message.connect(self.status_bar.flash)
        self.editor_workspace.refresh_status()

    def _on_file_selected(self, file_path: str) -> None:
        """Open a file from the sidebar in the matching editor tab."""
        self.editor_workspace.apply_file(file_path)

    def _install_search_shortcuts(self) -> None:
        self.quick_open_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.quick_open_shortcut.activated.connect(
            self.search_controller.focus_files
        )
        self.search_text_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+F"), self
        )
        self.search_text_shortcut.activated.connect(
            self.search_controller.focus_text
        )
        self.search_commands_shortcut = QShortcut(
            QKeySequence("Ctrl+Shift+P"), self
        )
        self.search_commands_shortcut.activated.connect(
            self.search_controller.focus_commands
        )

    def _search_commands(self) -> list[SearchCommand]:
        return [
            SearchCommand(
                "New graph",
                "Open an empty SCg graph",
                "",
                self.editor_workspace.new_graph,
            ),
            SearchCommand(
                "Save active file",
                "Save the current document",
                "Ctrl+S",
                self._save_active,
            ),
            SearchCommand(
                "Close current tab",
                "Close the active editor tab",
                "Ctrl+W",
                self._close_current_tab,
            ),
            SearchCommand(
                "Toggle project panel",
                "Show or hide the file tree",
                "",
                self.topbar.left_show_btn.on_clicked,
            ),
            SearchCommand(
                "Toggle problems panel",
                "Show or hide the problems panel",
                "",
                self.topbar.bottom_show_btn.on_clicked,
            ),
            SearchCommand(
                "Toggle AI chat",
                "Show or hide the chat panel",
                "",
                self.topbar.right_show_btn.on_clicked,
            ),
            SearchCommand(
                "Open settings",
                "Change themes and editor options",
                "",
                self.topbar.settings.exec,
            ),
        ]

    def _save_active(self) -> None:
        editor = self.editor_workspace.tabs.currentWidget()
        if editor is None:
            return
        if hasattr(editor, "save_changes"):
            editor.save_changes()
        elif hasattr(editor, "save"):
            editor.save()

    def _close_current_tab(self) -> None:
        tabs = self.editor_workspace.tabs
        if tabs.count():
            self.editor_workspace.close_tab(tabs.currentIndex())

    def show_error(self, error):
        QMessageBox.critical(self, "Error", error)

    def closeEvent(self, event):
        if not self.right_bar.panel.shutdown():
            QMessageBox.warning(
                self,
                "AI request is still running",
                "Wait for the current AI request to finish, then close the application.",
            )
            event.ignore()
            return

        if not self.editor_workspace.confirm_close_all():
            event.ignore()
            return

        ConfigManager.set("selected_dir", "")
        ConfigManager.set("selected_file", "")
        super().closeEvent(event)

def init_app():
    app = QApplication(sys.argv)
    app.setApplicationName("KB Studio")
    app.setOrganizationName("OSTIS")

    ConfigManager.init_config()

    theme_manager = ThemeManager()
    theme = ConfigManager.get("theme")
    qss = theme_manager.build_qss(theme)
    app.setStyleSheet(qss)
    window = MainWindow(theme_manager)
    window.show()
    sys.exit(app.exec())
