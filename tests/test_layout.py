import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.gui.code_editor_widget import CodeEditorWidget


class SplitterHandleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_editor_splitter_has_a_visible_grab_handle(self):
        editor = CodeEditorWidget()

        self.assertGreaterEqual(editor.splitter.handleWidth(), 6)
        self.assertFalse(editor.splitter.childrenCollapsible())

        editor.splitter.deleteLater()
        editor.deleteLater()
