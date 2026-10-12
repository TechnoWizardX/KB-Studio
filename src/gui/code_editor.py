from PySide6.QtWidgets import QVBoxLayout, QTabWidget, QHBoxLayout, QPushButton, QFrame, QPlainTextEdit, QSplitter, QWidget, QTextEdit, QStackedWidget, QMessageBox
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QKeySequence, QShortcut
from pathlib import Path
from src.utils.theme_manager import ThemeManager
from src.core.signals import signals
from src.lark_syntax.parser import SCSParser
from src.utils.config_manager import ConfigManager
from src.utils.security import safe_path, get_project_root
from src.resources.icons import Icons
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

        self.code_editor_workspace = CodeEditorWorkspace()
        self.splitter.addWidget(self.code_editor_workspace)

        self.dev_panel_widget = DevPanelWidget()
        self.splitter.addWidget(self.dev_panel_widget)
        self.code_editor_workspace.currentChanged.connect(
            self._show_current_editor_diagnostics
        )
        self.code_editor_workspace.syntax_status_changed.connect(
            self._show_editor_diagnostics
        )

        self.splitter.setSizes([700, 300])


    def apply_file(self, file_path : str | Path):
        self.code_editor_workspace.apply_file(file_path)

    def _show_current_editor_diagnostics(self, index: int) -> None:
        editor = self.code_editor_workspace.widget(index)
        error = editor.syntax_error if isinstance(editor, CodeEditor) else None
        self.dev_panel_widget.problems_wgt.show_diagnostics(error)

    def _show_editor_diagnostics(
        self, editor: "CodeEditor", error: str | None
    ) -> None:
        if self.code_editor_workspace.currentWidget() is editor:
            self.dev_panel_widget.problems_wgt.show_diagnostics(error)



class DevPanelWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("devPanelWidget")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.buttons_layout)

        self.problems_btn = QPushButton("Problems")
        self.problems_btn.setObjectName("devPanelBtn")
        self.problems_btn.setMaximumSize(100, 60)
        self.buttons_layout.addWidget(self.problems_btn)

        self.problems_wgt = ProblemsWidget()

        #self.terminal_btn = QPushButton("Terminal")
        #self.terminal_btn.setObjectName("devPanelBtn")
        #self.terminal_btn.setMaximumSize(100, 60)
        #self.buttons_layout.addWidget(self.terminal_btn)

        #self.terminal = Terminal()

        self.stacked_widget = QStackedWidget()

        self.stacked_widget.addWidget(self.problems_wgt)
        #self.stacked_widget.addWidget(self.terminal)

        self.main_layout.addWidget(self.stacked_widget)

        self.problems_btn.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.problems_wgt))
        #self.terminal_btn.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.terminal))
        


class ProblemsWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.show_diagnostics(None)

    def show_diagnostics(self, error: str | None) -> None:
        self.setText(error if error else "There is no syntax issues")


