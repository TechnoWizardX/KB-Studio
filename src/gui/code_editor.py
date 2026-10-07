from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QPlainTextEdit, QSplitter, QWidget, QLineEdit, QTextEdit, QStackedWidget
from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import QColor, QPainter, QKeySequence, QShortcut
import sys 
from pathlib import Path
from src.utils.theme_manager import ThemeManager
from src.core.signals import signals
from src.lark_syntax.parser import SCSParser
from src.utils.config_manager import ConfigManager
from src.gui.syntax_highlighter import SCSHighlighter
from lark.exceptions import UnexpectedToken, UnexpectedCharacters, UnexpectedEOF, LexError, ParseError


class CodeEditorWidget(QFrame):
    def __init__(self, parent : QWidget = None):
        super().__init__(parent=parent)

        self.setObjectName("codeEditorWidget")
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setHandleWidth(5)
        self.main_layout.addWidget(self.splitter)

        self.code_editor = CodeEditor()
        self.splitter.addWidget(self.code_editor)

        self.dev_panel_widget = DevPanelWidget()
        self.splitter.addWidget(self.dev_panel_widget)

        self.splitter.setSizes([700, 300])


    def apply_file(self, file_path : str | Path):
        self.code_editor.apply_file(file_path)



class DevPanelWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("devPanelWidget")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.buttons_layout)

        self.problems_btn = QPushButton("Problems")
        self.problems_btn.setObjectName("devPanelBtn")
        self.problems_btn.setMaximumSize(100, 60)
        self.buttons_layout.addWidget(self.problems_btn)

        self.problems_wgt = ProblemsWidget()

        self.terminal_btn = QPushButton("Terminal")
        self.terminal_btn.setObjectName("devPanelBtn")
        self.terminal_btn.setMaximumSize(100, 60)
        self.buttons_layout.addWidget(self.terminal_btn)

        self.terminal = Terminal()

        self.stacked_widget = QStackedWidget()

        self.stacked_widget.addWidget(self.problems_wgt)
        self.stacked_widget.addWidget(self.terminal)

        self.main_layout.addWidget(self.stacked_widget)

        self.problems_btn.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.problems_wgt))
        self.terminal_btn.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.terminal))
        


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

        self.shortcut_zoom_in = QShortcut(QKeySequence("Ctrl++"), self)
        self.shortcut_zoom_in.activated.connect(self.zoom_in)

        self.shortcut_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shortcut_zoom_out.activated.connect(self.zoom_out)

        self.shorcut_save_changes = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shorcut_save_changes.activated.connect(self.save_changes)

        self.line_highlight = ThemeManager.get_color("line_highlight_color")

        self.highlighter = SCSHighlighter(self.document(), self.parser)

        self.blockCountChanged.connect(self.update_line_area_width)
        self.updateRequest.connect(self.update_line_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.parse_timer = QTimer()
        self.parse_timer.timeout.connect(self.parse_syntax)
        self.parse_timer.setSingleShot(True)

        self.parse_timer.setInterval(1000)

        self.textChanged.connect(self.reset_parse_timer)


        self.apply_file(ConfigManager.get("last_viewed_file"))
        signals.selected_new_file.connect(self.apply_file)
        
        signals.theme_changed.connect(self.on_theme_changed)

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
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                    self.setPlainText(text)
                    print(f"Inserted next file: {text}")
            except Exception as e:
                print("Cannot load file")
                self.setPlainText("")

    def save_changes(self):
        text = self.toPlainText()
        file_path = ConfigManager.get("selected_file")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            print(f"ERROR: {e}")

    def parse_syntax(self):
        text = self.toPlainText()
        if not text:
            signals.gaps_resolved.emit()
            self.highlighter.clear_errors()
            return
        try:
            tree = self.parser.parse(text)
            signals.gaps_resolved.emit()
            self.highlighter.clear_errors()
            self.highlighter.refresh_tokens()
            return tree
        except UnexpectedToken as e:
            # Синтаксическая ошибка: неожиданный токен
            line = getattr(e, 'line', '?')
            column = getattr(e, 'column', '?')
            expected = getattr(e, 'expected', [])
            error = f"Line {line}, col {column}: unexpected token '{e.token}'"
            if expected:
                error += f", expected: {', '.join(expected)}"
            signals.gaps_appeared.emit(error)
            self._highlight_error_position(e)

        except UnexpectedCharacters as e:
            # Лексическая ошибка: недопустимый символ
            line = getattr(e, 'line', '?')
            column = getattr(e, 'column', '?')
            char = getattr(e, 'char', '?')
            error = f"Line {line}, col {column}: invalid character '{char}'"
            signals.gaps_appeared.emit(error)
            self._highlight_error_position(e)

        except UnexpectedEOF as e:
            # Неожиданный конец файла (незакрытые скобки и т.д.)
            expected = getattr(e, 'expected', [])
            error = f"Unexpected end of input"
            if expected:
                error += f", expected: {', '.join(expected)}"
            signals.gaps_appeared.emit(error)
            self._highlight_error_position(e)

        except LexError as e:
            # Ошибка токенизатора
            signals.gaps_appeared.emit(f"Lexer error: {e}")

        except ParseError as e:
            # Общая ошибка парсера (fallback)
            signals.gaps_appeared.emit(f"Parse error: {e}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            signals.gaps_appeared.emit(f"Internal parser error: {type(e).__name__}")

    def _highlight_error_position(self, exception):
        """Set error highlight position from Lark exception."""
        # Lark exceptions have pos_in_stream for character position
        pos = getattr(exception, 'pos_in_stream', None)
        if pos is not None:
            # Highlight a small range around the error
            self.highlighter.set_error_positions([(pos, pos + 1)])
        else:
            self.highlighter.clear_errors()

    def on_theme_changed(self, theme_name: str):
        """Handle theme change - update highlighter colors."""
        self.highlighter.set_theme(theme_name)
        self.line_highlight = ThemeManager.get_color("line_highlight_color")
        self.line_number_area.background = ThemeManager.get_color("editor_bg")
        self.line_number_area.number_col = ThemeManager.get_color("number_line_fg")
        self.line_number_area.update()
        self.viewport().update()

    def update_theme_colors(self):
        """Public method to refresh theme colors."""
        self.on_theme_changed(ConfigManager.get("theme"))

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
    """This is terminal widget that allows users to execute shell commands within the application."""
    def __init__(self):
        super().__init__()
        self.setObjectName("terminal")

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setTextInteractionFlags(   
        Qt.TextInteractionFlag.TextSelectableByMouse |
        Qt.TextInteractionFlag.TextSelectableByKeyboard |
        Qt.TextInteractionFlag.LinksAccessibleByMouse
        )

        self.input = QLineEdit()
        self.input.setPlaceholderText("Введите команду...")

        layout = QVBoxLayout(self)
        layout.addWidget(self.output)
        layout.addWidget(self.input)
        layout.setContentsMargins(0, 0, 0, 0)

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._on_output)
        self.process.readyReadStandardError.connect(self._on_error)
        self.process.setWorkingDirectory(ConfigManager.get("project_dir"))

        shell = "powershell.exe" if sys.platform == "win32" else "bash"
        self.process.start(shell)

        self.input.returnPressed.connect(self._execute)

    def _execute(self):
        if self.process.state() != QProcess.ProcessState.Running:
            self.output.appendPlainText("[Terminal: shell not running]")
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

    def closeEvent(self, event):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
        self.process.waitForFinished(1000)
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
        super().closeEvent(event)
    