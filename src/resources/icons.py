from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt
import src.resources.resources_rc


def _recolor_icon(icon: QIcon, color: QColor) -> QIcon:
    """Возвращает копию иконки, перекрашенную в заданный цвет."""
    pixmap = icon.pixmap(24, 24)
    result = QPixmap(pixmap.size())
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(result.rect(), color)
    painter.end()
    return QIcon(result)


class Icons:
    _cache: dict[str, QIcon] = {}
    _color: QColor = QColor("#d4d4d4")  # дефолт — тёмная тема

    @classmethod
    def set_theme_color(cls, color: str | QColor):
        """Меняет цвет всех иконок (вызывать при смене темы)."""
        if isinstance(color, str):
            color = QColor(color)
        if color == cls._color:
            return
        cls._color = color
        cls._cache.clear()

    @classmethod
    def _get(cls, name: str, resource_path: str) -> QIcon:
        if name not in cls._cache:
            base = QIcon(resource_path)
            cls._cache[name] = _recolor_icon(base, cls._color)
        return cls._cache[name]

    @classmethod
    def file_add(cls) -> QIcon:
        return cls._get("file_add", ":/icons/file_add.svg")

    @classmethod
    def folder_add(cls) -> QIcon:
        return cls._get("folder_add", ":/icons/folder_add.svg")

    @classmethod
    def folder_search(cls) -> QIcon:
        return cls._get("folder_search", ":/icons/folder_search.svg")
