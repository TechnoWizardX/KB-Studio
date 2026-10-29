from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
import sys
from pathlib import Path

from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import ThemeManager

from src.gui.code_editor_widget import CodeEditorWidget
from src.gui.graph_editor import GraphEditorWidget

from src.gui.left_sidebar_widget import LeftSidebarWidget
from src.gui.right_sidebar_widget import RightSidebarWidget

from src.gui.toolbar import ToolBar
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

        
        self.topbar = ToolBar(self._select_editor)
        self.main_layout.addWidget(self.topbar)

        self.editor_stack = QStackedWidget()
        self.code_editor = CodeEditorWidget()
        self.graph_editor = GraphEditorWidget()
        self.editor_stack.addWidget(self.code_editor)
        self.editor_stack.addWidget(self.graph_editor)
        self._select_editor(0)

        show_left_bar = ConfigManager.get("show_left_bar")
        show_right_bar = ConfigManager.get("show_right_bar")
        self.last_project = ConfigManager.get("project_dir")
        self.left_bar = LeftSidebarWidget(root_path=self.last_project, show = show_left_bar)
        self.right_bar = RightSidebarWidget(show = show_right_bar)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.main_splitter.setHandleWidth(5)
        self.main_layout.addWidget(self.main_splitter)

        self.main_splitter.addWidget(self.left_bar)
        self.main_splitter.addWidget(self.editor_stack)
        self.main_splitter.addWidget(self.right_bar)
        self.main_splitter.setSizes([200, 500, 200])

        signals.error_occured.connect(self.show_error)
        signals.selected_new_file.connect(self._on_file_selected)

    def _on_file_selected(self, file_path: str) -> None:
        if Path(str(file_path)).suffix.lower() == ".gwf":
            self.topbar.editor_selector.setCurrentIndex(1)

    def _select_editor(self, index: int) -> None:
        self.editor_stack.setCurrentIndex(index)
        self.code_editor.set_active(index == 0)
        self.graph_editor.set_active(index == 1)

    def show_error(self, error):
        QMessageBox.critical(self, "ERROR", error)

    def closeEvent(self, event):
        if not self.right_bar.panel.shutdown():
            QMessageBox.warning(
                self,
                "AI request is still running",
                "Wait for the current AI request to finish, then close the application.",
            )
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
    # window.code_editor.code_editor.test_parse()
    sys.exit(app.exec())