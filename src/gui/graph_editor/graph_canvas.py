from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QLineF, QPointF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

CONTOUR_SNAP_RADIUS_PX = 12.0


class GraphCanvasView(QGraphicsView):
    tool_error = Signal(str)
    tool_changed = Signal(str)

    SELECT = "select"
    NODE = "node"
    CONNECTOR = "connector"
    BUS = "bus"
    CONTOUR = "contour"

    def __init__(
        self,
        scene: QGraphicsScene,
        node_class: type,
        connector_class: type,
        create_node: Callable[[QPointF], object],
        create_connector: Callable[[object, object, QPointF, QPointF], None],
        create_bus: Callable[[object, QPointF], None],
        create_contour: Callable[[list[QPointF]], None],
        commit_move: Callable[[dict], None],
        build_context_menu: Callable[[QPointF, QGraphicsItem | None, object], None],
        delete_selection: Callable[[], None],
        parent: QWidget | None = None,
        contour_class: type | None = None,
    ):
        super().__init__(scene, parent)
        self.node_class = node_class
        self.connector_class = connector_class
        self.contour_class = contour_class
        self.create_node = create_node
        self.create_connector = create_connector
        self.create_bus = create_bus
        self.create_contour = create_contour
        self.commit_move = commit_move
        self.build_context_menu = build_context_menu
        self.delete_selection = delete_selection
        self.tool = self.SELECT
        self._start_node = None
        self._start_point: QPointF | None = None
        self._preview: QGraphicsItem | None = None
        self._contour_points: list[QPointF] = []
        self._contour_suppress_finish = False
        self._drag_positions: dict | None = None
        self._space_pressed = False
        self._pan_button: Qt.MouseButton | None = None
        self._last_pan_position: QPointF | None = None
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        # repainting the whole viewport per mouse move is far too expensive
        # for large graphs; bounding-rect updates repaint only dirty regions
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_tool(self, tool: str) -> None:
        if tool not in {self.SELECT, self.NODE, self.CONNECTOR, self.BUS, self.CONTOUR}:
            raise ValueError(f"Unknown graph tool: {tool}")
        self._cancel_creation()
        self.tool = tool
        self.setFocus()
        self.setDragMode(
            QGraphicsView.DragMode.RubberBandDrag
            if tool == self.SELECT
            else QGraphicsView.DragMode.NoDrag
        )
        self._update_cursor()
        self.tool_changed.emit(tool)

    def zoom(self, factor: float) -> None:
        current_scale = self.transform().m11()
        target_scale = current_scale * factor
        if 0.15 <= target_scale <= 8.0:
            self.scale(factor, factor)

    def zoom_in(self) -> None:
        self.zoom(1.2)

    def zoom_out(self) -> None:
        self.zoom(1 / 1.2)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._drag_positions = None
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_pressed
        ):
            self._pan_button = event.button()
            self._last_pan_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_positions = {
                item: QPointF(item.pos())
                for item in self.scene().items()
                if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            }
            self.scene()._set_dragging(bool(self._drag_positions))

        if event.button() != Qt.MouseButton.LeftButton or self.tool == self.SELECT:
            super().mousePressEvent(event)
            return

        scene_position = self.mapToScene(event.position().toPoint())
        if self.tool == self.NODE:
            if self.itemAt(event.position().toPoint()) is None:
                self.create_node(scene_position)
            event.accept()
            return

        if self.tool == self.CONTOUR:
            if self._should_close_contour(scene_position):
                self._contour_suppress_finish = True
                self._finish_contour()
            else:
                self._contour_points.append(scene_position)
                self._update_contour_preview(scene_position)
            event.accept()
            return

        item = self._graph_object_at(event.position().toPoint())
        if self.tool == self.CONNECTOR:
            is_valid_start = self._is_connector_start(item)
        else:
            is_valid_start = isinstance(item, self.node_class)
        if not is_valid_start:
            if self.tool == self.CONNECTOR:
                expected = "node, connector, contour or bus"
            else:
                expected = "node"
            self.tool_error.emit(f"Start this tool on a {expected}.")
            event.accept()
            return
        self._start_node = item
        self._start_point = scene_position
        self._create_preview(scene_position, scene_position)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_button is not None and self._last_pan_position is not None:
            current = event.position()
            delta = current - self._last_pan_position
            self._last_pan_position = current
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - round(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - round(delta.y())
            )
            event.accept()
            return
        if self._preview is not None and self._start_point is not None:
            scene_position = self.mapToScene(event.position().toPoint())
            self._preview.setLine(QLineF(self._start_point, scene_position))
            event.accept()
            return
        if self.tool == self.CONTOUR and self._contour_points:
            self._update_contour_preview(
                self.mapToScene(event.position().toPoint())
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _contour_snap_radius(self) -> float:
        scale = abs(self.transform().m11()) or 1.0
        return CONTOUR_SNAP_RADIUS_PX / scale

    def _should_close_contour(self, point: QPointF) -> bool:
        """True, если точка в радиусе прилипания к первой вершине контура."""
        return (
            len(self._contour_points) >= 3
            and QLineF(point, self._contour_points[0]).length()
            <= self._contour_snap_radius()
        )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._pan_button == event.button():
            self._pan_button = None
            self._last_pan_position = None
            self._update_cursor()
            event.accept()
            return
        drag_positions = self._drag_positions
        self._drag_positions = None
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        self.scene()._set_dragging(False)
        if self.tool not in {self.CONNECTOR, self.BUS} or self._start_node is None:
            if drag_positions is not None:
                self.commit_move(drag_positions)
            super().mouseReleaseEvent(event)
            return

        scene_position = self.mapToScene(event.position().toPoint())
        target = self._graph_object_at(
            event.position().toPoint(),
            include_connectors=self.tool == self.CONNECTOR,
        )
        start = self._start_node
        start_point = self._start_point
        self._remove_preview()
        self._start_node = None
        self._start_point = None

        if self.tool == self.CONNECTOR:
            if not self._is_connector_start(target):
                self.tool_error.emit(
                    "Connectors must end on a node, connector, contour or bus."
                )
            elif target is start:
                self.tool_error.emit("Choose two different graph objects.")
            else:
                self.create_connector(
                    start,
                    target,
                    start_point or scene_position,
                    scene_position,
                )
        else:
            if start_point is not None and (
                scene_position - start_point
            ).manhattanLength() < 5:
                self.tool_error.emit("Drag from a node to place the bus endpoint.")
            else:
                self.create_bus(start, scene_position)
        if drag_positions is not None:
            self.commit_move(drag_positions)
        event.accept()

    def contextMenuEvent(self, event) -> None:
        item = self._graph_object_at(event.pos().toPoint())
        self.build_context_menu(
            self.mapToScene(event.pos()),
            item,
            event.globalPos(),
        )

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self.tool == self.CONTOUR and event.button() == Qt.MouseButton.LeftButton:
            if not self._contour_points and self._contour_suppress_finish:
                # контур уже замкнут кликом по первой вершине; двойной клик
                # от этого же нажатия игнорируем
                self._contour_suppress_finish = False
                event.accept()
                return
            point = self.mapToScene(event.position().toPoint())
            if self._should_close_contour(point):
                pass
            elif not self._contour_points:
                self._contour_points.append(point)
            elif (point - self._contour_points[-1]).manhattanLength() > 1:
                self._contour_points.append(point)
            self._finish_contour()
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        if self.tool in {self.CONNECTOR, self.BUS}:
            scene_position = self.mapToScene(event.position().toPoint())
            item = self._graph_object_at(
                event.position().toPoint(),
                include_connectors=self.tool == self.CONNECTOR,
            )
            if self.tool == self.CONNECTOR:
                is_valid_start = self._is_connector_start(item)
            else:
                is_valid_start = isinstance(item, self.node_class)
            if is_valid_start:
                self._start_node = item
                self._start_point = scene_position
                self._create_preview(scene_position, scene_position)
            event.accept()
            return
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        tools = {
            Qt.Key.Key_1: self.SELECT,
            Qt.Key.Key_2: self.CONNECTOR,
            Qt.Key.Key_3: self.BUS,
            Qt.Key.Key_4: self.CONTOUR,
            Qt.Key.Key_5: self.NODE,
        }
        if event.key() in tools:
            self.set_tool(tools[event.key()])
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.tool == self.CONTOUR:
                self._finish_contour()
                event.accept()
            else:
                super().keyPressEvent(event)
        elif event.key() == Qt.Key.Key_Escape and self.tool != self.SELECT:
            self._cancel_creation()
            self.set_tool(self.SELECT)
            event.accept()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selection()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _create_preview(self, start: QPointF, end: QPointF) -> None:
        self._remove_preview()
        self._preview = QGraphicsLineItem(QLineF(start, end))
        self._preview.setPen(QColor(Qt.GlobalColor.cyan))
        self._preview.setZValue(10_000)
        self.scene().addItem(self._preview)

    def _update_contour_preview(self, current: QPointF) -> None:
        self._remove_preview()
        if not self._contour_points:
            return
        self._contour_suppress_finish = False
        snapping = self._should_close_contour(current)
        preview_end = self._contour_points[0] if snapping else current
        points = [*self._contour_points, preview_end]
        path_item = QGraphicsPathItem()
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path_item.setPath(path)
        pen = QPen(QColor(Qt.GlobalColor.cyan), 0)
        if snapping:
            pen = QPen(QColor("#44dd66"), 2)
        path_item.setPen(pen)
        path_item.setZValue(10_000)
        self._preview = path_item
        self.scene().addItem(path_item)

    def _finish_contour(self) -> None:
        if len(self._contour_points) < 3:
            self.tool_error.emit("A contour needs at least three canvas points.")
            return
        points = self._contour_points.copy()
        self._cancel_creation()
        self.create_contour(points)

    def _remove_preview(self) -> None:
        if self._preview is not None and self._preview.scene() is not None:
            self.scene().removeItem(self._preview)
        self._preview = None

    def _cancel_creation(self) -> None:
        self._remove_preview()
        self._start_node = None
        self._start_point = None
        self._contour_points.clear()
        self._contour_suppress_finish = False

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = False
            if self._pan_button is None:
                self._update_cursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _connector_endpoint_classes(self) -> tuple:
        classes = (self.node_class, self.connector_class)
        return classes + ((self.contour_class,) if self.contour_class else ())

    def _is_connector_start(self, item) -> bool:
        return isinstance(item, self._connector_endpoint_classes())

    def _graph_object_at(
        self, position, *, include_connectors: bool = True
    ) -> QGraphicsItem | None:
        """Topmost allowed graph object at ``position`` (viewport coords)."""
        allowed = (
            (self.node_class, self.connector_class, self.contour_class)
            if include_connectors and self.contour_class
            else (self.node_class, self.connector_class)
            if include_connectors
            else (self.node_class,)
        )
        for item in self.items(position):
            candidate = item
            while candidate is not None:
                if isinstance(candidate, allowed):
                    return candidate
                candidate = candidate.parentItem()
        return None

    def _update_cursor(self) -> None:
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
            if self._space_pressed
            else Qt.CursorShape.ArrowCursor
            if self.tool == self.SELECT
            else Qt.CursorShape.CrossCursor
        )
