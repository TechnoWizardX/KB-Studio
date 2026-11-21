import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.utils.theme_manager import ThemeManager


class ThemeManagerTests(unittest.TestCase):
    def test_every_placeholder_is_rendered(self):
        for name in ("dark", "light"):
            with self.subTest(theme=name):
                qss = ThemeManager.build_qss(name)
                self.assertNotIn("{{", qss)
                self.assertIn(f"chevron_down_{name}.svg", qss)
