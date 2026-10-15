from pathlib import Path

from lark.exceptions import (
    LexError,
    ParseError,
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedToken,
)
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QShortcut,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from src.core.signals import signals
from src.lark_syntax.parser import SCSParser
from src.resources.icons import Icons
from src.gui.syntax_highlighter import SCSHighlighter
from src.utils.config_manager import ConfigManager
from src.utils.security import get_project_root, safe_path
from src.utils.theme_manager import ThemeManager


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
        paths_to_restore = list(
            dict.fromkeys(
                [path for path in last_viewed_files if isinstance(path, str)]
                + (
                    [last_viewed_file]
                    if isinstance(last_viewed_file, str) and last_viewed_file
                    else []
                )
            )
        )
        for path in paths_to_restore:
            self.apply_file(path)
        if last_viewed_file:
            for index in range(self.count()):
                editor = self.widget(index)
                if editor.abs_path == Path(last_viewed_file).resolve():
                    self.setCurrentIndex(index)
                    break

    def apply_file(self, file_path: str | Path) -> None:
        if not file_path:
            return

        try:
            safe_file = safe_path(get_project_root(), str(file_path))
            if not safe_file.is_file():
                raise FileNotFoundError(f"Not a file: {safe_file}")
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Cannot open file", str(error))
            return

        for index in range(self.count()):
            editor = self.widget(index)
            if editor.abs_path == safe_file:
                self.setCurrentIndex(index)
                return

        try:
            editor = CodeEditor(safe_file)
            index = self.addTab(editor, safe_file.name)
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
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.warning(
                self, "Cannot open file", f"{safe_file}\n\n{error}"
            )
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
        close_button.clicked.connect(lambda *_: self._close_editor(editor))
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
            if (
                answer == QMessageBox.StandardButton.Save
                and not editor.save_changes()
            ):
                return

        self.removeTab(index)
        self._persist_open_tabs()
        editor.deleteLater()


