from importlib.resources import files
import json
import re
from src.resources.data import DEFAULT_THEME_CONFIG
from src.resources.icons import Icons


class ThemeManager:

    colors: dict[str, str] = {}
    last_used_theme: str = "dark"

    @classmethod
    def _load_json(cls, name: str) -> dict:
        """Load theme colors JSON from package resources."""
        try:
            text = files("src.resources.themes").joinpath(f"{name}.json").read_text(encoding="utf-8")
            return json.loads(text)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"ERROR: Cannot load theme colors '{name}': {e}")
            return DEFAULT_THEME_CONFIG.copy()

    @classmethod
    def _load_qss(cls, name: str) -> str:
        """Load theme QSS template from package resources."""
        try:
            return files("src.resources.themes").joinpath(f"{name}.qss").read_text(encoding="utf-8")
        except FileNotFoundError as e:
            print(f"ERROR: Cannot load theme QSS '{name}': {e}")
            return ""

    @classmethod
    def build_qss(cls, name: str) -> str:
        """Build complete QSS stylesheet from theme JSON + template."""
        cls.colors = cls._load_json(name)

        qss_template = cls._load_qss(name)
        if not qss_template:
            return ""

        qss = cls._render_qss(qss_template, cls.colors)
        cls.last_used_theme = name

        icon_color = cls.colors.get("icon_fg", "#d4d4d4")
        Icons.set_theme_color(icon_color)
        return qss

    @classmethod
    def set_last_used_theme(cls, name: str) -> None:
        """Set the last used theme name."""
        cls.last_used_theme = name

    @classmethod
    def _render_qss(cls, qss_template: str, colors: dict[str, str]) -> str:
        """Replace {{placeholder}} tokens in QSS template with color values."""
        def replace_placeholder(match):
            key = match.group(1)
            return colors.get(key, match.group(0))
        return re.sub(r"\{\{(\w+)\}\}", replace_placeholder, qss_template)

    @classmethod
    def get_color(cls, key: str) -> str:
        """Get a color value from the current theme."""
        return cls.colors.get(key, "#ffffff")

    @classmethod
    def list_themes(cls) -> list[str]:
        """Return list of available theme names from package resources."""
        try:
            themes_dir = files("src.resources.themes")
            return sorted(
                f.stem for f in themes_dir.iterdir()
                if f.is_file() and f.suffix == ".json"
            )
        except Exception:
            return ["dark", "light"]