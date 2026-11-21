import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from src.gui.toolbar import SideBarShowButton
from src.resources.icons import Icons
from src.utils.config_manager import ConfigManager


class IconRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_icons_have_pixmaps_for_every_button_size(self):
        icon = Icons.settings()

        for size in (16, 20, 24, 30, 32):
            with self.subTest(size=size):
                pixmap = icon.pixmap(QSize(size, size))
                self.assertFalse(pixmap.isNull())
                self.assertEqual(pixmap.size(), QSize(size, size))


class ToolbarTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._previous_config = ConfigManager._current_config
        ConfigManager._current_config = ConfigManager.DEFAULT_CONFIG.copy()
        self._set_patcher = patch.object(ConfigManager, "set")
        self._set_patcher.start()

    def tearDown(self):
        self._set_patcher.stop()
        ConfigManager._current_config = self._previous_config

    def test_sidebar_buttons_say_what_they_show_and_hide(self):
        button = SideBarShowButton("show_left_bar", True)

        self.assertEqual(button.toolTip(), "Hide the project file tree")
        self.assertEqual(button.accessibleName(), button.toolTip())

        button.on_clicked()

        self.assertEqual(button.toolTip(), "Show the project file tree")
        self.assertEqual(button.accessibleName(), button.toolTip())
        button.deleteLater()
