from PySide6.QtWidgets import QApplication, QMainWindow
import sys
from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import ThemeManager


class MainWindow(QMainWindow):
    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.theme_manager = theme_manager
        self.setWindowTitle("KB Studio")


def init_app():
    app = QApplication(sys.argv)
    app.setApplicationName("KB Studio")
    app.setOrganizationName("OSTIS")

    ConfigManager.init_config()

    theme_manager = ThemeManager(app)
    theme_manager.apply(ConfigManager.get("theme"))

    window = MainWindow(theme_manager)
    window.show()

    sys.exit(app.exec())
