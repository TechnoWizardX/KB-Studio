"""In-editor find and replace (``Ctrl+F`` / ``Ctrl+H``).

The panel floats over the editor area and routes to whichever editor owns the
active tab:

- :class:`~src.gui.code_editor.CodeEditor` — literal or regex search, case and
  whole-word options, highlight-all, next/previous and replace/replace-all;
- :class:`~src.gui.graph_editor.GraphEditorWidget` — node search by identifier,
  label and content, with next/previous selecting and centring each match.

Keeping the panel outside the editors means the same widget works for both
document kinds and the editors stay usable on their own (important for tests
and for embedding).
"""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.code_editor import CodeEditor
from src.gui.graph_editor import GraphEditorWidget
from src.gui.search.text_search import compile_query
from src.resources.icons import Icons

MAX_FIND_MATCHES = 5_000
FIND_DEBOUNCE_MS = 120


class FindLineEdit(QLineEdit):
    """Line edit with Enter / Shift+Enter / Escape handling."""

    next_pressed = Signal()
    previous_pressed = Signal()
    escape_pressed = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.previous_pressed.emit()
            else:
                self.next_pressed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class FindBar(QFrame):
    """Compact floating panel shared by text and graph editors."""

    changed = Signal()
    next_requested = Signal()
    previous_requested = Signal()
    replace_requested = Signal()
    replace_all_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("findBar")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._mode = "text"
        self._replace_visible = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        query_row = QHBoxLayout()
        query_row.setSpacing(3)
        self.query_edit = FindLineEdit(self)
        self.query_edit.setObjectName("findQueryEdit")
        self.query_edit.setPlaceholderText("Find")
        self.query_edit.setClearButtonEnabled(True)
        query_row.addWidget(self.query_edit, 1)

        self.counter = QLabel("", self)
        self.counter.setObjectName("findCounter")
        self.counter.setMinimumWidth(72)
        self.counter.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        query_row.addWidget(self.counter)

        self.previous_button = self._button(
            query_row,
            "↑",
            "Previous match (Shift+Enter)",
            self.previous_requested.emit,
        )
        self.next_button = self._button(
            query_row, "↓", "Next match (Enter)", self.next_requested.emit
        )
        self.case_button = self._toggle(query_row, "Aa", "Match case")
        self.word_button = self._toggle(
            query_row, "ab|", "Match whole word"
        )
        self.regex_button = self._toggle(
            query_row, ".*", "Use regular expression"
        )

        self.close_button = QToolButton(self)
        self.close_button.setObjectName("findBarButton")
        self.close_button.setIcon(Icons.cross())
        self.close_button.setIconSize(QSize(14, 14))
        self.close_button.setFixedSize(24, 24)
        self.close_button.setAutoRaise(True)
        self.close_button.setToolTip("Close find (Esc)")
        self.close_button.clicked.connect(self.closed)
        query_row.addWidget(self.close_button)
        layout.addLayout(query_row)

        self.replace_container = QWidget(self)
        replace_row = QHBoxLayout(self.replace_container)
        replace_row.setContentsMargins(0, 0, 0, 0)
        replace_row.setSpacing(3)
        self.replace_edit = FindLineEdit(self.replace_container)
        self.replace_edit.setObjectName("findReplaceEdit")
        self.replace_edit.setPlaceholderText("Replace")
        replace_row.addWidget(self.replace_edit, 1)
        self.replace_button = self._text_button(
            "Replace", "Replace the current match", self.replace_requested.emit
        )
        self.replace_all_button = self._text_button(
            "All", "Replace every match", self.replace_all_requested.emit
        )
        replace_row.addWidget(self.replace_button)
        replace_row.addWidget(self.replace_all_button)
        layout.addWidget(self.replace_container)
        self.replace_container.hide()

        self.error_label = QLabel("", self)
        self.error_label.setObjectName("findError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.query_edit.textChanged.connect(self.changed)
        self.query_edit.next_pressed.connect(self.next_requested)
        self.query_edit.previous_pressed.connect(self.previous_requested)
        self.query_edit.escape_pressed.connect(self.closed)
        self.replace_edit.next_pressed.connect(self.replace_requested)
        self.replace_edit.escape_pressed.connect(self.closed)
        self.case_button.toggled.connect(self._on_option_toggled)
        self.word_button.toggled.connect(self._on_option_toggled)
        self.regex_button.toggled.connect(self._on_option_toggled)

        self.hide()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _button(
        self, row: QHBoxLayout, text: str, tooltip: str, slot
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("findBarButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(24, 24)
        button.setAutoRaise(True)
        button.clicked.connect(slot)
        row.addWidget(button)
        return button

    def _toggle(
        self, row: QHBoxLayout, text: str, tooltip: str
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("findBarToggle")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCheckable(True)
        button.setFixedSize(28, 24)
        button.setAutoRaise(True)
        row.addWidget(button)
        return button

    def _text_button(self, text: str, tooltip: str, slot) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("findBarTextButton")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.clicked.connect(slot)
        return button

    def _on_option_toggled(self, _checked: bool) -> None:
        self.changed.emit()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        is_text = mode == "text"
        self.word_button.setVisible(is_text)
        self.regex_button.setVisible(is_text)
        if not is_text:
            self.word_button.setChecked(False)
            self.regex_button.setChecked(False)
        self.replace_container.setVisible(is_text and self._replace_visible)
        self._resize_to_content()

    def set_replace_visible(self, visible: bool) -> None:
        self._replace_visible = bool(visible)
        self.replace_container.setVisible(
            self._mode == "text" and self._replace_visible
        )
        self._resize_to_content()

    def set_query(self, text: str) -> None:
        was_blocked = self.query_edit.blockSignals(True)
        self.query_edit.setText(text)
        self.query_edit.blockSignals(was_blocked)

    def query(self) -> str:
        return self.query_edit.text().strip()

    def replacement(self) -> str:
        return self.replace_edit.text()

    def case_sensitive(self) -> bool:
        return self.case_button.isChecked()

    def whole_word(self) -> bool:
        return self.word_button.isChecked()

    def use_regex(self) -> bool:
        return self.regex_button.isChecked()

    def set_counter(self, current: int, total: int) -> None:
        if total <= 0:
            self.counter.setText("No results")
        else:
            self.counter.setText(f"{max(0, current) + 1} of {total}")

    def set_error(self, message: str | None) -> None:
        if message:
            self.error_label.setText(message)
            self.error_label.show()
        else:
            self.error_label.clear()
            self.error_label.hide()
        self._resize_to_content()

    def focus_query(self, *, select_all: bool = True) -> None:
        self.query_edit.setFocus()
        if select_all:
            self.query_edit.selectAll()

    def position_in(self, parent: QWidget) -> None:
        margin = 12
        width = min(560, max(340, parent.width() - 2 * margin))
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)
        self.adjustSize()
        x = parent.width() - width - margin
        y = 44
        self.setGeometry(x, y, width, self.height())
        self.raise_()

    def _resize_to_content(self) -> None:
        if self.isVisible():
            self.adjustSize()


class EditorFindController(QObject):
    """Route find/replace requests to the active editor."""

    def __init__(self, workspace: QWidget) -> None:
        super().__init__(workspace)
        self.workspace = workspace
        self.bar = FindBar(workspace)
        self._target: QWidget | None = None
        self._matches: list = []
        self._index = -1

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(FIND_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_search)

        self.bar.changed.connect(self._schedule)
        self.bar.next_requested.connect(self.next_match)
        self.bar.previous_requested.connect(self.previous_match)
        self.bar.replace_requested.connect(self.replace_current)
        self.bar.replace_all_requested.connect(self.replace_all)
        self.bar.closed.connect(self.close)

        self._find_shortcut = QShortcut(QKeySequence.StandardKey.Find, workspace)
        self._find_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._find_shortcut.activated.connect(self.open_find)

        self._replace_shortcut = QShortcut(QKeySequence("Ctrl+H"), workspace)
        self._replace_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._replace_shortcut.activated.connect(self.open_replace)

        self._next_shortcut = QShortcut(QKeySequence("F3"), workspace)
        self._next_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._next_shortcut.activated.connect(self._repeat_next)

        self._previous_shortcut = QShortcut(
            QKeySequence("Shift+F3"), workspace
        )
        self._previous_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._previous_shortcut.activated.connect(self._repeat_previous)

        if hasattr(workspace, "tabs"):
            workspace.tabs.currentChanged.connect(self._on_tab_changed)
        workspace.installEventFilter(self)

    # ------------------------------------------------------------------
    # Opening
    # ------------------------------------------------------------------
    def open_find(self) -> None:
        self._open(replace=False)

    def open_replace(self) -> None:
        self._open(replace=True)

    def _open(self, *, replace: bool) -> None:
        editor = self._active_editor()
        if editor is None:
            return
        self._target = editor
        is_graph = isinstance(editor, GraphEditorWidget)
        self.bar.set_mode("graph" if is_graph else "text")
        self.bar.set_replace_visible(replace and not is_graph)
        self._seed_from_selection(editor)
        self.bar.position_in(self.workspace)
        self.bar.show()
        self.bar.raise_()
        self.bar.focus_query(select_all=not self.bar.query())
        self._run_search()

    def _seed_from_selection(self, editor) -> None:
        if not isinstance(editor, CodeEditor):
            return
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            return
        text = cursor.selectedText().replace("\u2029", "\n")
        if text and "\n" not in text:
            self.bar.set_query(text)

    def _repeat_next(self) -> None:
        if not self.bar.isVisible():
            self.open_find()
            return
        self.next_match()

    def _repeat_previous(self) -> None:
        if not self.bar.isVisible():
            self.open_find()
            return
        self.previous_match()

    # ------------------------------------------------------------------
    # Search dispatch
    # ------------------------------------------------------------------
    def _active_editor(self) -> QWidget | None:
        if hasattr(self.workspace, "tabs"):
            return self.workspace.tabs.currentWidget()
        return None

    def _on_tab_changed(self, _index: int) -> None:
        if not self.bar.isVisible():
            return
        editor = self._active_editor()
        if editor is None:
            self.close()
            return
        self._target = editor
        is_graph = isinstance(editor, GraphEditorWidget)
        self.bar.set_mode("graph" if is_graph else "text")
        if is_graph:
            self.bar.set_replace_visible(False)
        self._run_search()

    def _schedule(self) -> None:
        self._debounce.start()

    def _run_search(self) -> None:
        editor = self._active_editor()
        if editor is None:
            self.close()
            return
        self._target = editor
        query = self.bar.query()
        if not query:
            self._clear_results()
            return
        if isinstance(editor, CodeEditor):
            self._search_text(editor, query)
        elif isinstance(editor, GraphEditorWidget):
            self._search_graph(editor, query)
        else:
            self.close()

    def _search_text(self, editor: CodeEditor, query: str) -> None:
        try:
            pattern = compile_query(
                query,
                case_sensitive=self.bar.case_sensitive(),
                regex=self.bar.use_regex(),
                whole_word=self.bar.whole_word(),
            )
        except re.error as error:
            self._matches = []
            self._index = -1
            editor.clear_search_highlights()
            self.bar.set_counter(0, 0)
            self.bar.set_error(f"Invalid regular expression: {error}")
            return

        self.bar.set_error(None)
        text = editor.toPlainText()
        matches: list[tuple[int, int]] = []
        for match in pattern.finditer(text):
            matches.append((match.start(), max(1, match.end() - match.start())))
            if len(matches) >= MAX_FIND_MATCHES:
                break

        self._matches = matches
        self._index = 0 if matches else -1
        editor.set_search_highlights(matches, self._index)
        if matches:
            editor.goto_range(*matches[0], focus=False)
        self._update_counter()

    def _search_graph(self, editor: GraphEditorWidget, query: str) -> None:
        self.bar.set_error(None)
        nodes = editor.search_nodes(
            query, case_sensitive=self.bar.case_sensitive()
        )
        self._matches = nodes
        self._index = 0 if nodes else -1
        if nodes:
            editor.activate_search_result(nodes[0], focus=False)
        self._update_counter()

    def _update_counter(self) -> None:
        total = len(self._matches)
        self.bar.set_counter(self._index, total)

    def _clear_results(self) -> None:
        if isinstance(self._target, CodeEditor):
            self._target.clear_search_highlights()
        self._matches = []
        self._index = -1
        self.bar.set_counter(0, 0)
        self.bar.set_error(None)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def next_match(self) -> None:
        if not self._matches:
            return
        self._index = (self._index + 1) % len(self._matches)
        self._apply_current()

    def previous_match(self) -> None:
        if not self._matches:
            return
        self._index = (self._index - 1) % len(self._matches)
        self._apply_current()

    def _apply_current(self) -> None:
        if not self._matches or self._index < 0:
            return
        if isinstance(self._target, CodeEditor):
            self._target.set_search_highlights(self._matches, self._index)
            start, length = self._matches[self._index]
            self._target.goto_range(start, length, focus=False)
        elif isinstance(self._target, GraphEditorWidget):
            self._target.activate_search_result(
                self._matches[self._index], focus=False
            )
        self._update_counter()

    # ------------------------------------------------------------------
    # Replace
    # ------------------------------------------------------------------
    def replace_current(self) -> None:
        editor = self._target
        if not isinstance(editor, CodeEditor):
            return
        if not self._matches or self._index < 0:
            return
        start, length = self._matches[self._index]
        replacement = self._replacement_for(editor.toPlainText(), start)
        if replacement is None:
            return

        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        cursor.endEditBlock()

        previous_index = self._index
        self._run_search()
        if self._matches:
            self._index = min(previous_index, len(self._matches) - 1)
            self._apply_current()

    def replace_all(self) -> None:
        editor = self._target
        if not isinstance(editor, CodeEditor):
            return
        try:
            pattern = compile_query(
                self.bar.query(),
                case_sensitive=self.bar.case_sensitive(),
                regex=self.bar.use_regex(),
                whole_word=self.bar.whole_word(),
            )
        except re.error as error:
            self.bar.set_error(f"Invalid regular expression: {error}")
            return

        text = editor.toPlainText()
        matches = [
            (match.start(), match.end() - match.start(), match)
            for match in pattern.finditer(text)
        ]
        if not matches:
            return

        replacement_text = self.bar.replacement()
        use_regex = self.bar.use_regex()
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        try:
            for start, length, match in reversed(matches):
                replacement = (
                    match.expand(replacement_text)
                    if use_regex
                    else replacement_text
                )
                cursor.setPosition(start)
                cursor.setPosition(
                    start + length, QTextCursor.MoveMode.KeepAnchor
                )
                cursor.insertText(replacement)
        except re.error as error:
            self.bar.set_error(f"Invalid replacement: {error}")
        finally:
            cursor.endEditBlock()
        self._run_search()

    def _replacement_for(self, text: str, start: int) -> str | None:
        replacement = self.bar.replacement()
        if not self.bar.use_regex():
            return replacement
        try:
            pattern = compile_query(
                self.bar.query(),
                case_sensitive=self.bar.case_sensitive(),
                regex=True,
                whole_word=self.bar.whole_word(),
            )
            match = pattern.match(text, start)
            return match.expand(replacement) if match is not None else replacement
        except re.error as error:
            self.bar.set_error(f"Invalid replacement: {error}")
            return None

    # ------------------------------------------------------------------
    # Closing and layout
    # ------------------------------------------------------------------
    def close(self) -> None:
        self._debounce.stop()
        self.bar.hide()
        if isinstance(self._target, CodeEditor):
            self._target.clear_search_highlights()
        self._matches = []
        self._index = -1
        self._focus_editor()

    def _focus_editor(self) -> None:
        editor = self._active_editor()
        if editor is None:
            return
        view = getattr(editor, "view", None)
        if view is not None:
            view.setFocus()
        else:
            editor.setFocus()

    def eventFilter(self, obj, event) -> bool:
        if obj is self.workspace and event.type() == QEvent.Type.Resize:
            if self.bar.isVisible():
                self.bar.position_in(self.workspace)
        return super().eventFilter(obj, event)
