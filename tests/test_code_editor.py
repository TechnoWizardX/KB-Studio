import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.gui.code_editor.editor import CodeEditor


class CodeEditorBracketCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.editor = CodeEditor()

    def test_opening_brackets_insert_closing_bracket_and_keep_cursor_inside(self):
        for opening, expected in (
            ("(", "()"),
            ("[", "[]"),
            ("{", "{}"),
        ):
            with self.subTest(opening=opening):
                self.editor.clear()
                QTest.keyClicks(self.editor, opening)

                self.assertEqual(self.editor.toPlainText(), expected)
                self.assertEqual(self.editor.textCursor().position(), 1)

    def test_typing_star_after_opening_parenthesis_completes_scs_delimiters(self):
        QTest.keyClicks(self.editor, "(*")

        self.assertEqual(self.editor.toPlainText(), "(**)")
        self.assertEqual(self.editor.textCursor().position(), 2)

    def test_typing_scs_closing_delimiters_moves_cursor_over_them(self):
        QTest.keyClicks(self.editor, "(*")

        QTest.keyClicks(self.editor, "*)")

        self.assertEqual(self.editor.toPlainText(), "(**)")
        self.assertEqual(self.editor.textCursor().position(), 4)

    def test_backspace_removes_empty_scs_delimiter_pair(self):
        QTest.keyClicks(self.editor, "(*")

        QTest.keyClick(self.editor, Qt.Key.Key_Backspace)

        self.assertEqual(self.editor.toPlainText(), "")

    def test_brackets_wrap_selected_text(self):
        self.editor.setPlainText("content")
        cursor = self.editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self.editor.setTextCursor(cursor)

        QTest.keyClicks(self.editor, "(")

        self.assertEqual(self.editor.toPlainText(), "(content)")
        self.assertEqual(self.editor.textCursor().position(), 8)

    def test_typing_existing_closing_bracket_moves_cursor_over_it(self):
        self.editor.setPlainText("()")
        cursor = self.editor.textCursor()
        cursor.setPosition(1)
        self.editor.setTextCursor(cursor)

        QTest.keyClicks(self.editor, ")")

        self.assertEqual(self.editor.toPlainText(), "()")
        self.assertEqual(self.editor.textCursor().position(), 2)

    def test_backspace_removes_empty_bracket_pair(self):
        QTest.keyClicks(self.editor, "[")

        QTest.keyClick(self.editor, Qt.Key.Key_Backspace)

        self.assertEqual(self.editor.toPlainText(), "")

    def test_parse_syntax_does_not_rearm_its_own_debounce_timer(self):
        """One parse is scheduled per text change: highlight work fires
        textChanged, and re-arming on those events made the editor re-parse
        (a ~150ms UI stall) once per second forever, even while idle."""
        self.editor.setPlainText("(nonexistent-scs-statement")  # parse error path
        count = 0

        def tick():
            nonlocal count
            count += 1

        timer = self.editor.parse_timer
        timer.timeout.connect(tick)
        try:
            self.editor.parse_syntax()
            # let the debounce fire once (it was armed by the explicit text
            # change); afterwards the parse must not schedule itself again,
            # so no further timer ticks arrive during the idle window
            self.app.processEvents()
            timer.start()
            QTest.qWait(1200)
            self.app.processEvents()
        finally:
            timer.timeout.disconnect(tick)
        self.assertLessEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
