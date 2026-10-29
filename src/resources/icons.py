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
    def panel_bottom_fill(cls) -> QIcon:
        return cls._get("panel-bottom-fill", ":/icons/panel-bottom-fill.svg")

    @classmethod
    def panel_bottom(cls) -> QIcon:
        return cls._get("panel-bottom", ":/icons/panel-bottom.svg")
    
    @classmethod
    def panel_left_fill(cls) -> QIcon:
        return cls._get("panel-left-fill", ":/icons/panel-left-fill.svg")
    
    @classmethod
    def panel_left(cls) -> QIcon:
        return cls._get("panel-left", ":/icons/panel-left.svg")
    
    @classmethod
    def panel_right_fill(cls) -> QIcon:
        return cls._get("panel-right-fill", ":/icons/panel-right-fill.svg")
    
    @classmethod
    def panel_right(cls) -> QIcon:
        return cls._get("panel-right", ":/icons/panel-right.svg")
    
    @classmethod
    def file_add(cls) -> QIcon:
        return cls._get("file_add", ":/icons/file_add.svg")

    @classmethod
    def folder_add(cls) -> QIcon:
        return cls._get("folder_add", ":/icons/folder_add.svg")

    @classmethod
    def folder_search(cls) -> QIcon:
        return cls._get("folder_search", ":/icons/folder_search.svg")

    @classmethod
    def send(cls) -> QIcon:
        return cls._get("send", ":/icons/send.svg")

    @classmethod
    def cross(cls) -> QIcon:
        return cls._get("cross", ":/icons/cross.svg")

    @classmethod
    def plus(cls) -> QIcon:
        return cls._get("plus", ":/icons/plus.svg")

    @classmethod
    def settings(cls) -> QIcon:
        return cls._get("settings", ":/icons/settings.svg")

    @classmethod
    def new_graph(cls) -> QIcon:
        return cls._get("new_graph", ":/icons/new_graph.svg")

    @classmethod
    def save(cls) -> QIcon:
        return cls._get("save", ":/icons/save.svg")

    @classmethod
    def undo(cls) -> QIcon:
        return cls._get("undo", ":/icons/undo.svg")

    @classmethod
    def redo(cls) -> QIcon:
        return cls._get("redo", ":/icons/redo.svg")

    @classmethod
    def zoom_in(cls) -> QIcon:
        return cls._get("zoom_in", ":/icons/zoom_in.svg")

    @classmethod
    def zoom_out(cls) -> QIcon:
        return cls._get("zoom_out", ":/icons/zoom_out.svg")

    @classmethod
    def fit(cls) -> QIcon:
        return cls._get("fit", ":/icons/fit.svg")

    @classmethod
    def export_image(cls) -> QIcon:
        return cls._get("export_image", ":/icons/export_image.svg")

    @classmethod
    def find(cls) -> QIcon:
        return cls._get("find", ":/icons/find.svg")

    @classmethod
    def rename(cls) -> QIcon:
        return cls._get("rename", ":/icons/rename.svg")

    @classmethod
    def delete(cls) -> QIcon:
        return cls._get("delete", ":/icons/delete.svg")

    @classmethod
    def tool_select(cls) -> QIcon:
        return cls._get("tool_select", ":/icons/tool_select.svg")

    @classmethod
    def tool_node(cls) -> QIcon:
        return cls._get("tool_node", ":/icons/tool_node.svg")

    @classmethod
    def tool_connector(cls) -> QIcon:
        return cls._get("tool_connector", ":/icons/tool_connector.svg")

    @classmethod
    def tool_bus(cls) -> QIcon:
        return cls._get("tool_bus", ":/icons/tool_bus.svg")

    @classmethod
    def tool_contour(cls) -> QIcon:
        return cls._get("tool_contour", ":/icons/tool_contour.svg")

    @classmethod
    def arrange_grid(cls) -> QIcon:
        return cls._get("arrange_grid", ":/icons/arrange_grid.svg")

    @classmethod
    def arrange_vertical(cls) -> QIcon:
        return cls._get("arrange_vertical", ":/icons/arrange_vertical.svg")

    @classmethod
    def arrange_horizontal(cls) -> QIcon:
        return cls._get("arrange_horizontal", ":/icons/arrange_horizontal.svg")

    @classmethod
    def arrange_tuple(cls) -> QIcon:
        return cls._get("arrange_tuple", ":/icons/arrange_tuple.svg")