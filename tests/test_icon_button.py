import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QSizePolicy

from src.gui.widgets import IconButton


class IconButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _icon() -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill()
        return QIcon(pixmap)

    def test_defaults_match_the_shared_stylesheet(self):
        button = IconButton(self._icon(), "Do something")

        self.assertEqual(button.objectName(), "IconButton")
        self.assertEqual(button.iconSize(), QSize(24, 24))
        self.assertEqual(button.size(), QSize(30, 30))
        self.assertEqual(
            button.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Fixed
        )
        self.assertEqual(
            button.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Fixed
        )
        self.assertEqual(button.toolTip(), "Do something")
        self.assertFalse(button.icon().isNull())

        button.deleteLater()

    def test_size_and_icon_size_can_be_overridden(self):
        button = IconButton(self._icon(), size=28, icon_size=18)

        self.assertEqual(button.size(), QSize(28, 28))
        self.assertEqual(button.iconSize(), QSize(18, 18))

        button.deleteLater()

    def test_click_emits_clicked(self):
        button = IconButton()
        spy = QSignalSpy(button.clicked)

        button.click()

        self.assertEqual(spy.count(), 1)
        button.deleteLater()

    def test_icon_is_optional(self):
        button = IconButton()

        self.assertTrue(button.icon().isNull())
        self.assertEqual(button.toolTip(), "")

        button.deleteLater()


if __name__ == "__main__":
    unittest.main()
