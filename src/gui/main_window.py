from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout
from PySide6.QtCore import Qt
import sys
from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import ThemeManager
from src.gui.directory_view import DirectoryTreeViewWidget
from src.gui.code_editor import CodeEditorWidget


class MainWindow(QMainWindow):
    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager
        self.setWindowTitle("KB Studio")

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)

        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)

        self.dir_view = DirectoryTreeViewWidget()
        self.code_editor = CodeEditorWidget()

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.main_splitter)
        
        self.main_splitter.addWidget(self.dir_view)
        self.main_splitter.addWidget(self.code_editor)
        self.main_splitter.setSizes([300, 700])

    def apply_file_test(self, file_path):
        self.code_editor.apply_file(file_path)


def init_app():
    app = QApplication(sys.argv)
    app.setApplicationName("KB Studio")
    app.setOrganizationName("OSTIS")

    ConfigManager.init_config()

    theme_manager = ThemeManager(app)
    theme_manager.apply(ConfigManager.get("theme"))

    window = MainWindow(theme_manager)
    window.show()

    window.apply_file_test("./test.scs")
    sys.exit(app.exec())