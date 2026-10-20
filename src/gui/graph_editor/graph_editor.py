from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QShortcut,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.signals import signals
from src.gui.graph_editor.graph_canvas import GraphCanvasView
from src.gui.graph_editor.graph_commands import (
    CommandConnectorTypeChange,
    CommandCreateBus,
    CommandCreateContour,
    CommandCreateConnector,
    CommandCreateNode,
    CommandDeleteSelection,
    CommandMoveObjects,
    CommandNodeTypeChange,
    CommandRenameNode,
)
from src.gui.graph_editor.graph_types import (
    CONNECTOR_TYPES as _CONNECTOR_TYPES,
    EDGE_TYPES as _EDGE_TYPES,
    IDENTIFIER as _IDENTIFIER,
    NODE_TYPES as _NODE_TYPES,
    SIMPLE_NODE as _SIMPLE_NODE,
    SIMPLE_RELATION as _SIMPLE_RELATION,
    node_type_parts as _node_type_parts,
    relation_for_gwf as _relation_for_gwf,
)
from src.gui.graph_editor.gwf_codec import (
    gwf_number as _gwf_number,
    parse_gwf_document,
    serialize_gwf,
)
from src.utils.security import get_project_root, safe_path


class GraphNode(QGraphicsItem):
    ICON_SIZE = 24
    LABEL_GAP = 8

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
        self.label = QGraphicsTextItem(gwf_idtf or identifier, self)
        self.label.setDefaultTextColor(QColor("#d4d4d4"))
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(1)
        self._position_label()

    def boundingRect(self):
        glyph_bounds = self._glyph_rect().adjusted(-2, -2, 2, 2)
        return glyph_bounds.united(self._label_rect())

    def shape(self) -> QPainterPath:
        path = self._glyph_shape()
        path.addRect(self._label_rect())
        return path

    def _label_rect(self) -> QRectF:
        return self.label.boundingRect().translated(self.label.pos())

    def _position_label(self) -> None:
        text_rect = self.label.boundingRect()
        self.label.setPos(
            self.ICON_SIZE / 2 + self.LABEL_GAP,
            -text_rect.center().y(),
        )

    def _glyph_rect(self) -> QRectF:
        half_size = self.ICON_SIZE / 2
        return QRectF(-half_size, -half_size, self.ICON_SIZE, self.ICON_SIZE)

    def _glyph_shape(self) -> QPainterPath:
        path = QPainterPath()
        permanence, structure = _node_type_parts(self.gwf_type)
        rect = self._glyph_rect()
        if structure == "not_define":
            path.addEllipse(rect.adjusted(8.4, 8.4, -8.4, -8.4))
        elif permanence == "const":
            path.addEllipse(rect)
        else:
            path.addRect(rect)
        return path

    def connection_point(self, target: QPointF) -> QPointF:
        center = QPointF(0, 0)
        target_local = self.mapFromScene(target)
        direction = target_local - center
        if not direction.x() and not direction.y():
            return self.mapToScene(center)

        path = self._glyph_shape()
        low, high = 0.0, 1.0
        for _ in range(32):
            mid = (low + high) / 2
            if path.contains(center + direction * mid):
                low = mid
            else:
                high = mid
        return self.mapToScene(center + direction * low)

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        permanence, structure = _node_type_parts(self.gwf_type)
        color = QColor("#66aaff") if self.isSelected() else QColor("#d4d4d4")
        brush = QBrush(QColor(255, 255, 255, 224))
        if structure == "not_define":
            color = QColor("#d4d4d4")
            brush = QBrush(QColor(color.red(), color.green(), color.blue(), 224))
        painter.save()
        pen = QPen(color, 2)
        if "/var/" in self.gwf_type or "/meta/" in self.gwf_type:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(brush)
        glyph = self._glyph_rect()
        if structure == "not_define":
            glyph = glyph.adjusted(8.4, 8.4, -8.4, -8.4)
        if structure == "not_define" or permanence == "const":
            painter.drawEllipse(glyph)
        else:
            painter.drawRect(glyph)
        self._paint_structure(painter, glyph, structure, color)
        content = (
            self.gwf_element.find("content")
            if self.gwf_element is not None
            else None
        )
        if content is not None and content.get("type", "0") != "0":
            painter.setBrush(QBrush(QColor("#cc66ff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(
                QRectF(glyph.right() - 5, glyph.bottom() - 5, 5, 5)
            )
        painter.restore()

    def set_identifier(self, identifier: str) -> None:
        self.prepareGeometryChange()
        self.identifier = identifier
        self.gwf_idtf = identifier
        self.label.setPlainText(identifier)
        self._position_label()
        self.update()

    @staticmethod
    def _paint_structure(
        painter: QPainter, rect: QRectF, structure: str, color: QColor
    ) -> None:
        center = rect.center()
        left, right = rect.left(), rect.right()
        top, bottom = rect.top(), rect.bottom()
        if structure == "struct":
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QRectF(center.x() - 2, center.y() - 2, 4, 4))
        elif structure == "tuple":
            painter.drawLine(QPointF(left, center.y()), QPointF(right, center.y()))
        elif structure == "role":
            painter.drawLine(QPointF(left, center.y()), QPointF(right, center.y()))
            painter.drawLine(QPointF(center.x(), top), QPointF(center.x(), bottom))
        elif structure == "relation":
            painter.drawLine(QPointF(left, top), QPointF(right, bottom))
            painter.drawLine(QPointF(right, top), QPointF(left, bottom))
        elif structure == "group":
            painter.drawLine(QPointF(left, top), QPointF(right, bottom))
            painter.drawLine(QPointF(right, top), QPointF(left, bottom))
            painter.drawLine(QPointF(left, center.y()), QPointF(right, center.y()))
        elif structure == "abstract":
            for y in range(int(top + 2), int(bottom), 3):
                painter.drawLine(QPointF(left, y), QPointF(right, y))
        elif structure == "material":
            for offset in range(0, int(rect.width()), 5):
                painter.drawLine(
                    QPointF(left + offset, top),
                    QPointF(left, min(bottom, top + offset)),
                )
                painter.drawLine(
                    QPointF(right - offset, bottom),
                    QPointF(right, max(top, bottom - offset)),
                )

    def itemChange(self, change, value):
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            scene = self.scene()
            if isinstance(scene, GraphScene):
                scene.node_moved(self)
        return result


class GraphEdge(QGraphicsPathItem):
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
        self.update_path()

    def update_path(self) -> None:
        source_center = self._endpoint_center(self.source)
        target_center = self._endpoint_center(self.target)
        source_toward = self.waypoints[0] if self.waypoints else target_center
        target_toward = self.waypoints[-1] if self.waypoints else source_center
        start = self._endpoint_connection_point(
            self.source, source_toward, self.begin_dot
        )
        end = self._endpoint_connection_point(
            self.target, target_toward, self.end_dot
        )
        path = QPainterPath(start)
        for waypoint in self.waypoints:
            path.lineTo(waypoint)
        path.lineTo(end)
        self.setPath(path)

    @staticmethod
    def _endpoint_center(endpoint: GraphNode | GraphEdge) -> QPointF:
        if isinstance(endpoint, GraphNode):
            return endpoint.mapToScene(QPointF(0, 0))
        path = endpoint.mapToScene(endpoint.path())
        return path.pointAtPercent(0.5)

    @staticmethod
    def _endpoint_connection_point(
        endpoint: GraphNode | GraphEdge, toward: QPointF, dot: float
    ) -> QPointF:
        if isinstance(endpoint, GraphNode):
            return endpoint.connection_point(toward)
        return endpoint.cross(dot)

    def connection_point(self, toward: QPointF) -> QPointF:
        return self.cross(self.dot_position(toward))

    def dot_position(self, point: QPointF) -> float:
        scene_path = self.mapToScene(self.path())
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

    def cross(self, dot: float) -> QPointF:
        scene_path = self.mapToScene(self.path())
        count = scene_path.elementCount()
        if count < 2:
            return self.scenePos()
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

    def boundingRect(self):
        return self.path().boundingRect().adjusted(-15, -18, 15, 18)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(self.path())

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        line = self.path()
        if line.isEmpty():
            return
        end = line.pointAtPercent(1)
        middle = line.pointAtPercent(0.5)
        pen = QPen(
            QColor("#66aaff") if self.isSelected() else QColor("#a0a0a0"),
            2,
        )
        if "/var/" in self.gwf_type or "/meta/" in self.gwf_type:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif "/temp" in self.gwf_type:
            pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        painter.drawPath(line)
        oriented = self.gwf_tag == "arc" or self.gwf_type.endswith("/orient")
        arrow_start = line.pointAtPercent(0.98)
        dx = end.x() - arrow_start.x()
        dy = end.y() - arrow_start.y()
        length = math.hypot(dx, dy)
        if length and oriented:
            unit_x = dx / length
            unit_y = dy / length
            arrow_base = end - QPointF(unit_x * 11, unit_y * 11)
            perpendicular = QPointF(-unit_y * 5, unit_x * 5)
            painter.drawLine(end, arrow_base + perpendicular)
            painter.drawLine(end, arrow_base - perpendicular)
        if length and "/neg" in self.gwf_type:
            midpoint = line.pointAtPercent(0.5)
            perpendicular = QPointF(-dy / length * 6, dx / length * 6)
            painter.drawLine(midpoint - perpendicular, midpoint + perpendicular)
        painter.setPen(QColor("#d4d4d4"))
        painter.drawText(middle + QPointF(5, -5), self.edge_type)


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
        self.setPen(QPen(QColor("#a0a0a0"), 1, Qt.PenStyle.DashLine))
        self.setBrush(Qt.BrushStyle.NoBrush)

    def itemChange(self, change, value):
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            scene = self.scene()
            if isinstance(scene, GraphScene) and not scene._loading:
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


class GraphScene(QGraphicsScene):
    model_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.aux_objects: list[GraphAuxObject] = []
        self.opaque_lines: list[str] = []
        self.gwf_root_attributes: dict[str, str] = {"version": "2.0"}
        self.gwf_root_extras: list[ET.Element] = []
        self.gwf_sector_attributes: dict[str, str] = {}
        self.gwf_sector_extras: list[ET.Element] = []
        self._loading = False
        self.setSceneRect(0, 0, 1600, 1000)
        self.setBackgroundBrush(QColor("#1e1e1e"))

    def add_node(
        self,
        identifier: str,
        position=None,
        *,
        gwf_id: str = "",
        gwf_type: str = "node/const/general_node",
        gwf_idtf: str | None = None,
        gwf_element: ET.Element | None = None,
    ) -> GraphNode:
        if not _IDENTIFIER.fullmatch(identifier):
            raise ValueError("Node names must be valid SCs identifiers.")
        if identifier in self.nodes:
            raise ValueError(f"A node named '{identifier}' already exists.")

        if not gwf_id:
            gwf_id = self._next_gwf_id("node")
        elif gwf_id in self._existing_gwf_ids():
            raise ValueError(f"A GWF object with id '{gwf_id}' already exists.")
        node = GraphNode(
            identifier,
            gwf_id,
            gwf_type,
            identifier if gwf_idtf is None else gwf_idtf,
            gwf_element,
        )
        self.addItem(node)
        self.nodes[identifier] = node
        if position is None:
            index = len(self.nodes) - 1
            position = QPointF(100 + (index % 5) * 210, 100 + (index // 5) * 150)
        node.setPos(position)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()
        return node

    def connect_nodes(
        self,
        source: GraphNode | GraphEdge,
        target: GraphNode | GraphEdge,
        edge_type: str,
        *,
        gwf_id: str = "",
        gwf_type: str = "arc/-/-",
        gwf_tag: str = "arc",
        gwf_element: ET.Element | None = None,
        waypoints: list[QPointF] | None = None,
        source_anchor: QPointF | None = None,
        target_anchor: QPointF | None = None,
    ) -> GraphEdge:
        if not isinstance(source, (GraphNode, GraphEdge)) or not isinstance(
            target, (GraphNode, GraphEdge)
        ):
            raise ValueError(
                "SCg connectors can only be attached to nodes or connectors."
            )
        if source is target:
            raise ValueError("Choose two different graph objects to create a relation.")
        if source.scene() is not self or target.scene() is not self:
            raise ValueError("Both graph objects must belong to this graph.")
        if edge_type not in _EDGE_TYPES:
            raise ValueError(f"Unsupported SCs edge token: '{edge_type}'.")
        if gwf_tag not in {"arc", "pair"} or gwf_type not in {
            item[1] for item in _CONNECTOR_TYPES
        }:
            raise ValueError(f"Unsupported SCg connector type: '{gwf_type}'.")
        if gwf_id and gwf_id in self._existing_gwf_ids():
            raise ValueError(f"A GWF object with id '{gwf_id}' already exists.")
        edge = GraphEdge(
            source,
            target,
            edge_type,
            gwf_id or self._next_gwf_id("edge"),
            gwf_type,
            gwf_tag,
            gwf_element,
            waypoints,
        )
        if isinstance(source, GraphEdge) and source_anchor is not None:
            edge.begin_dot = source.dot_position(source_anchor)
        if isinstance(target, GraphEdge) and target_anchor is not None:
            edge.end_dot = target.dot_position(target_anchor)
        edge.update_path()
        self.addItem(edge)
        self.edges.append(edge)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()
        return edge

    def set_connector_type(
        self, edge: GraphEdge, gwf_type: str, gwf_tag: str, scs_token: str
    ) -> None:
        if edge not in self.edges or edge.scene() is not self:
            raise ValueError("The connector must belong to this graph.")
        allowed = {
            (connector_type, tag, token)
            for _, connector_type, tag, token in _CONNECTOR_TYPES
        }
        if (gwf_type, gwf_tag, scs_token) not in allowed:
            raise ValueError(f"Unsupported SCg connector type: '{gwf_type}'.")
        edge.gwf_type = gwf_type
        edge.gwf_tag = gwf_tag
        edge.edge_type = scs_token
        edge.update()
        if not self._loading:
            self.model_changed.emit()

    def rename_node(self, node: GraphNode, identifier: str) -> None:
        if node.scene() is not self or node.identifier not in self.nodes:
            raise ValueError("The node must belong to this graph.")
        if not _IDENTIFIER.fullmatch(identifier):
            raise ValueError("Node names must be valid SCs identifiers.")
        if identifier != node.identifier and identifier in self.nodes:
            raise ValueError(f"A node named '{identifier}' already exists.")
        del self.nodes[node.identifier]
        node.identifier = identifier
        node.gwf_idtf = identifier
        node.set_identifier(identifier)
        self.nodes[identifier] = node
        for edge in self.edges:
            if edge.source is node or edge.target is node:
                edge.update_path()
        if not self._loading:
            self.model_changed.emit()

    def set_node_type(self, node: GraphNode, gwf_type: str) -> None:
        valid_types = {value for _, value in _NODE_TYPES}
        if gwf_type not in valid_types:
            raise ValueError(f"Unsupported SCg node type: '{gwf_type}'.")
        if node.scene() is not self:
            raise ValueError("The node must belong to this graph.")
        node.gwf_type = gwf_type
        node.update()
        self.node_moved(node)

    def add_contour(self, points: list[QPointF]) -> GraphAuxObject:
        if len(points) < 3:
            raise ValueError("A contour needs at least three points.")
        element = ET.Element(
            "contour",
            {
                "type": "contour",
                "idtf": "",
                "shapeColor": "0",
                "id": self._next_gwf_id("contour"),
                "parent": "0",
            },
        )
        points_element = ET.SubElement(element, "points")
        for point in points:
            ET.SubElement(
                points_element,
                "point",
                {"x": str(point.x()), "y": str(point.y())},
            )
        contour = GraphAuxObject("contour", element)
        self.addItem(contour)
        self.aux_objects.append(contour)
        self._update_scene_rect()
        self.model_changed.emit()
        return contour

    def add_bus(self, owner: GraphNode, end: QPointF) -> GraphAuxObject:
        if not isinstance(owner, GraphNode) or owner.scene() is not self:
            raise ValueError("The bus owner must belong to this graph.")
        start = owner.connection_point(end)
        element = ET.Element(
            "bus",
            {
                "type": "bus",
                "idtf": "",
                "shapeColor": "0",
                "id": self._next_gwf_id("bus"),
                "parent": "0",
                "owner": owner.gwf_id,
                "b_x": str(start.x()),
                "b_y": str(start.y()),
                "e_x": str(end.x()),
                "e_y": str(end.y()),
            },
        )
        ET.SubElement(element, "points")
        bus = GraphAuxObject("bus", element, owner)
        self.addItem(bus)
        self.aux_objects.append(bus)
        self._update_scene_rect()
        self.model_changed.emit()
        return bus

    def _collect_removal(
        self, selected
    ) -> tuple[set[GraphNode], set[GraphEdge], set[GraphAuxObject]]:
        selected = set(selected)
        removed_nodes = {item for item in selected if isinstance(item, GraphNode)}
        removed_edges = {item for item in selected if isinstance(item, GraphEdge)}
        removed_aux = {
            item for item in selected if isinstance(item, GraphAuxObject)
        }
        removed_objects: set[GraphNode | GraphEdge] = set(removed_nodes)
        removed_objects.update(removed_edges)
        while True:
            dependent_edges = {
                edge
                for edge in self.edges
                if edge.source in removed_objects or edge.target in removed_objects
            }
            new_edges = dependent_edges - removed_edges
            if not new_edges:
                break
            removed_edges.update(new_edges)
            removed_objects.update(new_edges)
        removed_aux.update(
            item for item in self.aux_objects if item.owner in removed_nodes
        )
        return removed_nodes, removed_edges, removed_aux

    def remove_selected(self) -> None:
        removed_nodes, removed_edges, removed_aux = self._collect_removal(
            self.selectedItems()
        )
        self._remove_objects(removed_nodes, removed_edges, removed_aux)

    def _remove_objects(
        self,
        removed_nodes: set[GraphNode],
        removed_edges: set[GraphEdge],
        removed_aux: set[GraphAuxObject],
    ) -> None:
        if not removed_nodes and not removed_edges and not removed_aux:
            return
        for edge in list(self.edges):
            if edge in removed_edges:
                self.edges.remove(edge)
                self.removeItem(edge)
        for node in removed_nodes:
            self.nodes.pop(node.identifier, None)
            self.removeItem(node)
        removed_ids = {item.gwf_id for item in (*removed_nodes, *removed_edges)}
        self.gwf_sector_extras = [
            child
            for child in self.gwf_sector_extras
            if child.get("id_b") not in removed_ids
            and child.get("id_e") not in removed_ids
            and child.get("owner") not in removed_ids
        ]
        for item in removed_aux:
            if item in self.aux_objects:
                self.aux_objects.remove(item)
            self.removeItem(item)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def _restore_objects(
        self,
        removed_nodes: list[GraphNode],
        removed_edges: list[GraphEdge],
        removed_aux: list[GraphAuxObject],
    ) -> None:
        self._loading = True
        try:
            for node in removed_nodes:
                if node.scene() is not self:
                    self.addItem(node)
                    self.nodes[node.identifier] = node
            pending = list(removed_edges)
            while pending:
                remaining: list[GraphEdge] = []
                restored_any = False
                for edge in pending:
                    if (
                        edge.source.scene() is self
                        and edge.target.scene() is self
                    ):
                        self.addItem(edge)
                        self.edges.append(edge)
                        edge.update_path()
                        restored_any = True
                    else:
                        remaining.append(edge)
                if not restored_any:
                    break
                pending = remaining
            for item in removed_aux:
                if item.scene() is not self:
                    self.addItem(item)
                    self.aux_objects.append(item)
        finally:
            self._loading = False
        self._update_scene_rect()
        self.model_changed.emit()

    def _insert_node_instance(
        self, node: GraphNode, position: QPointF | None = None
    ) -> None:
        if node.scene() is self:
            return
        if node.identifier in self.nodes:
            raise ValueError(f"A node named '{node.identifier}' already exists.")
        self.addItem(node)
        self.nodes[node.identifier] = node
        if position is not None and node.pos() != position:
            node.setPos(position)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def _remove_node_instance(self, node: GraphNode) -> None:
        if node.scene() is not self:
            return
        self.nodes.pop(node.identifier, None)
        self.removeItem(node)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def _insert_edge_instance(self, edge: GraphEdge) -> None:
        if edge.scene() is self:
            return
        for endpoint in (edge.source, edge.target):
            if not isinstance(endpoint, (GraphNode, GraphEdge)) or (
                endpoint.scene() is not self
            ):
                raise ValueError("Both graph objects must belong to this graph.")
        self.addItem(edge)
        self.edges.append(edge)
        edge.update_path()
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def _remove_edge_instance(self, edge: GraphEdge) -> None:
        if edge.scene() is not self:
            return
        if edge in self.edges:
            self.edges.remove(edge)
        self.removeItem(edge)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def _insert_aux_instance(self, item: GraphAuxObject) -> None:
        if item.scene() is self:
            return
        if item.owner is not None and item.owner.scene() is not self:
            raise ValueError("The bus owner must belong to this graph.")
        self.addItem(item)
        self.aux_objects.append(item)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def _remove_aux_instance(self, item: GraphAuxObject) -> None:
        if item.scene() is not self:
            return
        if item in self.aux_objects:
            self.aux_objects.remove(item)
        self.removeItem(item)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def node_moved(self, node: GraphNode) -> None:
        self._refresh_connected_edges(node, set())
        for item in self.aux_objects:
            if item.kind == "bus" and item.owner is node:
                old_path = item.mapToScene(item.path())
                elements = [
                    old_path.elementAt(index)
                    for index in range(old_path.elementCount())
                ]
                if len(elements) >= 2:
                    second = QPointF(elements[1].x, elements[1].y)
                    end = QPointF(elements[-1].x, elements[-1].y)
                    start = node.connection_point(second)
                    path = QPainterPath(item.mapFromScene(start))
                    for element in elements[1:-1]:
                        path.lineTo(item.mapFromScene(QPointF(element.x, element.y)))
                    path.lineTo(item.mapFromScene(end))
                    item.setPath(path)
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def _update_scene_rect(self) -> None:
        bounds = self.itemsBoundingRect().united(QRectF(0, 0, 1600, 1000))
        self.setSceneRect(bounds.adjusted(-200, -200, 200, 200))

    def _refresh_connected_edges(
        self, endpoint: GraphNode | GraphEdge, refreshed: set[GraphEdge]
    ) -> None:
        for edge in self.edges:
            if edge in refreshed or (
                edge.source is not endpoint and edge.target is not endpoint
            ):
                continue
            refreshed.add(edge)
            edge.update_path()
            self._refresh_connected_edges(edge, refreshed)

    def load_scs(self, source: str) -> None:
        self._loading = True
        try:
            self.clear()
            self.nodes.clear()
            self.edges.clear()
            self.aux_objects.clear()
            self.opaque_lines = []
            self.gwf_root_attributes = {"version": "2.0"}
            self.gwf_root_extras.clear()
            self.gwf_sector_attributes.clear()
            self.gwf_sector_extras.clear()
            relations: list[tuple[str, str, str]] = []
            identifiers: list[str] = []

            for line in source.splitlines(keepends=True):
                content = line.rstrip("\r\n")
                relation_match = _SIMPLE_RELATION.fullmatch(content)
                node_match = _SIMPLE_NODE.fullmatch(content)
                if relation_match:
                    left, edge_type, right = relation_match.groups()
                    relations.append((left, edge_type, right))
                    identifiers.extend((left, right))
                elif node_match:
                    identifiers.append(node_match.group(1))
                else:
                    self.opaque_lines.append(line)

            for identifier in dict.fromkeys(identifiers):
                self.add_node(identifier)
            for index, (left, edge_type, right) in enumerate(relations):
                self.connect_nodes(
                    self.nodes[left],
                    self.nodes[right],
                    edge_type,
                )
                if index:
                    self.edges[-1].setZValue(0)
        finally:
            self._loading = False

    def load_gwf(self, source: str | bytes) -> None:
        root, sector, known_node_ids = parse_gwf_document(source)

        self._loading = True
        try:
            self.clear()
            self.nodes.clear()
            self.edges.clear()
            self.aux_objects.clear()
            self.opaque_lines.clear()
            self.gwf_root_attributes = dict(root.attrib)
            self.gwf_root_extras = [
                deepcopy(child) for child in root if child is not sector
            ]
            self.gwf_sector_attributes = dict(sector.attrib)
            known_tags = {"node", "arc", "pair", "bus", "contour"}
            supported_connector_types = {
                connector_type for _, connector_type, _, _ in _CONNECTOR_TYPES
            }
            self.gwf_sector_extras = [
                deepcopy(child)
                for child in sector
                if child.tag not in known_tags
                or child.tag in {"arc", "pair"}
                and (
                    child.get("type") not in supported_connector_types
                    or child.get("id_b") == child.get("id_e")
                )
                or child.tag == "bus"
                and child.get("owner") not in known_node_ids
            ]

            element_ids: dict[str, GraphNode | GraphEdge] = {}
            node_ids: dict[str, GraphNode] = {}
            for element in sector.findall("node"):
                gwf_id = element.get("id", "")
                if not gwf_id or gwf_id in element_ids:
                    raise ValueError("GWF nodes must have unique, non-empty ids.")
                idtf = element.get("idtf", "")
                identifier = idtf if _IDENTIFIER.fullmatch(idtf) else ""
                if not identifier or identifier in self.nodes:
                    identifier = f"node_{len(self.nodes) + 1}"
                    while identifier in self.nodes:
                        identifier += "_"
                position = QPointF(
                    _gwf_number(element, "x", f"GWF node {gwf_id}"),
                    _gwf_number(element, "y", f"GWF node {gwf_id}"),
                )
                node = self.add_node(
                    identifier,
                    position,
                    gwf_id=gwf_id,
                    gwf_type=element.get("type", "node/const/not_define"),
                    gwf_idtf=idtf,
                    gwf_element=deepcopy(element),
                )
                element_ids[gwf_id] = node
                node_ids[gwf_id] = node

            pending_connectors = [
                element
                for tag in ("arc", "pair")
                for element in sector.findall(tag)
                if element.get("type") in supported_connector_types
                and element.get("id_b") != element.get("id_e")
            ]
            while pending_connectors:
                remaining: list[ET.Element] = []
                loaded_connector = False
                for element in pending_connectors:
                    source_id = element.get("id_b", "")
                    target_id = element.get("id_e", "")
                    source_object = element_ids.get(source_id)
                    target_object = element_ids.get(target_id)
                    if source_object is None or target_object is None:
                        remaining.append(element)
                        continue
                    tag = element.tag
                    connector = self.connect_nodes(
                        source_object,
                        target_object,
                        _relation_for_gwf(tag, element.get("type", "")),
                        gwf_id=element.get("id", ""),
                        gwf_type=element.get("type", "arc/-/-"),
                        gwf_tag=tag,
                        gwf_element=deepcopy(element),
                        waypoints=[
                            QPointF(
                                float(point.get("x", "0")),
                                float(point.get("y", "0")),
                            )
                            for point in element.findall("./points/point")
                        ],
                    )
                    element_ids[connector.gwf_id] = connector
                    loaded_connector = True
                if not loaded_connector:
                    self.gwf_sector_extras.extend(
                        deepcopy(item) for item in remaining
                    )
                    break
                pending_connectors = remaining
            for tag in ("bus", "contour"):
                for element in sector.findall(tag):
                    if (
                        tag == "bus"
                        and element.get("owner", "") not in node_ids
                    ):
                        continue
                    owner = (
                        node_ids.get(element.get("owner", ""))
                        if tag == "bus"
                        else None
                    )
                    item = GraphAuxObject(tag, element, owner)
                    self.addItem(item)
                    self.aux_objects.append(item)
        finally:
            self._loading = False

    def to_scs(self) -> str:
        output = "".join(self.opaque_lines)
        if output and not output.endswith("\n"):
            output += "\n"
        connected_nodes = {
            endpoint
            for edge in self.edges
            for endpoint in (edge.source, edge.target)
            if isinstance(endpoint, GraphNode)
        }
        for node in self.nodes.values():
            if node not in connected_nodes:
                output += f"{node.identifier};;\n"
        for edge in self.edges:
            if not isinstance(edge.source, GraphNode) or not isinstance(
                edge.target, GraphNode
            ):
                continue
            output += (
                f"{edge.source.identifier} {edge.edge_type} "
                f"{edge.target.identifier};;\n"
            )
        return output

    def to_gwf(self) -> str:
        return serialize_gwf(self)

    def _next_gwf_id(self, prefix: str) -> str:
        identifiers = self._existing_gwf_ids()
        index = 1
        while f"KBStudio{prefix.title()}{index}" in identifiers:
            index += 1
        return f"KBStudio{prefix.title()}{index}"

    def _existing_gwf_ids(self) -> set[str]:
        item_ids = {
            item.gwf_id
            for item in (*self.nodes.values(), *self.edges, *self.aux_objects)
            if item.gwf_id
        }
        item_ids.update(
            object_id
            for element in self.gwf_sector_extras
            if (object_id := element.get("id"))
        )
        return item_ids


class GraphEditorWidget(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("graphEditorWidget")
        self.file_path: Path | None = None
        self.is_modified = False
        self.is_active = True

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        tools_toolbar = QHBoxLayout()
        layout.addLayout(toolbar)
        layout.addLayout(tools_toolbar)

        self.new_button = QPushButton("New graph")
        self.new_button.clicked.connect(self.new_graph)
        toolbar.addWidget(self.new_button)

        self.node_type_combo = QComboBox()
        self.node_type_combo.setMaximumWidth(190)
        for label, gwf_type in _NODE_TYPES:
            self.node_type_combo.addItem(label, gwf_type)
        default_node_type = self.node_type_combo.findData("node/const/general_node")
        if default_node_type >= 0:
            self.node_type_combo.setCurrentIndex(default_node_type)
        toolbar.addWidget(self.node_type_combo)

        self.edge_type_combo = QComboBox()
        self.edge_type_combo.setMaximumWidth(210)
        for label, gwf_type, gwf_tag, scs_token in _CONNECTOR_TYPES:
            self.edge_type_combo.addItem(label, (gwf_type, gwf_tag, scs_token))
        toolbar.addWidget(self.edge_type_combo)

        self.rename_edit = QLineEdit()
        self.rename_edit.setPlaceholderText("Selected node name")
        self.rename_edit.returnPressed.connect(self.rename_selected)
        toolbar.addWidget(self.rename_edit)

        self.rename_button = QPushButton("Rename")
        self.rename_button.clicked.connect(self.rename_selected)
        toolbar.addWidget(self.rename_button)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find node")
        self.search_edit.returnPressed.connect(self.find_node)
        toolbar.addWidget(self.search_edit)

        self.find_button = QPushButton("Find")
        self.find_button.clicked.connect(self.find_node)
        toolbar.addWidget(self.find_button)

        self.remove_button = QPushButton("Delete")
        self.remove_button.clicked.connect(self.remove_selected)
        toolbar.addWidget(self.remove_button)

        self.undo_stack = QUndoStack(self)
        self.undo_button = QPushButton("Undo")
        self.undo_button.clicked.connect(self.undo_stack.undo)
        self.undo_button.setEnabled(False)
        self.redo_button = QPushButton("Redo")
        self.redo_button.clicked.connect(self.undo_stack.redo)
        self.redo_button.setEnabled(False)
        self.undo_stack.canUndoChanged.connect(self.undo_button.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.redo_button.setEnabled)
        tools_toolbar.addWidget(self.undo_button)
        tools_toolbar.addWidget(self.redo_button)
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self.undo_stack.undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self.undo_stack.redo)

        self.zoom_in_button = QPushButton("Zoom +")
        self.zoom_in_button.clicked.connect(lambda: self.view.zoom_in())
        tools_toolbar.addWidget(self.zoom_in_button)

        self.zoom_out_button = QPushButton("Zoom -")
        self.zoom_out_button.clicked.connect(lambda: self.view.zoom_out())
        tools_toolbar.addWidget(self.zoom_out_button)

        self.fit_button = QPushButton("Fit")
        self.fit_button.clicked.connect(self.fit_graph)
        tools_toolbar.addWidget(self.fit_button)

        self.export_button = QPushButton("Export PNG")
        self.export_button.clicked.connect(self.export_image)
        tools_toolbar.addWidget(self.export_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        toolbar.addWidget(self.save_button)

        self.scene = GraphScene(self)
        self.view = GraphCanvasView(
            self.scene,
            GraphNode,
            GraphEdge,
            self._create_node_at,
            self._create_connector,
            self._create_bus,
            self._create_contour,
            self._commit_move,
            self.remove_selected,
        )
        self.view.tool_error.connect(self._show_tool_error)
        self.view.tool_changed.connect(self._show_tool)
        layout.addWidget(self.view)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons: dict[str, QPushButton] = {}
        for tool, label in (
            (GraphCanvasView.SELECT, "Select (1)"),
            (GraphCanvasView.CONNECTOR, "Arc (2)"),
            (GraphCanvasView.BUS, "Bus (3)"),
            (GraphCanvasView.CONTOUR, "Contour (4)"),
            (GraphCanvasView.NODE, "Node (5)"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setToolTip(f"Choose {tool} tool")
            button.clicked.connect(
                lambda checked, selected_tool=tool: self.view.set_tool(selected_tool)
                if checked
                else None
            )
            self.tool_group.addButton(button)
            tools_toolbar.addWidget(button)
            self.tool_buttons[tool] = button
        self.tool_buttons[GraphCanvasView.SELECT].setChecked(True)
        self.view.tool_changed.connect(self._sync_tool_button)

        self.status_label = QLineEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setObjectName("graphEditorStatus")
        layout.addWidget(self.status_label)

        self.scene.model_changed.connect(self._mark_modified)
        self.scene.selectionChanged.connect(self._sync_type_selectors)
        self.node_type_combo.currentIndexChanged.connect(self._apply_selected_node_type)
        self.edge_type_combo.currentIndexChanged.connect(
            self._apply_selected_connector_type
        )
        signals.selected_new_file.connect(self.apply_file)
        self._mark_modified(False)
        self.status_label.setText("Create a graph or open a .gwf file.")

    def apply_file(self, file_path: str | Path) -> None:
        if not self.is_active:
            return
        if not file_path or Path(file_path).suffix.lower() != ".gwf":
            return
        try:
            safe_file = safe_path(get_project_root(), str(file_path))
            if not safe_file.is_file():
                raise FileNotFoundError(f"Not a file: {safe_file}")
            source = safe_file.read_bytes()
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.warning(self, "Cannot open graph", str(error))
            return

        if safe_file == self.file_path:
            return
        if not self._confirm_replace_current_graph():
            return
        try:
            self.scene.load_gwf(source)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot open graph", str(error))
            return
        self.file_path = safe_file
        self._mark_modified(False)
        self.undo_stack.clear()
        self.status_label.setText(f"Opened {safe_file.name}.")

    def set_active(self, active: bool) -> None:
        self.is_active = active

    def new_graph(self) -> None:
        if not self._confirm_replace_current_graph():
            return
        self.scene.load_scs("")
        self.file_path = None
        self._mark_modified(True)
        self.undo_stack.clear()
        self.status_label.setText("New graph — save it as a .gwf file.")

    def _create_node_at(self, position: QPointF) -> None:
        index = len(self.scene.nodes) + 1
        while f"node_{index}" in self.scene.nodes:
            index += 1
        try:
            self.undo_stack.push(
                CommandCreateNode(
                    self.scene,
                    f"node_{index}",
                    position,
                    self.node_type_combo.currentData(),
                )
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def _create_connector(
        self,
        source: object,
        target: object,
        source_anchor: QPointF,
        target_anchor: QPointF,
    ) -> None:
        if not isinstance(source, (GraphNode, GraphEdge)) or not isinstance(
            target, (GraphNode, GraphEdge)
        ):
            self._show_tool_error(
                "Connectors must join nodes or other connectors."
            )
            return
        gwf_type, gwf_tag, token = self.edge_type_combo.currentData()
        try:
            self.undo_stack.push(
                CommandCreateConnector(
                    self.scene,
                    source,
                    target,
                    token,
                    gwf_type=gwf_type,
                    gwf_tag=gwf_tag,
                    source_anchor=source_anchor,
                    target_anchor=target_anchor,
                )
            )
            self._show_tool("connector")
        except ValueError as error:
            self._show_tool_error(str(error))

    def _create_bus(self, owner: object, endpoint: QPointF) -> None:
        if not isinstance(owner, GraphNode):
            self._show_tool_error("A bus must start on a node.")
            return
        try:
            self.undo_stack.push(CommandCreateBus(self.scene, owner, endpoint))
        except ValueError as error:
            self._show_tool_error(str(error))

    def _create_contour(self, points: list[QPointF]) -> None:
        try:
            self.undo_stack.push(
                CommandCreateContour(self.scene, points)
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def _commit_move(self, old_positions: dict) -> None:
        command = CommandMoveObjects(self.scene, old_positions)
        if not command.is_empty():
            self.undo_stack.push(command)

    def _show_tool_error(self, message: str) -> None:
        self.status_label.setText(message)

    def _show_tool(self, tool: str) -> None:
        self.status_label.setText(
            {
                GraphCanvasView.SELECT: "Select and move SCg objects.",
                GraphCanvasView.NODE: "Click the canvas to create a node.",
                GraphCanvasView.CONNECTOR:                 "Drag from a node or connector to another graph object to create an arc.",
                GraphCanvasView.BUS: "Drag from an owner node to place a bus.",
                GraphCanvasView.CONTOUR: (
                    "Click contour vertices; double-click or Enter to finish."
                ),
            }[tool]
        )

    def _sync_type_selectors(self) -> None:
        selected_nodes = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphNode)
        ]
        if len(selected_nodes) == 1:
            index = self.node_type_combo.findData(selected_nodes[0].gwf_type)
            if index >= 0:
                self.node_type_combo.setCurrentIndex(index)

        selected_edges = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphEdge)
        ]
        if len(selected_edges) == 1:
            edge = selected_edges[0]
            match = (edge.gwf_type, edge.gwf_tag, edge.edge_type)
            index = self.edge_type_combo.findData(match)
            if index >= 0:
                self.edge_type_combo.setCurrentIndex(index)
        selected_aux = [
            item
            for item in self.scene.selectedItems()
            if isinstance(item, GraphAuxObject)
        ]
        if len(selected_aux) == 1:
            self.rename_edit.setText(selected_aux[0].gwf_element.get("idtf", ""))

    def _sync_tool_button(self, tool: str) -> None:
        button = self.tool_buttons.get(tool)
        if button is not None:
            button.setChecked(True)

    def _apply_selected_node_type(self) -> None:
        nodes = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphNode)
        ]
        if len(nodes) != 1:
            return
        gwf_type = self.node_type_combo.currentData()
        if nodes[0].gwf_type == gwf_type:
            return
        try:
            self.undo_stack.push(
                CommandNodeTypeChange(self.scene, nodes[0], gwf_type)
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def _apply_selected_connector_type(self) -> None:
        edges = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphEdge)
        ]
        if len(edges) != 1:
            return
        gwf_type, gwf_tag, edge_type = self.edge_type_combo.currentData()
        if (edges[0].gwf_type, edges[0].gwf_tag, edges[0].edge_type) == (
            gwf_type,
            gwf_tag,
            edge_type,
        ):
            return
        try:
            self.undo_stack.push(
                CommandConnectorTypeChange(
                    self.scene, edges[0], gwf_type, gwf_tag, edge_type
                )
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def find_node(self) -> None:
        query = self.search_edit.text().strip().casefold()
        if not query:
            self._show_tool_error("Enter a node identifier to find.")
            return
        node = next(
            (
                candidate
                for candidate in self.scene.nodes.values()
                if candidate.identifier.casefold() == query
                or candidate.gwf_idtf.casefold() == query
            ),
            None,
        )
        if node is None:
            self._show_tool_error(f"No node found for '{self.search_edit.text()}'.")
            return
        self.scene.clearSelection()
        node.setSelected(True)
        self.view.centerOn(node)
        self.view.setFocus()

    def fit_graph(self) -> None:
        bounds = self.scene.itemsBoundingRect()
        if bounds.isEmpty():
            bounds = self.scene.sceneRect()
        self.view.fitInView(
            bounds.adjusted(-24, -24, 24, 24),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def export_image(self) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export graph image",
            "graph.png",
            "PNG images (*.png)",
        )
        if not selected_path:
            return
        output_path = Path(selected_path)
        if output_path.suffix.lower() != ".png":
            output_path = output_path.with_suffix(".png")
        bounds = self.scene.itemsBoundingRect().adjusted(-24, -24, 24, 24)
        if bounds.isEmpty():
            bounds = self.scene.sceneRect()
        image = QImage(
            max(1, math.ceil(bounds.width())),
            max(1, math.ceil(bounds.height())),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(QColor("#1e1e1e"))
        painter = QPainter(image)
        self.scene.render(painter, QRectF(image.rect()), bounds)
        painter.end()
        if not image.save(str(output_path)):
            self._show_tool_error(f"Could not export image to {output_path}.")
            return
        self.status_label.setText(f"Exported {output_path.name}.")

    def rename_selected(self) -> None:
        nodes = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphNode)
        ]
        if len(nodes) != 1:
            QMessageBox.information(
                self, "Select a node", "Select exactly one node to rename."
            )
            return
        try:
            self.undo_stack.push(
                CommandRenameNode(
                    self.scene, nodes[0], self.rename_edit.text().strip()
                )
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid node name", str(error))

    def remove_selected(self) -> None:
        command = CommandDeleteSelection(self.scene, self.scene.selectedItems())
        if command.is_empty():
            return
        self.undo_stack.push(command)

    def save(self) -> None:
        if self.file_path is None:
            try:
                project_root = get_project_root()
            except ValueError as error:
                QMessageBox.warning(self, "Cannot save graph", str(error))
                return
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save graph",
                str(project_root / "graph.gwf"),
                "GWF files (*.gwf)",
            )
            if not selected_path:
                return
            selected = Path(selected_path)
            if selected.suffix.lower() != ".gwf":
                selected = selected.with_suffix(".gwf")
            try:
                self.file_path = safe_path(project_root, str(selected))
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Cannot save graph", str(error))
                return

        try:
            safe_file = safe_path(get_project_root(), str(self.file_path))
            content = self.scene.to_gwf()
            safe_file.write_text(content, encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.warning(self, "Cannot save graph", str(error))
            return
        self.file_path = safe_file
        self._mark_modified(False)
        self.status_label.setText(f"Saved {self.file_path.name}.")

    def _confirm_replace_current_graph(self) -> bool:
        if not self.is_modified:
            return True
        answer = QMessageBox.warning(
            self,
            "Unsaved graph",
            "Save changes to the current graph before replacing it?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            self.save()
            return not self.is_modified
        return answer == QMessageBox.StandardButton.Discard

    def _mark_modified(self, modified: bool = True) -> None:
        self.is_modified = modified
        self.save_button.setEnabled(modified or self.file_path is None)
        title = "Save *" if modified else "Save"
        self.save_button.setText(title)
