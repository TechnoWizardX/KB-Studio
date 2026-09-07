from PySide6.QtWidgets import QVBoxLayout, QFrame, QPlainTextEdit, QSplitter, QWidget, QLineEdit
from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QColor, QPainter
import sys

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

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setViewportMargins(30, 0, 0, 0)

        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

    def update_line_number_area_width(self, new_count):
        digits = len(str(new_count))
        width = 30 + self.fontMetrics().horizontalAdvance('9') * digits
        self.setViewportMargins(width, 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.x(), self.line_number_area.width(), rect.height())

    def highlight_current_line(self):
        cursor = self.textCursor()
        block_number = cursor.blockNumber()
    def load_file(self):
        pass

class LineNumberArea(QWidget):
    def __init__(self, editor):
            super().__init__(editor)
            self.editor = editor
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))

        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.editor.blockBoundingGeometry(block).translated(
            self.editor.contentOffset()).top())
        bottom = top + int(self.editor.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#858585"))
                painter.drawText(0, top, self.width(),
                    self.editor.fontMetrics().height(),
                    Qt.AlignRight | Qt.AlignVCenter, number)
            block = block.next()
            block_number += 1
            top = bottom
            bottom = top + int(self.editor.blockBoundingRect(block).height())

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