class CodeEditorWorkspace(QTabWidget):
    syntax_status_changed = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.setObjectName("codeEditorWorkspace")
        self.setTabsClosable(False)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.tabBar().setExpanding(False)
        self.tabBar().setUsesScrollButtons(True)
        self.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.tabBar().setDrawBase(False)
        self.currentChanged.connect(self._on_current_changed)
        signals.theme_changed.connect(self._refresh_close_icons)
        signals.selected_new_file.connect(self.apply_file)
        last_viewed_files = ConfigManager.get("last_viewed_files")
        if not isinstance(last_viewed_files, list):
            last_viewed_files = []
        last_viewed_file = ConfigManager.get("last_viewed_file")
        paths_to_restore = list(dict.fromkeys(
            [path for path in last_viewed_files if isinstance(path, str)]
            + ([last_viewed_file] if isinstance(last_viewed_file, str) and last_viewed_file else [])
        ))
        for path in paths_to_restore:
            self.apply_file(path)
        if last_viewed_file:
            for index in range(self.count()):
                editor = self.widget(index)
                if editor.abs_path == Path(last_viewed_file).resolve():
                    self.setCurrentIndex(index)
                    break

    def apply_file(self, file_path : str | Path):
        if not file_path:
            return

        try:
            safe_file = safe_path(get_project_root(), str(file_path))
            if not safe_file.is_file():
                raise FileNotFoundError(f"Not a file: {safe_file}")
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Cannot open file", str(e))
            return

        for i in range(self.count()):
            editor = self.widget(i)
            if editor.abs_path == safe_file:
                self.setCurrentIndex(i)
                return

        try:
            editor = CodeEditor(safe_file)
            title = safe_file.name
            index = self.addTab(editor, title)
            self.setTabToolTip(index, str(safe_file))
            self._set_close_icon(index)
            editor.syntax_status_changed.connect(
                lambda error, current_editor=editor: self.syntax_status_changed.emit(
                    current_editor, error
                )
            )
            editor.document().modificationChanged.connect(
                lambda modified, current_editor=editor: self._update_tab_title(
                    current_editor, modified
                )
            )
        except (OSError, UnicodeError, ValueError) as e:
            QMessageBox.warning(self, "Cannot open file", f"{safe_file}\n\n{e}")
            return

        self.setCurrentWidget(editor)

    def _set_close_icon(self, index: int) -> None:
        editor = self.widget(index)
        if not isinstance(editor, CodeEditor):
            return
        close_button = QPushButton()
        close_button.setObjectName("editorTabCloseButton")
        close_button.setIcon(Icons.cross())
        close_button.setIconSize(QSize(14, 14))
        close_button.setFixedSize(18, 18)
        close_button.setToolTip("Close tab")
        close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close_button.clicked.connect(
            lambda *_: self._close_editor(editor)
        )
        self.tabBar().setTabButton(
            index, self.tabBar().ButtonPosition.RightSide, close_button
        )

    def _close_editor(self, editor: "CodeEditor") -> None:
        index = self.indexOf(editor)
        if index >= 0:
            self.close_tab(index)

    def _refresh_close_icons(self) -> None:
        for index in range(self.count()):
            self._set_close_icon(index)

    def _on_current_changed(self, index: int) -> None:
        editor = self.widget(index)
        if isinstance(editor, CodeEditor) and editor.abs_path is not None:
            current_file = str(editor.abs_path)
        elif index < 0:
            current_file = ""
        else:
            current_file = ""

        ConfigManager.set("selected_file", current_file)
        self._persist_open_tabs(current_file)

    def _persist_open_tabs(self, current_file: str | None = None) -> None:
        open_files = [
            str(editor.abs_path)
            for index in range(self.count())
            if isinstance((editor := self.widget(index)), CodeEditor)
            and editor.abs_path is not None
        ]
        if current_file is None:
            editor = self.currentWidget()
            current_file = (
                str(editor.abs_path)
                if isinstance(editor, CodeEditor) and editor.abs_path is not None
                else ""
            )
        ConfigManager.set("last_viewed_files", open_files)
        ConfigManager.set("last_viewed_file", current_file)

    def _update_tab_title(self, editor: "CodeEditor", modified: bool) -> None:
        index = self.indexOf(editor)
        if index >= 0:
            title = Path(editor.abs_path).name if editor.abs_path else "Untitled"
            self.setTabText(index, f"{title} *" if modified else title)

    def close_tab(self, index: int) -> None:
        editor = self.widget(index)
        if not isinstance(editor, CodeEditor):
            return

        if editor.document().isModified():
            answer = QMessageBox.question(
                self,
                "Unsaved changes",
                f"Save changes to '{Path(editor.abs_path).name}' before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save and not editor.save_changes():
                return

        self.removeTab(index)
        self._persist_open_tabs()
        editor.deleteLater()


class CodeEditor(QPlainTextEdit):
    syntax_status_changed = Signal(object)
    parser = SCSParser()
    def __init__(self, path: str | Path | None = None):
        super().__init__()
        self.setObjectName("codeEditor")
        self.abs_path = Path(path).resolve() if path else None
        self.syntax_error: str | None = None
        self.setViewportMargins(20, 0, 0, 0)

        self.line_number_area = LineNumberArea(self)

        self.shortcut_zoom_in = QShortcut(QKeySequence("Ctrl++"), self)
        self.shortcut_zoom_in.activated.connect(self.zoom_in)

        self.shortcut_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shortcut_zoom_out.activated.connect(self.zoom_out)

        self.shorcut_save_changes = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shorcut_save_changes.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
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
        
        signals.theme_changed.connect(self.on_theme_changed)
        if self.abs_path is not None:
            self.load_file(self.abs_path)

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
    
    def load_file(self, file_path: str | Path) -> None:
        safe_file = safe_path(get_project_root(), str(file_path))
        text = safe_file.read_text(encoding="utf-8")
        self.abs_path = safe_file
        self.setPlainText(text)
        self.document().setModified(False)
        self.update_line_area_width()

    def save_changes(self) -> bool:
        text = self.toPlainText()
        file_path = self.abs_path
        if not file_path:
            return False
        try:
            safe_file = safe_path(get_project_root(), str(file_path))
            safe_file.write_text(text, encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as e:
            QMessageBox.critical(self, "Cannot save file", f"{file_path}\n\n{e}")
            return False
        self.document().setModified(False)
        return True

    def parse_syntax(self):
        text = self.toPlainText()
        if not text:
            self._set_syntax_error(None)
            self.highlighter.clear_errors()
            return
        try:
            tree = self.parser.parse(text)
            self._set_syntax_error(None)
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
            self._set_syntax_error(error)
            self._highlight_error_position(e)

        except UnexpectedCharacters as e:
            # Лексическая ошибка: недопустимый символ
            line = getattr(e, 'line', '?')
            column = getattr(e, 'column', '?')
            char = getattr(e, 'char', '?')
            error = f"Line {line}, col {column}: invalid character '{char}'"
            self._set_syntax_error(error)
            self._highlight_error_position(e)

        except UnexpectedEOF as e:
            # Неожиданный конец файла (незакрытые скобки и т.д.)
            expected = getattr(e, 'expected', [])
            error = f"Unexpected end of input"
            if expected:
                error += f", expected: {', '.join(expected)}"
            self._set_syntax_error(error)
            self._highlight_error_position(e)

        except LexError as e:
            # Ошибка токенизатора
            self._set_syntax_error(f"Lexer error: {e}")

        except ParseError as e:
            # Общая ошибка парсера (fallback)
            self._set_syntax_error(f"Parse error: {e}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._set_syntax_error(f"Internal parser error: {type(e).__name__}")

    def _set_syntax_error(self, error: str | None) -> None:
        self.syntax_error = error
        self.syntax_status_changed.emit(error)

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



# class Terminal(QFrame):
#     """This is terminal widget that allows users to execute shell commands within the application."""
#     def __init__(self):
#         super().__init__()
#         self.setObjectName("terminal")
#
#         self.output = QPlainTextEdit()
#         self.output.setReadOnly(True)
#         self.output.setTextInteractionFlags(   
#         Qt.TextInteractionFlag.TextSelectableByMouse |
#         Qt.TextInteractionFlag.TextSelectableByKeyboard |
#         Qt.TextInteractionFlag.LinksAccessibleByMouse
#         )
#
#         self.input = QLineEdit()
#         self.input.setPlaceholderText("Введите команду...")
#
#         layout = QVBoxLayout(self)
#         layout.addWidget(self.output)
#         layout.addWidget(self.input)
#         layout.setContentsMargins(0, 0, 0, 0)
#
#         self.process = QProcess(self)
#         self.process.readyReadStandardOutput.connect(self._on_output)
#         self.process.readyReadStandardError.connect(self._on_error)
#         self.process.setWorkingDirectory(ConfigManager.get("project_dir"))
#
#         shell = "powershell.exe" if sys.platform == "win32" else "bash"
#         self.process.start(shell)
#
#         self.input.returnPressed.connect(self._execute)
#
#     def _execute(self):
#         if self.process.state() != QProcess.ProcessState.Running:
#             self.output.appendPlainText("[Terminal: shell not running]")
#         cmd = self.input.text().strip()
#         if not cmd:
#             return
#         self.output.appendPlainText(f"$ {cmd}")
#         self.process.write(cmd.encode() + b"\n")
#         self.input.clear()
#
#     def _on_output(self):
#         text = self.process.readAllStandardOutput().data().decode(errors="replace")
#         self.output.insertPlainText(text)
#         self.output.ensureCursorVisible()
#
#     def _on_error(self):
#         text = self.process.readAllStandardError().data().decode(errors="replace")
#         self.output.insertPlainText(text)
#         self.output.ensureCursorVisible()
#
#     def closeEvent(self, event):
#         if self.process.state() != QProcess.ProcessState.NotRunning:
#             self.process.terminate()
#         self.process.waitForFinished(1000)
#         if self.process.state() != QProcess.ProcessState.NotRunning:
#             self.process.kill()
#         super().closeEvent(event)
    