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


if __name__ == "__main__":
    unittest.main()
