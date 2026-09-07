from PySide6.QtWidgets import QApplication
from pathlib import Path
from typing import Any
import json
import re


class ThemeManager():

    def __init__(self, app: QApplication):
        self.app = app
        self.colors: dict[str, str] = {}

    def _get_themes_dir(self) -> Path:
        return Path(__file__).parent.parent / "resources" / "themes"

    def apply(self, name: str) -> None:
        """Loads theme JSON + QSS, replaces {{placeholders}}, applies to QApplication"""
        colors_file = self._get_themes_dir() / f"{name}.json"
        qss_file = self._get_themes_dir() / f"{name}.qss"

        try:
            with open(colors_file, "r", encoding="utf-8") as f:
                self.colors = json.load(f)
        except Exception as e:
            print(f"ERROR: Cannot load theme colors '{name}': {e}")
            return

        try:
            with open(qss_file, "r", encoding="utf-8") as f:
                qss_template = f.read()
        except Exception as e:
            print(f"ERROR: Cannot load theme QSS '{name}': {e}")
            return

        qss = self._render_qss(qss_template, self.colors)
        self.app.setStyleSheet(qss)

    def _render_qss(self, qss_template: str, colors: dict[str, str]) -> str:
        def replace_placeholder(match):
            key = match.group(1)
            return colors.get(key, match.group(0))
        return re.sub(r"\{\{(\w+)\}\}", replace_placeholder, qss_template)

    def get_color(self, key: str) -> str:
        """Returns a color from current theme for SyntaxHighlighter / custom widgets"""
        return self.colors.get(key, "#ffffff")

    def list_themes(self) -> list[str]:
        """Returns list of available theme names"""
        themes_dir = self._get_themes_dir()
        if not themes_dir.exists():
            return []
        return [f.stem for f in themes_dir.glob("*.json")]
