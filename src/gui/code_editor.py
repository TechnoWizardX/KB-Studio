from PySide6.QtWidgets import QVBoxLayout, QFrame, QPlainTextEdit, QSplitter, QWidget, QLineEdit
from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QColor, QPainter, QKeySequence, QShortcut
import sys
from pathlib import Path
class CodeEditorWidget(QFrame):
    def __init__(self, parent : QWidget = None):
        super().__init__(parent=parent)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.splitter = QSplitter(Qt.Vertical)
        self.main_layout.addWidget(self.splitter)

        self.code_editor = CodeEditor()
        self.splitter.addWidget(self.code_editor)

        self.terminal = Terminal()
        self.splitter.addWidget(self.terminal)

        self.splitter.setSizes([700, 300])

    def apply_file(self, file_path : str | Path):
        self.code_editor.apply_file(file_path)
    

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setViewportMargins(30, 0, 0, 0)

        self.line_number_area = LineNumberArea(self)

        self.shorcut_zoom_in = QShortcut(QKeySequence("Ctrl++"), self)
        self.shorcut_zoom_in.activated.connect(self.zoom_in)

        self.shorcut_zoom_in = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shorcut_zoom_in.activated.connect(self.zoom_out)

    def zoom_in(self, range : int = 2):
        self.zoomIn(range)

    def zoom_out(self, range : int = 2):
        self.zoomOut(range)
    
    def apply_file(self, file_path : str | Path):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
            self.setPlainText(text)
            print(f"Inserted next file: {text}")

    def test_syntax(self, parser):
        text = self.toPlainText

class LineNumberArea(QWidget):
    def __init__(self, editor : CodeEditor):
            super().__init__(editor)
            self.editor = editor
            self.setObjectName("lineNumberArea")
            
    def getFirstVisibleBlock(self) -> int:
        return self.editor.firstVisibleBlock().blockNumber() + 1
    
    
    
    def paintEvent(self, event):
        pass
class Terminal(QFrame):

    def __init__(self):
        super().__init__()
        self.setObjectName("terminal")

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите команду...")

        layout = QVBoxLayout(self)
        layout.addWidget(self.output)
        layout.addWidget(self.input)
        layout.setContentsMargins(0, 0, 0, 0)

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._on_output)
        self.process.readyReadStandardError.connect(self._on_error)

        shell = "powershell.exe" if sys.platform == "win32" else "bash"
        self.process.start(shell)

        self.input.returnPressed.connect(self._execute)

    def _execute(self):
        cmd = self.input.text().strip()
        if not cmd:
            return
        self.output.appendPlainText(f"$ {cmd}")
        self.process.write(cmd.encode() + b"\n")
        self.input.clear()

    def _on_output(self):
        text = self.process.readAllStandardOutput().data().decode(errors="replace")
        self.output.insertPlainText(text)
        self.output.ensureCursorVisible()

    def _on_error(self):
        text = self.process.readAllStandardError().data().decode(errors="replace")
        self.output.insertPlainText(text)
        self.output.ensureCursorVisible()