class CodeEditor(QPlainTextEdit):
    syntax_status_changed = Signal(object)
    parser = SCSParser()
    bracket_pairs = {"(": ")", "[": "]", "{": "}", "<": ">"}
    closing_brackets = {
        closing: opening for opening, closing in bracket_pairs.items()
    }

    def __init__(self, path: str | Path | None = None):
        super().__init__()
        self.setObjectName("codeEditor")
        self.abs_path = Path(path).resolve() if path else None
        self.syntax_error: str | None = None
        self.setViewportMargins(20, 0, 0, 0)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.line_number_area = LineNumberArea(self)
        self.shortcut_zoom_in = QShortcut(QKeySequence("Ctrl++"), self)
        self.shortcut_zoom_in.activated.connect(self.zoom_in)
        self.shortcut_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        self.shortcut_zoom_out.activated.connect(self.zoom_out)
        self.shorcut_save_changes = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shorcut_save_changes.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.shorcut_save_changes.activated.connect(self.save_changes)

        self.line_highlight = ThemeManager.get_color("line_highlight_color")
        self.highlighter = SCSHighlighter(self.document(), self.parser)
        self.blockCountChanged.connect(self.update_line_area_width)
        self.updateRequest.connect(self.update_line_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.parse_timer = QTimer()
        self.parse_timer.timeout.connect(self.parse_syntax)
        self.parse_timer.setSingleShot(True)
        self.parse_timer.setInterval(500)
        self.textChanged.connect(self.reset_changed_timer)

        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.save_changes)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.textChanged.connect(self.reset_changed_timer)

        signals.theme_changed.connect(self.on_theme_changed)
        signals.auto_save_changed.connect(self.on_auto_save_changed)
        if self.abs_path is not None:
            self.load_file(self.abs_path)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        cursor = self.textCursor()
        text = event.text()

        modifiers = event.modifiers()
        shortcut_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        if (
            not self.isReadOnly()
            and text in self.bracket_pairs
            and not modifiers & shortcut_modifiers
        ):
            closing = self.bracket_pairs[text]
            selected_text = cursor.selectedText()
            if selected_text:
                selected_text = selected_text.replace("\u2029", "\n")
                cursor.insertText(f"{text}{selected_text}{closing}")
                cursor.setPosition(cursor.position() - 1)
            else:
                cursor.insertText(f"{text}{closing}")
                cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
            self.setTextCursor(cursor)
            return

        if (
            not self.isReadOnly()
            and text == "*"
            and not modifiers & shortcut_modifiers
            and not cursor.hasSelection()
        ):
            position = cursor.position()
            content = self.toPlainText()
            if (
                position > 0
                and position < len(content)
                and content[position - 1] == "("
                and content[position] == ")"
            ):
                cursor.setPosition(position - 1)
                cursor.setPosition(position + 1, QTextCursor.MoveMode.KeepAnchor)
                cursor.insertText("(**)")
                cursor.setPosition(position + 1)
                self.setTextCursor(cursor)
                return

        if (
            not self.isReadOnly()
            and (text in self.closing_brackets or text == "*")
            and not modifiers & shortcut_modifiers
            and not cursor.hasSelection()
        ):
            content = self.toPlainText()
            if cursor.position() < len(content):
                next_character = content[cursor.position()]
                if next_character == text or (
                    text == "*"
                    and content[cursor.position() : cursor.position() + 2] == "*)"
                ):
                    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
                    self.setTextCursor(cursor)
                    return

        if (
            not self.isReadOnly()
            and event.key() == Qt.Key.Key_Backspace
            and not modifiers & shortcut_modifiers
            and not cursor.hasSelection()
        ):
            position = cursor.position()
            content = self.toPlainText()
            if (
                content[position - 2 : position] == "(*"
                and content[position : position + 2] == "*)"
            ):
                cursor.setPosition(position - 2)
                cursor.setPosition(position + 2, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                self.setTextCursor(cursor)
                return
            if position > 0 and position < len(content):
                previous_character = content[position - 1]
                next_character = content[position]
                if self.bracket_pairs.get(previous_character) == next_character:
                    cursor.setPosition(position - 1)
                    cursor.setPosition(
                        position + 1, QTextCursor.MoveMode.KeepAnchor
                    )
                    cursor.removeSelectedText()
                    self.setTextCursor(cursor)
                    return

        super().keyPressEvent(event)

    def reset_changed_timer(self) -> None:
        self.parse_timer.start()
        if self.abs_path is not None and ConfigManager.get("auto_save"):
            self.save_timer.start()
        else:
            self.save_timer.stop()

    def on_auto_save_changed(self, enabled: bool) -> None:
        if enabled and self.abs_path is not None and self.document().isModified():
            self.save_timer.start()
        else:
            self.save_timer.stop()

    def line_number_area_width(self) -> int:
        digits = 1
        count = max(1, self.blockCount())
        while count >= 10:
            count //= 10
            digits += 1
        return 20 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_area_width(self) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_area(self, rect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0, rect.y(), self.line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.update_line_area_width()

    def highlight_current_line(self) -> None:
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(self.line_highlight))
            selection.format.setProperty(0x06000, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def zoom_in(self, amount: int = 2) -> None:
        self.zoomIn(amount)
        self.line_number_area.setFont(self.font())
        self.update_line_area_width()

    def zoom_out(self, amount: int = 2) -> None:
        self.zoomOut(amount)
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
        file_path = self.abs_path
        if not file_path:
            return False
        try:
            safe_file = safe_path(get_project_root(), str(file_path))
            safe_file.write_text(self.toPlainText(), encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.critical(
                self, "Cannot save file", f"{file_path}\n\n{error}"
            )
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
        except UnexpectedToken as error:
            line = getattr(error, "line", "?")
            column = getattr(error, "column", "?")
            expected = getattr(error, "expected", [])
            message = (
                f"Line {line}, col {column}: unexpected token '{error.token}'"
            )
            if expected:
                message += f", expected: {', '.join(expected)}"
            self._set_syntax_error(message)
            self._highlight_error_position(error)
        except UnexpectedCharacters as error:
            line = getattr(error, "line", "?")
            column = getattr(error, "column", "?")
            char = getattr(error, "char", "?")
            self._set_syntax_error(
                f"Line {line}, col {column}: invalid character '{char}'"
            )
            self._highlight_error_position(error)
        except UnexpectedEOF as error:
            expected = getattr(error, "expected", [])
            message = "Unexpected end of input"
            if expected:
                message += f", expected: {', '.join(expected)}"
            self._set_syntax_error(message)
            self._highlight_error_position(error)
        except LexError as error:
            self._set_syntax_error(f"Lexer error: {error}")
        except ParseError as error:
            self._set_syntax_error(f"Parse error: {error}")
        except Exception as error:
            import traceback

            traceback.print_exc()
            self._set_syntax_error(
                f"Internal parser error: {type(error).__name__}"
            )

    def _set_syntax_error(self, error: str | None) -> None:
        self.syntax_error = error
        self.syntax_status_changed.emit(error)

    def _highlight_error_position(self, exception) -> None:
        pos = getattr(exception, "pos_in_stream", None)
        if pos is not None:
            self.highlighter.set_error_positions([(pos, pos + 1)])
        else:
            self.highlighter.clear_errors()

    def on_theme_changed(self, theme_name: str) -> None:
        self.highlighter.set_theme(theme_name)
        self.line_highlight = ThemeManager.get_color("line_highlight_color")
        self.line_number_area.background = ThemeManager.get_color("editor_bg")
        self.line_number_area.number_col = ThemeManager.get_color("number_line_fg")
        self.line_number_area.update()
        self.viewport().update()

    def update_theme_colors(self) -> None:
        self.on_theme_changed(ConfigManager.get("theme"))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        content_rect = self.contentsRect()
        self.line_number_area.setGeometry(
            content_rect.left(),
            content_rect.top(),
            self.line_number_area_width(),
            content_rect.height(),
        )


class LineNumberArea(QWidget):
    def __init__(self, editor: CodeEditor):
        super().__init__(editor)
        self.editor = editor
        self.setObjectName("lineNumberArea")
        self.background = ThemeManager.get_color("editor_bg")
        self.number_col = ThemeManager.get_color("number_line_fg")

    def getFirstVisibleBlock(self) -> int:
        return self.editor.firstVisibleBlock().blockNumber() + 1

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), self.background)

        block = self.editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = (
            self.editor.blockBoundingGeometry(block)
            .translated(self.editor.contentOffset())
            .top()
        )
        bottom = top + self.editor.blockBoundingRect(block).height()
        height = self.editor.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(self.number_col)
                painter.drawText(
                    0,
                    top,
                    self.width(),
                    height,
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + self.editor.blockBoundingRect(block).height()
            block_number += 1
