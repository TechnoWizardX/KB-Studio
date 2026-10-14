import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication

from src.gui.syntax_highlighter import SCSHighlighter
from src.lark_syntax.parser import SCSParser


class SCSSyntaxHighlighterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.document = QTextDocument()
        self.highlighter = SCSHighlighter(self.document, SCSParser())

    def _color_at(self, block_number: int, position: int) -> str | None:
        block = self.document.findBlockByNumber(block_number)
        for item in block.layout().formats():
            if item.start <= position < item.start + item.length:
                return item.format.foreground().color().name()
        return None

    def test_highlights_identifiers_edges_strings_and_line_comments(self):
        self.document.setPlainText('node1 -> "url";; // note')
        self.highlighter.rehighlight()

        self.assertEqual(self._color_at(0, 0), "#ce9178")
        self.assertEqual(self._color_at(0, 6), "#ff0080")
        self.assertEqual(self._color_at(0, 10), "#6a9955")
        self.assertEqual(self._color_at(0, 19), "#858585")

    def test_highlights_multiline_comments_without_coloring_following_tokens(self):
        self.document.setPlainText("/* comment\nstill */ node2;;")
        self.highlighter.rehighlight()

        self.assertEqual(self._color_at(0, 2), "#858585")
        self.assertEqual(self._color_at(1, 3), "#858585")
        self.assertEqual(self._color_at(1, 9), "#ce9178")

    def test_highlights_link_content(self):
        self.document.setPlainText(
            "nrel_idtf -> (concept_A => [apple]);;"
        )
        self.highlighter.rehighlight()

        self.assertEqual(self._color_at(0, 30), "#c678dd")

    def test_highlights_identifiers_and_edges_while_expression_is_incomplete(self):
        self.document.setPlainText("node1 -> node2")
        self.highlighter.rehighlight()

        self.assertEqual(self._color_at(0, 0), "#ce9178")
        self.assertEqual(self._color_at(0, 6), "#ff0080")
        self.assertEqual(self._color_at(0, 9), "#ce9178")


if __name__ == "__main__":
    unittest.main()
