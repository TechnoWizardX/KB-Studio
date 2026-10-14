from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout, QMessageBox, QHBoxLayout
from PySide6.QtCore import Qt
import sys

from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import ThemeManager

from src.gui.directory_view import DirectoryTreeViewWidget
from src.gui.code_editor_widget import CodeEditorWidget
from src.gui.ai_chat import ChatBot
from src.gui.settings import Settings

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

        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.settings = Settings(self)
        self.settings_button = self.settings.call_button
        self.settings_button.clicked.connect(self.settings.exec)

        self.top_bar_layout.addWidget(self.settings_button)
        self.top_bar_layout.addStretch()

        self.main_layout.addLayout(self.top_bar_layout)

        self.last_project = ConfigManager.get("project_dir")
        self.dir_view = DirectoryTreeViewWidget(root_path=self.last_project)
        self.code_editor = CodeEditorWidget()
        self.chat_bot = ChatBot()

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(5)
        self.main_layout.addWidget(self.main_splitter)
        
        self.main_splitter.addWidget(self.dir_view)
        self.main_splitter.addWidget(self.code_editor)
        self.main_splitter.addWidget(self.chat_bot)
        self.main_splitter.setSizes([300, 500, 200])

        signals.error_occured.connect(self.show_error)

    def show_error(self, error):
        QMessageBox.critical(self, "ERROR", error)

    def closeEvent(self, event):
        super().closeEvent(event)
        ConfigManager.set("selected_dir", "")
        ConfigManager.set("selected_file", "")

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