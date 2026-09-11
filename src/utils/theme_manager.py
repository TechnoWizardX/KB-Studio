from pathlib import Path
import json
import re
from src.resources.data import DEFAULT_THEME_CONFIG

class ThemeManager():

    
    colors: dict[str, str] = {}
    last_used_theme : str

    def init_theme(cls):
        pass
    
    def get_json_config(cls) -> dict[str, str]:
        if cls.colors:
            return cls.colors
        else:
            try:
                colors_file = cls._get_themes_dir() / f"{cls.last_used_theme}.json"
                with open(colors_file, "r", encoding="utf-8") as f:
                    cls.colors = json.load()
            except Exception as e:
                print(f"Can't load config: {e}. Returns reserve config")
                cls.colors = DEFAULT_THEME_CONFIG.copy()
        

    def _get_themes_dir() -> Path:
        return Path(__file__).parent.parent / "resources" / "themes"

    @classmethod
    def build_qss(cls, name: str) -> str:
        """Builds theme JSON + QSS, replaces {{placeholders}}, returns qss style config"""
        colors_file = cls._get_themes_dir() / f"{name}.json"
        qss_file = cls._get_themes_dir() / f"{name}.qss"

        try:
            with open(colors_file, "r", encoding="utf-8") as f:
                cls.colors = json.load(f)
        except Exception as e:
            print(f"ERROR: Cannot load theme colors '{name}': {e}")
            return

        try:
            with open(qss_file, "r", encoding="utf-8") as f:
                qss_template = f.read()
        except Exception as e:
            print(f"ERROR: Cannot load theme QSS '{name}': {e}")
            return

        qss = cls._render_qss(qss_template, cls.colors)
        cls.last_used_theme = name
        return qss

    @classmethod
    def set_last_used_theme(cls, name: str) -> None:
        cls.last_used_theme = name

    @classmethod
    def _render_qss(cls, qss_template: str, colors: dict[str, str]) -> str:
        def replace_placeholder(match):
            key = match.group(1)
            return colors.get(key, match.group(0))
        return re.sub(r"\{\{(\w+)\}\}", replace_placeholder, qss_template)

    @classmethod
    def get_color(cls, key: str) -> str:
        """Returns a color from current theme for SyntaxHighlighter / custom widgets"""
        return cls.colors.get(key, "#ffffff")

    def list_themes(self) -> list[str]:
        """Returns list of available theme names"""
        themes_dir = self._get_themes_dir()
        if not themes_dir.exists():
            return []
        return [f.stem for f in themes_dir.glob("*.json")]
