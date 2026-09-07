from PySide6.QtWidgets import QVBoxLayout, QFrame, QPlainTextEdit, QSplitter, QWidget
from PySide6.QtGui import QColor, QPainter
from PySide6.QtCore import QRect, Qt


class CodeEditorWidget(QFrame):
    def __init__(self, parent : QWidget = None):
        super().__init__(parent=parent)

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.code_editor = CodeEditor()
        self.setLayout(self.main_layout)
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.code_editor)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()

class Terminal():
    pass