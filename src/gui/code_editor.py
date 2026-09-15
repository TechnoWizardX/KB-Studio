from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QPlainTextEdit, QSplitter, QWidget, QLineEdit, QTextEdit, QStackedWidget
from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import QColor, QPainter, QKeySequence, QShortcut
import sys 
from pathlib import Path
from src.utils.theme_manager import ThemeManager
from src.core import signals
from src.lark_syntax.parser import SCSParser
from lark.exceptions import UnexpectedToken


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

class DevPanelWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.main_layout = QVBoxLayout(self)

        self.buttons_layout = QHBoxLayout(self)
        self.main_layout.addLayout(self.buttons_layout)

        self.problems_btn = QPushButton("Problems")
        self.problems_btn.setMaximumSize(80, 40)
        self.buttons_layout.addWidget(self.problems_btn)

        

        self.terminal_btn = QPushButton("Terminal")
        self.terminal_btn.setMaximumSize(80, 40)
        self.buttons_layout.addWidget(self.terminal_btn)

        self.stacked_widget = QStackedWidget()

        self.main_layout.addWidget(self.stacked_widget)

        self.buttons_layout.addStretch(1)

class ProblemsWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        signals.gaps_appeared.connect(self.appear_gaps)
        signals.gaps_resolved.connect(self.gaps_resolved)
    def appear_gaps(self, error):
        self.setText(error)
    def gaps_resolved(self):
        self.setText("There is no syntax issues")

    
class CodeEditor(QPlainTextEdit):
    parser = SCSParser()
    def __init__(self):
        super().__init__()
        self.setViewportMargins(20, 0, 0, 0)

        self.line_number_area = LineNumberArea(self)

        self.shorcut_zoom_in = QShortcut(QKeySequence("Ctrl++"), self)
        self.shorcut_zoom_in.activated.connect(self.zoom_in)

        self.shorcut_zoom_in = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shorcut_zoom_in.activated.connect(self.zoom_out)

        self.line_highlight = ThemeManager.get_color("line_highlight_color")

        self.blockCountChanged.connect(self.update_line_area_width)
        self.updateRequest.connect(self.update_line_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.init_parsing()

    def init_parsing(self):
        self.parse_timer = QTimer()

        self.parse_timer.setSingleShot(True)

        self.parse_timer.setInterval(1500)

        self.textChanged.connect(self.reset_parse_timer)
        self.parse_syntax()

    def reset_parse_timer(self):
        self.parse_timer.start()

    def line_number_area_width(self):
        digits = 1
        count = max(1, self.blockCount())
        while count >= 10:
            count /= 10
            digits += 1

        space = 20 + self.fontMetrics().horizontalAdvance('9')*digits
        return space
    
    def update_line_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_area_width()

    def highlight_current_line(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            
            line_color = QColor(self.line_highlight)
            selection.format.setBackground(line_color)
            selection.format.setProperty(0x06000, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def zoom_in(self, range : int = 2):
        self.zoomIn(range)
        self.line_number_area.setFont(self.font())
        self.update_line_area_width()

    def zoom_out(self, range : int = 2):
        self.zoomOut(range)
        self.line_number_area.setFont(self.font())
        self.update_line_area_width()
    
    def apply_file(self, file_path : str | Path):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
            self.setPlainText(text)
            print(f"Inserted next file: {text}")

    def parse_syntax(self):
        text = self.toPlainText()
        print(f"Parse {text} ...")
        if not text:
            return
        try:
            signals.gaps_resolved.emit()
            tree = self.parser.parse(text)
        except UnexpectedToken as e:
            signals.gaps_appeared.emit(e)
            return f"Unexpected Token: {e}"
        except Exception as e:
            signals.gaps_appeared.emit(e)
            print (f"Unexpected exception: {e}!")
            return 

        return tree

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            cr.left(), 
            cr.top(), 
            self.line_number_area_width(), 
            cr.height()
        )

class LineNumberArea(QWidget):
    def __init__(self, editor : CodeEditor):
        super().__init__(editor)
        self.editor = editor
        self.setObjectName("lineNumberArea")
        self.background = ThemeManager.get_color("editor_bg")
        self.number_col = ThemeManager.get_color("number_line_fg")
            
    def getFirstVisibleBlock(self) -> int:
        return self.editor.firstVisibleBlock().blockNumber() + 1
    
    def paintEvent(self, event):
        mypainter = QPainter(self)

        mypainter.fillRect(event.rect(), self.background)

        block       = self.editor.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top()
        bottom = top + self.editor.blockBoundingRect(block).height()

        height = self.editor.fontMetrics().height()
        while block.isValid() and (top <= event.rect().bottom()):
            block  = block.next()
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(blockNumber + 1)
                mypainter.setPen(self.number_col)
                mypainter.drawText(0, top, self.width(), height,
                 Qt.AlignmentFlag.AlignRight, number)

            top    = bottom
            bottom = top + self.editor.blockBoundingRect(block).height()
            blockNumber += 1

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

