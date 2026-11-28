import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.gui.widgets import ElidedLabel


class ElidedLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_label(self, text: str, width: int) -> ElidedLabel:
        label = ElidedLabel(text)
        # Lay the label out without mapping a real top-level window: showing
        # an offscreen window would steal focus from later shortcut tests.
        label.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        label.resize(width, 24)
        label.show()
        self.app.processEvents()
        return label

    def _dispose(self, label: ElidedLabel) -> None:
        label.close()
        label.deleteLater()
        self.app.processEvents()

    def test_short_text_is_shown_unchanged(self):
        label = self._make_label("short", 200)

        self.assertEqual(label.text(), "short")
        self.assertEqual(label.full_text(), "short")
        self.assertEqual(label.toolTip(), "short")

        self._dispose(label)

    def test_long_text_is_elided_and_kept_in_the_tooltip(self):
        text = "/home/user/very/long/path/to/some/project/folder"
        label = self._make_label(text, 120)

        self.assertIn("\u2026", label.text())
        self.assertEqual(label.full_text(), text)
        self.assertEqual(label.toolTip(), text)

        self._dispose(label)

    def test_set_text_updates_elision_and_tooltip(self):
        label = ElidedLabel("old")
        label.setText("new value")

        self.assertEqual(label.full_text(), "new value")
        self.assertEqual(label.toolTip(), "new value")

        label.deleteLater()


if __name__ == "__main__":
    unittest.main()
