"""SCg scene items: node, connector, contour and bus graphics items.

Items know nothing about GraphScene (graph_scene.py imports them); scene
interaction happens through the deferred helper ``_graph_scene`` so the
import cycle graph_items -> graph_scene stays broken.
"""
from __future__ import annotations

import base64
import math
import xml.etree.ElementTree as ET
from collections.abc import Callable
from copy import deepcopy

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPixmap,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsTextItem,
)

from src.gui.graph_editor import scg_painter
from src.gui.graph_editor.graph_types import (
    node_type_parts as _node_type_parts,
)


def _graph_scene(scene: object):
    """scene, if it is a GraphScene (deferred import, see module docstring)."""
    from src.gui.graph_editor.graph_scene import GraphScene

    return scene if isinstance(scene, GraphScene) else None


class GraphNodeLabel(QGraphicsTextItem):
    committed = Signal(str)
    cancelled = Signal()

    def __init__(self, text: str, parent: QGraphicsItem):
        super().__init__(text, parent)
        self.original_text = text
        self._editing = False

    def start_editing(self) -> None:
        if self._editing:
            return
        self.original_text = self.toPlainText()
        self._editing = True
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextEditorInteraction
        )
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._stop_editing()
            self.committed.emit(self.toPlainText().strip())
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._stop_editing()
            self.cancelled.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        if self._editing:
            self._stop_editing()
            self.committed.emit(self.toPlainText().strip())

    def restore_text(self, text: str) -> None:
        self.setPlainText(text)

    def _stop_editing(self) -> None:
        self._editing = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        self.clearFocus()


