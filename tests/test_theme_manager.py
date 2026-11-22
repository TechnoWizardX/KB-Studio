import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.utils.theme_manager import ThemeManager


class ThemeManagerTests(unittest.TestCase):
    def test_every_placeholder_is_rendered(self):
        for name in ThemeManager.list_themes():
            with self.subTest(theme=name):
                qss = ThemeManager.build_qss(name)
                self.assertNotIn("{{", qss)
                expected_variant = "light" if name in ("light", "solarized_light") else "dark"
                self.assertIn(f"chevron_down_{expected_variant}.svg", qss)
