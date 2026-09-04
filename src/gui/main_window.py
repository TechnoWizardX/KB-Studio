from PySide6.QtWidgets import QApplication, QWidget, QMainWindow, QHBoxLayout, QVBoxLayout, QFrame, QSplitter
from PySide6.QtCore import QStandardPaths 
import sys
from pathlib import Path
from src.utils.config_manager import ConfigManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KB Studio")

        self.main_frame = QFrame()
        self.setCentralWidget(self.main_frame)

        self.main_layout = QHBoxLayout(self.main_frame)




def init_app():
    app = QApplication(sys.argv)
    app.setApplicationName("KB Studio")
    app.setOrganizationName("OSTIS")

    ConfigManager.init_config()
    window = MainWindow()
    window.show()

    sys.exit(app.exec())