class GraphNode(QGraphicsItem):
    ICON_SIZE = 30
    LABEL_GAP = 8
    CONTENT_GAP = 6
    CONTENT_PANEL_PAD = 12
    CONTENT_PANEL_MIN = 100
    CONTENT_PANEL_MAX = 240
    CONTENT_TEXT_INNER = 180

    def __init__(
        self,
        identifier: str,
        gwf_id: str = "",
        gwf_type: str = "node/const/general_node",
        gwf_idtf: str = "",
        gwf_element: ET.Element | None = None,
    ):
        super().__init__()
        self.identifier = identifier
        self.gwf_id = gwf_id
        self.gwf_type = gwf_type
        self.gwf_idtf = gwf_idtf
        self.gwf_element = gwf_element
        self._content_item: QGraphicsTextItem | None = None
        self._content_pixmap: QGraphicsPixmapItem | None = None
        self._panel_cache: tuple[tuple, QRectF | None] | None = None
        self._glyph_shape_cache: tuple | None = None
        self.content_expanded: bool = False
        self.label = GraphNodeLabel(gwf_idtf or identifier, self)
        self.label.setDefaultTextColor(QColor("#d4d4d4"))
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.label.document().documentLayout().documentSizeChanged.connect(
            self._position_label
        )
        self.label.committed.connect(self._on_label_committed)
        self.label.cancelled.connect(self._on_label_cancelled)
        self._refresh_content_viewer()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(1)
        self._position_label()
        self.rename_requester: Callable[..., None] | None = None
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        tooltip = f"{self.identifier}\n{self.gwf_type}"
        content_text = self._content_viewer_text()
        if content_text:
            preview = content_text.replace("\n", " ")[:120]
            tooltip += f"\n{preview}"
        self.setToolTip(tooltip)

    # --- content (attachments) ------------------------------------------------

    def content_element(self) -> ET.Element | None:
        return (
            self.gwf_element.find("content")
            if self.gwf_element is not None
            else None
        )

    def has_content(self) -> bool:
        element = self.content_element()
        return element is not None and element.get("type", "0") != "0"

    def _content_viewer_text(self) -> str:
        """Text put into the expanded content panel for visible content."""
        element = self.content_element()
        if element is None or element.get("type", "0") == "0":
            return ""
        c_type = element.get("type", "0")
        if c_type in {"1", "2", "3"}:
            return (element.text or "").strip()
        file_name = element.get("file_name", "") or "file"
        if self._content_image() is not None:
            return ""
        raw = element.text or ""
        padding = int(raw.endswith("==")) + int(raw.endswith("="))
        size = max(0, len(raw) * 3 // 4 - padding)
        return f"📎 {file_name} ({size} B)"

    def _content_image(self) -> QImage | None:
        """Decoded image for file content whose MIME type is an image."""
        element = self.content_element()
        if element is None or element.get("type", "0") != "4":
            return None
        if not element.get("mime_type", "").startswith("image/"):
            return None
        try:
            raw = base64.b64decode(element.text or "")
        except ValueError:
            return None
        image = QImage.fromData(raw)
        return None if image.isNull() else image

    def _content_font(self) -> QFont:
        font = QFont()
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1.0))
        return font

    def _content_panel_rect(self) -> QRectF | None:
        """Square glyph shown instead of the node body in expanded mode.

        Active only when this node's display mode is expanded (toggled with C)
        and the content itself is visible according to ``content_visibility``.
        The size fits the payload: an image is shown as is (scaled to fit),
        strings and file labels are wrapped at the inner width.
        """
        if not self.content_expanded:
            return None
        element = self.content_element()
        if (
            element is None
            or element.get("type", "0") == "0"
            or element.get("content_visibility", "false") != "true"
        ):
            return None
        key = (
            element.get("type", "0"),
            element.get("mime_type", ""),
            element.get("file_name", ""),
            element.text or "",
        )
        if self._panel_cache is not None and self._panel_cache[0] == key:
            return self._panel_cache[1]
        image = self._content_image()
        side = self._measure_content_side(image)
        rect = QRectF(-side / 2, -side / 2, side, side)
        self._panel_cache = (key, rect)
        return rect

    def _measure_content_side(self, image: QImage | None) -> float:
        """Square side fitting the payload with matching text wrap width."""
        if image is not None:
            return min(
                max(max(image.width(), image.height()) + 2
                    * self.CONTENT_PANEL_PAD, self.CONTENT_PANEL_MIN),
                self.CONTENT_PANEL_MAX,
            )
        probe = QTextDocument()
        probe.setDefaultFont(self._content_font())
        text = self._content_viewer_text() or " "
        width = self.CONTENT_TEXT_INNER
        side = self.CONTENT_PANEL_MIN
        # two passes: the wrap width follows the panel size and back
        for _ in range(2):
            probe.setPlainText(text)
            probe.setTextWidth(width)
            side = min(
                max(
                    probe.size().height() + 2 * self.CONTENT_PANEL_PAD + 6,
                    self.CONTENT_PANEL_MIN,
                ),
                self.CONTENT_PANEL_MAX,
            )
            width = side - 2 * self.CONTENT_PANEL_PAD
        return side

    def _body_rect(self) -> QRectF:
        """Glyph square: the expanded content panel or the plain glyph."""
        return self._content_panel_rect() or self._glyph_rect()

    def set_node_content(self, content: ET.Element) -> None:
        """Replace the ``<content>`` subtree of this node."""
        self.prepareGeometryChange()
        self._panel_cache = None
        if self.gwf_element is None:
            self.gwf_element = ET.Element("node")
        old = self.gwf_element.find("content")
        if old is not None:
            self.gwf_element.remove(old)
        self.gwf_element.append(deepcopy(content))
        self._refresh_content_viewer()
        self._position_label()
        self._update_tooltip()
        self.update()

    def refresh_content_display(self) -> None:
        """Rebuild the content visuals after a scene display mode change."""
        self.prepareGeometryChange()
        self._panel_cache = None
        self._refresh_content_viewer()
        self._position_label()
        self.update()

    def _refresh_content_viewer(self) -> None:
        """Show, hide or update the content inside the expanded panel."""
        panel = self._content_panel_rect()
        if panel is None:
            if self._content_item is not None:
                self._content_item.setVisible(False)
            if self._content_pixmap is not None:
                self._content_pixmap.setVisible(False)
            return
        image = self._content_image()
        inner = panel.width() - 2 * self.CONTENT_PANEL_PAD
        if image is not None:
            if self._content_pixmap is None:
                self._content_pixmap = QGraphicsPixmapItem(self)
            self._content_pixmap.setPixmap(
                QPixmap.fromImage(
                    image.scaled(
                        int(inner),
                        int(inner),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            )
            self._content_pixmap.setVisible(True)
            if self._content_item is not None:
                self._content_item.setVisible(False)
        else:
            if self._content_item is None:
                self._content_item = QGraphicsTextItem(self)
                self._content_item.setDefaultTextColor(QColor("#c9d1d9"))
                self._content_item.setFont(self._content_font())
                self._content_item.setAcceptedMouseButtons(
                    Qt.MouseButton.NoButton
                )
                self._content_item.document().documentLayout().documentSizeChanged.connect(
                    self._position_content
                )
            self._content_item.setPlainText(self._content_viewer_text())
            self._content_item.setTextWidth(inner)
            self._content_item.setVisible(True)
            if self._content_pixmap is not None:
                self._content_pixmap.setVisible(False)
        self._position_content()

    def _position_content(self, *_document_size) -> None:
        self.prepareGeometryChange()
        panel = self._content_panel_rect()
        if panel is None:
            return
        center = panel.center()
        if self._content_pixmap is not None and self._content_pixmap.isVisible():
            size = self._content_pixmap.pixmap().size()
            self._content_pixmap.setZValue(0)
            self._content_pixmap.setPos(
                center - QPointF(size.width(), size.height()) / 2
            )
        elif (
            self._content_item is not None
            and self._content_item.isVisible()
        ):
            bounds = self._content_item.boundingRect()
            self._content_item.setPos(
                center - QPointF(bounds.width(), bounds.height()) / 2
            )

    def boundingRect(self):
        bounds = self._body_rect().adjusted(-2, -2, 2, 2).united(self._label_rect())
        return bounds

    def shape(self) -> QPainterPath:
        path = self._glyph_shape()
        path.addRect(self._label_rect())
        return path

    def _label_rect(self) -> QRectF:
        return self.label.boundingRect().translated(self.label.pos())

    def _position_label(self, *_document_size) -> None:
        self.prepareGeometryChange()
        text_rect = self.label.boundingRect()
        self.label.setPos(
            self._body_rect().width() / 2 + self.LABEL_GAP,
            -text_rect.center().y(),
        )

    def _glyph_rect(self) -> QRectF:
        half_size = self.ICON_SIZE / 2
        return QRectF(-half_size, -half_size, self.ICON_SIZE, self.ICON_SIZE)

    def _glyph_shape(self) -> QPainterPath:
        panel = self._content_panel_rect()
        if panel is not None:
            key = ("panel", panel.width(), panel.height())
            if self._glyph_shape_cache is not None and (
                self._glyph_shape_cache[0] == key
            ):
                path = QPainterPath(self._glyph_shape_cache[1])
                return path
            path = QPainterPath()
            path.addRoundedRect(panel, 6, 6)
            self._glyph_shape_cache = (key, path)
            return path
        if self._glyph_shape_cache is not None and (
            self._glyph_shape_cache[0] == self.gwf_type
        ):
            return QPainterPath(self._glyph_shape_cache[1])
        permanence, structure = _node_type_parts(self.gwf_type)
        path = scg_painter.node_shape(self._glyph_rect(), permanence, structure)
        self._glyph_shape_cache = (self.gwf_type, path)
        return path

    def connection_point(self, target: QPointF) -> QPointF:
        center = QPointF(0, 0)
        target_local = self.mapFromScene(target)
        direction = target_local - center
        if not direction.x() and not direction.y():
            return self.mapToScene(center)

        path = self._glyph_shape()
        low, high = 0.0, 1.0
        # 12 bisections give ~1/4096 precision of the ray (≈0.7px at a
        # 3000px offset) — imperceptible for arrow anchors, but ~3× cheaper
        # than the previous 32: during a multi-select drag every edge runs
        # this twice per frame.
        for _ in range(12):
            mid = (low + high) / 2
            if path.contains(center + direction * mid):
                low = mid
            else:
                high = mid
        return self.mapToScene(center + direction * low)

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        permanence, structure = _node_type_parts(self.gwf_type)
        # border colour encodes the constancy side, like sc-web themes do:
        # constants are near white, variables blue-violet, meta violet
        if self.isSelected():
            color = QColor("#ffa657")
        elif self.gwf_type.startswith("node/meta"):
            color = QColor("#d2a8ff")
        elif self.gwf_type.startswith("node/var"):
            color = QColor("#79c0ff")
        else:
            color = QColor("#e6e6e6")
        if structure == "not_define":
            color = QColor("#d4d4d4")
        glyph = self._body_rect()
        painter.save()
        panel = self._content_panel_rect()
        if panel is not None:
            # expanded content form: a square glyph carrying the content
            painter.setPen(QPen(color, 3))
            painter.setBrush(QBrush(scg_painter.NODE_FILL))
            painter.drawRoundedRect(panel, 6, 6)
            painter.restore()
            return
        scg_painter.paint_node(painter, glyph, color, permanence, structure)
        painter.restore()
        if self.has_content():
            painter.save()
            painter.setBrush(QBrush(QColor("#cc66ff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(glyph.right() - 5, glyph.bottom() - 5, 5, 5))
            painter.restore()

    def set_identifier(self, identifier: str) -> None:
        self.prepareGeometryChange()
        self.identifier = identifier
        self.gwf_idtf = identifier
        self.label.setPlainText(identifier)
        self._position_label()
        self._update_tooltip()
        self.update()

    def itemChange(self, change, value):
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            scene = self.scene()
            if _graph_scene(scene) is not None:
                scene.node_moved(self)
        return result

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.label.start_editing()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _on_label_committed(self, text: str) -> None:
        if text == self.identifier:
            self.label.restore_text(self.identifier)
            return
        if self.rename_requester is None:
            self.label.restore_text(self.identifier)
            return
        self.rename_requester(self, text)

    def _on_label_cancelled(self) -> None:
        self.label.restore_text(self.identifier)


class GraphEdge(QGraphicsPathItem):
    WAYPOINT_HANDLE_HALF = 3.5
    DOT_HANDLE_RADIUS = 8.0

    def __init__(
        self,
        source: GraphNode | GraphEdge,
        target: GraphNode | GraphEdge,
        edge_type: str,
        gwf_id: str = "",
        gwf_type: str = "arc/-/-",
        gwf_tag: str = "arc",
        gwf_element: ET.Element | None = None,
        waypoints: list[QPointF] | None = None,
        begin_dot: float = 0.0,
        end_dot: float = 0.0,
    ):
        super().__init__()
        self.source = source
        self.target = target
        self.edge_type = edge_type
        self.gwf_id = gwf_id
        self.gwf_type = gwf_type
        self.gwf_tag = gwf_tag
        self.gwf_element = gwf_element
        self.waypoints = waypoints or []
        self.begin_dot = (
            float(gwf_element.get("dotBBalance", "0"))
            if gwf_element is not None
            else begin_dot
        )
        self.end_dot = (
            float(gwf_element.get("dotEBalance", "0"))
            if gwf_element is not None
            else end_dot
        )
        self.setZValue(0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.waypoints_requester: Callable[..., None] | None = None
        self.dots_requester: Callable[..., None] | None = None
        self._drag_waypoint: int | None = None
        self._drag_original_waypoints: list[QPointF] | None = None
        self._drag_dot_side: str | None = None
        self._drag_original_dots: tuple[float, float] | None = None
        self.setToolTip(f"{gwf_tag}: {gwf_type} ({edge_type})")
        self.update_path()

    def update_path(self) -> None:
        # first pass: dot-balanced sides (connectors and buses) attach at
        # their stored dot; shape sides aim at the other side's centre
        target_initial_toward = (
            self.waypoints[-1] if self.waypoints
            else self._endpoint_center(self.source)
        )
        end = self._endpoint_connection_point(
            self.target, target_initial_toward, self.end_dot
        )
        # second pass: every shape side aims at the actual attach point of
        # the other side, so the connector approaches the border radially
        # (towards the attach junction) instead of grazing it tangentially
        source_toward = (
            self.waypoints[0] if self.waypoints else end
        )
        start = self._endpoint_connection_point(
            self.source, source_toward, self.begin_dot
        )
        if not self.waypoints:
            end = self._endpoint_connection_point(self.target, start, self.end_dot)
        path = QPainterPath(start)
        for waypoint in self.waypoints:
            path.lineTo(waypoint)
        path.lineTo(end)
        self.setPath(path)
        # connectors attached to other connectors must paint above their
        # parents, otherwise parent lines cover the arrowheads
        attached = isinstance(self.source, GraphEdge) or isinstance(
            self.target, GraphEdge
        )
        self.setZValue(1.5 if attached else 0.0)

    @staticmethod
    def _endpoint_center(endpoint: GraphNode | GraphEdge) -> QPointF:
        if isinstance(endpoint, GraphNode):
            return endpoint.mapToScene(QPointF(0, 0))
        if isinstance(endpoint, GraphAuxObject) and endpoint.is_contour():
            return endpoint.mapToScene(endpoint.path().boundingRect().center())
        path = endpoint.mapToScene(endpoint.path())
        return path.pointAtPercent(0.5)

    def begin_element_point(self) -> QPointF:
        """GWF b_x/b_y coordinate: anchor point of the connector start."""
        return self._element_point(True)

    def end_element_point(self) -> QPointF:
        """GWF e_x/e_y coordinate: anchor point of the connector end."""
        return self._element_point(False)

    def _element_point(self, begin: bool) -> QPointF:
        endpoint = self.source if begin else self.target
        if isinstance(endpoint, GraphNode):
            return endpoint.scenePos()
        if isinstance(endpoint, GraphEdge):
            # Edge items live in scene coordinates anchored at (0, 0), so
            # scenePos is meaningless: export the drawn attach point on the
            # parent connector path (same dot the GWF balance encodes).
            if endpoint.path().isEmpty():
                return endpoint.scenePos()
            return endpoint.cross(self.begin_dot if begin else self.end_dot)
        path = self.path()
        if path.isEmpty():
            return self._endpoint_center(endpoint)
        element = path.elementAt(0 if begin else path.elementCount() - 1)
        return self.mapToScene(QPointF(element.x, element.y))

    @staticmethod
    def _endpoint_connection_point(
        endpoint: GraphNode | GraphEdge | GraphAuxObject,
        toward: QPointF,
        dot: float,
    ) -> QPointF:
        if isinstance(endpoint, GraphNode):
            return endpoint.connection_point(toward)
        if isinstance(endpoint, GraphAuxObject):
            if endpoint.kind == "bus":
                # kbe: connectors attach to bus polyline dots, like arcs
                # attached to other point objects
                return endpoint.cross(dot)
            return endpoint.connection_point(toward)
        return endpoint.cross(dot)

    def connection_point(self, toward: QPointF) -> QPointF:
        return self.cross(self.dot_position(toward))

    def dot_position(self, point: QPointF) -> float:
        return _scene_path_dot_position(self.mapToScene(self.path()), point)

    def cross(self, dot: float) -> QPointF:
        return _scene_path_cross(self.mapToScene(self.path()), dot)

    def boundingRect(self):
        return self.path().boundingRect().adjusted(-15, -18, 15, 18)

    def _waypoint_index_at(
        self, point: QPointF, radius: float = 9.0
    ) -> int | None:
        for index, waypoint in enumerate(self.waypoints):
            if QLineF(point, waypoint).length() <= radius:
                return index
        return None

    def _dot_handle_at(self, point: QPointF) -> str | None:
        """Возвращает 'begin'/'end', если точка у ручки крепления на коннекторе."""
        line = self.path()
        if line.isEmpty():
            return None
        for side, percent in (("begin", 0.0), ("end", 1.0)):
            endpoint = self.source if side == "begin" else self.target
            if not isinstance(endpoint, GraphEdge) and (
                not isinstance(endpoint, GraphAuxObject)
                or endpoint.kind != "bus"
            ):
                # only endpoints whose dot is honoured on repaint
                continue
            anchor = line.pointAtPercent(percent)
            if QLineF(point, anchor).length() <= self.DOT_HANDLE_RADIUS:
                return side
        return None

    def _apply_dragged_dot(self, dot: float) -> None:
        side = self._drag_dot_side
        endpoint = self.source if side == "begin" else self.target
        if isinstance(endpoint, (GraphEdge, GraphAuxObject)):
            # the dot travels along the parent polyline
            parent_path = endpoint.mapToScene(endpoint.path())
            max_dot = max(parent_path.elementCount() - 1, 1)
            dot = min(max(dot, 0.0), max_dot)
        if side == "begin":
            self.begin_dot = dot
        else:
            self.end_dot = dot
        self.update_path()
        self.update()

    def _change_dots(
        self, old_dots: tuple[float, float], new_dots: tuple[float, float]
    ) -> None:
        self.begin_dot, self.end_dot = new_dots
        self.update_path()
        scene = self.scene()
        if _graph_scene(scene) is not None:
            scene.connector_changed(self)
        self.update()

    def _waypoint_insert_index(self, point: QPointF) -> int:
        scene_path = self.mapToScene(self.path())
        best_index = 0
        best_distance = math.inf
        for index in range(scene_path.elementCount() - 1):
            first = scene_path.elementAt(index)
            second = scene_path.elementAt(index + 1)
            start = QPointF(first.x, first.y)
            end = QPointF(second.x, second.y)
            vector = end - start
            length_squared = vector.x() ** 2 + vector.y() ** 2
            if not length_squared:
                candidate = start
            else:
                fraction = max(
                    0.0,
                    min(
                        1.0,
                        ((point.x() - start.x()) * vector.x()
                         + (point.y() - start.y()) * vector.y())
                        / length_squared,
                    ),
                )
                candidate = start + vector * fraction
            delta = point - candidate
            distance = delta.x() ** 2 + delta.y() ** 2
            if distance < best_distance:
                best_distance = distance
                best_index = index
        return best_index

    def _change_waypoints(self, old: list[QPointF], new: list[QPointF]) -> None:
        self.waypoints = [QPointF(point) for point in new]
        self.update_path()
        scene = self.scene()
        if _graph_scene(scene) is not None:
            scene._refresh_connected_edges(self, set())
            scene.connector_changed(self)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        index = self._waypoint_index_at(event.scenePos())
        if index is not None:
            self.setSelected(True)
            self._drag_waypoint = index
            self._drag_original_waypoints = [
                QPointF(point) for point in self.waypoints
            ]
            event.accept()
            return
        side = self._dot_handle_at(event.scenePos())
        if side is not None:
            self.setSelected(True)
            self._drag_dot_side = side
            self._drag_original_dots = (self.begin_dot, self.end_dot)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_waypoint is not None:
            self.waypoints[self._drag_waypoint] = QPointF(event.scenePos())
            self.update_path()
            scene = self.scene()
            if _graph_scene(scene) is not None:
                scene._refresh_connected_edges(self, set())
            self.update()
            event.accept()
            return
        if self._drag_dot_side is not None:
            self._apply_dragged_dot(self.dot_position(event.scenePos()))
            scene = self.scene()
            if _graph_scene(scene) is not None:
                scene._refresh_connected_edges(self, set())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_waypoint is not None:
            self._drag_waypoint = None
            old_list = self._drag_original_waypoints
            self._drag_original_waypoints = None
            new_list = [QPointF(point) for point in self.waypoints]
            if (
                self.waypoints_requester is not None
                and old_list is not None
                and old_list != new_list
            ):
                self.waypoints_requester(self, old_list, new_list)
            event.accept()
            return
        if self._drag_dot_side is not None:
            self._drag_dot_side = None
            old_dots = self._drag_original_dots
            self._drag_original_dots = None
            new_dots = (self.begin_dot, self.end_dot)
            if (
                self.dots_requester is not None
                and old_dots is not None
                and new_dots != old_dots
            ):
                self.dots_requester(self, old_dots, new_dots)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            old = [QPointF(point) for point in self.waypoints]
            index = self._waypoint_index_at(event.scenePos())
            if index is not None:
                new = (
                    old[:index]
                    + old[index + 1 :]
                )
            elif self.shape().contains(event.pos()):
                insert_index = self._waypoint_insert_index(event.scenePos())
                new = old[:insert_index] + [QPointF(event.scenePos())] + old[insert_index:]
            else:
                super().mouseDoubleClickEvent(event)
                return
            self._change_waypoints(old, new)
            if self.waypoints_requester is not None:
                self.waypoints_requester(self, old, new)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self.path())

    def _is_oriented_type(self) -> bool:
        return (
            self.gwf_tag == "arc"
            or self.gwf_type.endswith("/orient")
            or "/orient/" in self.gwf_type
        )

    def _edge_style(self) -> scg_painter.ScgEdgeStyle:
        return scg_painter.ScgEdgeStyle.from_connector(self.gwf_tag, self.gwf_type)

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        line = self.path()
        if line.isEmpty():
            return
        color = QColor("#ffa657") if self.isSelected() else QColor("#c9d1d9")
        style = self._edge_style()
        painter.save()
        scg_painter.paint_edge(painter, line, style, color)
        painter.restore()
        if not style.has_distinct_visual:
            # Connector types without their own SCg form carry their SCs token
            # next to the line instead.
            painter.save()
            painter.setPen(QColor("#d4d4d4"))
            painter.drawText(
                line.pointAtPercent(0.5) + QPointF(5, -5), self.edge_type
            )
            painter.restore()
        if self.isSelected():
            pen = QPen(QColor("#ffa657"), 1)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor("#ffffff")))
            half = self.WAYPOINT_HANDLE_HALF
            for waypoint in self.waypoints:
                painter.drawRect(
                    QRectF(
                        waypoint.x() - half,
                        waypoint.y() - half,
                        half * 2,
                        half * 2,
                    )
                )
            for side, percent in (("begin", 0.0), ("end", 1.0)):
                endpoint = self.source if side == "begin" else self.target
                if not isinstance(endpoint, (GraphEdge, GraphAuxObject)):
                    continue
                anchor = line.pointAtPercent(percent)
                painter.drawEllipse(
                    anchor, self.DOT_HANDLE_RADIUS, self.DOT_HANDLE_RADIUS
                )


class GraphAuxObject(QGraphicsPathItem):
    def __init__(
        self, kind: str, element: ET.Element, owner: GraphNode | None = None
    ):
        super().__init__()
        self.kind = kind
        self.gwf_element = deepcopy(element)
        self.owner = owner
        self.gwf_id = element.get("id", "")
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(-1 if kind == "contour" else 0)

        path = QPainterPath()
        if kind == "bus":
            path.moveTo(float(element.get("b_x", "0")), float(element.get("b_y", "0")))
            for point in element.findall("./points/point"):
                path.lineTo(float(point.get("x", "0")), float(point.get("y", "0")))
            path.lineTo(float(element.get("e_x", "0")), float(element.get("e_y", "0")))
        else:
            points = [
                QPointF(float(point.get("x", "0")), float(point.get("y", "0")))
                for point in element.findall("./points/point")
            ]
            if points:
                path.moveTo(points[0])
                for point in points[1:]:
                    path.lineTo(point)
                path.closeSubpath()
        self.setPath(path)
        if kind == "bus":
            # solid and clearly visible, as the kbe bus (a 5 px solid line)
            self.setPen(QPen(QColor("#c9d1d9"), 2))
        else:
            self.setPen(QPen(QColor("#8b949e"), 1, Qt.PenStyle.DashLine))
        self.setBrush(Qt.BrushStyle.NoBrush)

    def is_contour(self) -> bool:
        return self.kind == "contour"

    def dot_position(self, point: QPointF) -> float:
        """Nearest polyline dot to ``point`` (kbe SCgBus::dotPos)."""
        return _scene_path_dot_position(self.mapToScene(self.path()), point)

    def cross(self, dot: float) -> QPointF:
        """Scene point at polyline ``dot`` (kbe SCgBus::cross)."""
        return _scene_path_cross(self.mapToScene(self.path()), dot)

    def connection_point(self, target: QPointF) -> QPointF:
        """Attachment point: on the bus polyline or the contour border."""
        if self.kind == "bus":
            scene_path = self.mapToScene(self.path())
            if scene_path.elementCount() < 2:
                return self.mapToScene(self.path().boundingRect().center())
            return _scene_path_cross(
                scene_path, _scene_path_dot_position(scene_path, target)
            )
        center = self.path().boundingRect().center()
        target_local = self.mapFromScene(target)
        ray = QLineF(center, target_local)
        if ray.length() == 0:
            return self.mapToScene(center)
        best_point: QPointF | None = None
        best_distance = math.inf
        segment_count = self.path().elementCount() - 1
        for index in range(segment_count):
            first = self.path().elementAt(index)
            second = self.path().elementAt(index + 1)
            start = QPointF(first.x, first.y)
            end = QPointF(second.x, second.y)
            intersection_type, intersection_point = ray.intersects(
                QLineF(start, end)
            )
            if (
                intersection_type != QLineF.IntersectionType.BoundedIntersection
            ):
                continue
            distance = QLineF(center, intersection_point).length()
            if distance > 1e-6 and distance < best_distance:
                best_distance = distance
                best_point = intersection_point
        if best_point is None:
            return self.mapToScene(center)
        return self.mapToScene(best_point)

    def itemChange(self, change, value):
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            scene = self.scene()
            if _graph_scene(scene) is not None and not scene._loading:
                if self.kind == "bus":
                    # dragging the bus keeps its start glued to the owner node
                    scene._glue_bus_start(self)
                scene._refresh_connected_edges(self, set())
                if not scene._in_drag:
                    scene._update_scene_rect()
                    scene.model_changed.emit()
        return result

    def to_gwf_element(self) -> ET.Element:
        element = deepcopy(self.gwf_element)
        points = element.find("points")
        if points is None:
            points = ET.SubElement(element, "points")
        else:
            points.clear()
        scene_path = self.mapToScene(self.path())
        path_points = [
            scene_path.elementAt(index)
            for index in range(scene_path.elementCount())
        ]
        if self.kind == "bus" and len(path_points) >= 2:
            first, last = path_points[0], path_points[-1]
            element.attrib.update(
                {
                    "b_x": str(round(first.x, 3)),
                    "b_y": str(round(first.y, 3)),
                    "e_x": str(round(last.x, 3)),
                    "e_y": str(round(last.y, 3)),
                }
            )
            path_points = path_points[1:-1]
        elif (
            self.kind == "contour"
            and len(path_points) > 1
            and path_points[0].x == path_points[-1].x
            and path_points[0].y == path_points[-1].y
        ):
            path_points.pop()
        for point in path_points:
            ET.SubElement(
                points,
                "point",
                {"x": str(round(point.x, 3)), "y": str(round(point.y, 3))},
            )
        return element


def _scene_path_dot_position(scene_path: QPainterPath, point: QPointF) -> float:
    """Dot of a polyline path nearest to ``point`` (kbe SCgPair::dotPos)."""
    if scene_path.elementCount() < 2:
        return 0.0

    closest_dot = 0.0
    closest_distance = math.inf
    for index in range(scene_path.elementCount() - 1):
        first = scene_path.elementAt(index)
        second = scene_path.elementAt(index + 1)
        start = QPointF(first.x, first.y)
        end = QPointF(second.x, second.y)
        vector = end - start
        length_squared = vector.x() ** 2 + vector.y() ** 2
        if not length_squared:
            fraction = 0.0
            candidate = start
        else:
            offset = point - start
            fraction = max(
                0.0,
                min(
                    1.0,
                    (offset.x() * vector.x() + offset.y() * vector.y())
                    / length_squared,
                ),
            )
            candidate = start + vector * fraction
        delta = point - candidate
        distance = delta.x() ** 2 + delta.y() ** 2
        if distance < closest_distance:
            closest_distance = distance
            closest_dot = index + fraction
    return closest_dot


def _scene_path_cross(scene_path: QPainterPath, dot: float) -> QPointF:
    """Scene point at ``dot`` segment-position on a polyline (kbe SCgObject::cross)."""
    count = scene_path.elementCount()
    if count < 2:
        return scene_path.elementAt(0) if count else QPointF()
    if dot >= count - 1:
        segment, fraction = count - 2, 1.0
    elif dot <= 0:
        segment, fraction = 0, 0.0
    else:
        segment = int(dot)
        fraction = dot - segment
    first = scene_path.elementAt(segment)
    second = scene_path.elementAt(segment + 1)
    start = QPointF(first.x, first.y)
    end = QPointF(second.x, second.y)
    return start + (end - start) * fraction


def _is_connector_endpoint(item: object) -> bool:
    """Connectors may attach to nodes, other connectors, contours and buses."""
    return isinstance(item, (GraphNode, GraphEdge, GraphAuxObject))
