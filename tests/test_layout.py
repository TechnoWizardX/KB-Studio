import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.gui.editor_workspace import EditorWorkspace


class SplitterHandleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_editor_splitter_has_a_visible_grab_handle(self):
        editor = EditorWorkspace()

        self.assertGreaterEqual(editor.splitter.handleWidth(), 6)
        self.assertFalse(editor.splitter.childrenCollapsible())

        editor.splitter.deleteLater()
        editor.deleteLater()
