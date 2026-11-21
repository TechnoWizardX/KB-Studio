import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from src.core.signals import signals
from src.gui.settings import CountChangeSection, Settings
from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import ThemeManager


class _CounterSignal(QObject):
    value_changed = Signal(int)


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._previous_config = ConfigManager._current_config
        ConfigManager._current_config = ConfigManager.DEFAULT_CONFIG.copy()
        ConfigManager._current_config["theme"] = "dark"
        self._set_patcher = patch.object(ConfigManager, "set")
        self._set_mock = self._set_patcher.start()
        self.settings = Settings()

    def tearDown(self):
        self.settings.close()
        self.settings.deleteLater()
        self._set_patcher.stop()
        ConfigManager._current_config = self._previous_config
        self.app.setStyleSheet("")

    def test_active_theme_is_checked_and_only_one_theme_can_be_active(self):
        self.assertTrue(self.settings.theme_group.exclusive())
        self.assertTrue(self.settings.theme_dark_button.isChecked())
        self.assertFalse(self.settings.theme_light_button.isChecked())
        self.assertTrue(self.settings.theme_dark_button.isCheckable())

    def test_applying_a_theme_checks_its_button_and_emits_once(self):
        received = []

        def record(theme):
            received.append(theme)

        signals.theme_changed.connect(record)

        self.settings.apply_theme("light")
        self.app.processEvents()
        signals.theme_changed.disconnect(record)

        self.assertEqual(received, ["light"])
        self.assertTrue(self.settings.theme_light_button.isChecked())
        self.assertFalse(self.settings.theme_dark_button.isChecked())
        self._set_mock.assert_any_call("theme", "light")

    def test_count_sections_use_a_spin_box_and_save_immediately(self):
        counter = _CounterSignal()
        received = []
        counter.value_changed.connect(received.append)
        section = CountChangeSection(
            "Messages loaded at startup",
            "startup_message_count",
            100,
            counter.value_changed,
        )

        self.assertEqual(section._spin_box.value(), 100)
        section._spin_box.setValue(250)

        self.assertEqual(received, [250])
        self._set_mock.assert_any_call("startup_message_count", 250)
