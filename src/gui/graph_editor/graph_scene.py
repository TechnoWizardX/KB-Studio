"""Graph scene model: nodes/edges/aux objects and GWF/SCs round-trip.

Owns load/save, drag batching and undo-facing helpers; item classes live
in graph_items.py, the editing surface in graph_editor.py.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from copy import deepcopy

from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainterPath
from PySide6.QtWidgets import QGraphicsScene, QWidget

from src.gui.graph_editor.graph_items import (
    GraphAuxObject,
    GraphEdge,
    GraphNode,
    _is_connector_endpoint,
)
from src.gui.graph_editor.graph_types import (
    CONNECTOR_TYPES as _CONNECTOR_TYPES,
    EDGE_TYPES as _EDGE_TYPES,
    IDENTIFIER as _IDENTIFIER,
    NODE_TYPES as _NODE_TYPES,
    SIMPLE_NODE as _SIMPLE_NODE,
    SIMPLE_RELATION as _SIMPLE_RELATION,
    connector_parts as _connector_parts,
    relation_for_gwf as _relation_for_gwf,
)
from src.gui.graph_editor.gwf_codec import (
    gwf_number as _gwf_number,
    parse_gwf_document,
    serialize_gwf,
)


class GraphScene(QGraphicsScene):
    model_changed = Signal()
    rename_requested = Signal(object, str)
    waypoints_changed = Signal(object, list, list)
    dots_changed = Signal(object, object, object)

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
        self._in_drag = False
        # edges queued for one mouse event during drags: nodes moved by the
        # same move event flush their edges once, with final positions
        self._edge_batch: list[GraphEdge] | None = None
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
        node.rename_requester = self.rename_requested.emit
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
        if not _is_connector_endpoint(source) or not _is_connector_endpoint(
            target
        ):
            raise ValueError(
                "SCg connectors can only be attached to nodes, connectors, "
                "contours or buses."
            )
        if source is target:
            raise ValueError("Choose two different graph objects to create a relation.")
        if source.scene() is not self or target.scene() is not self:
            raise ValueError("Both graph objects must belong to this graph.")
        if edge_type not in _EDGE_TYPES:
            raise ValueError(f"Unsupported SCs edge token: '{edge_type}'.")
        if gwf_tag not in {"arc", "pair"} or not (
            gwf_type in {item[1] for item in _CONNECTOR_TYPES}
            or _connector_parts(gwf_tag, gwf_type) is not None
        ):
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
        if (
            isinstance(source, (GraphEdge, GraphAuxObject))
            and source_anchor is not None
        ):
            edge.begin_dot = source.dot_position(source_anchor)
        if (
            isinstance(target, (GraphEdge, GraphAuxObject))
            and target_anchor is not None
        ):
            edge.end_dot = target.dot_position(target_anchor)
        edge.update_path()
        self.addItem(edge)
        self.edges.append(edge)
        self._update_scene_rect()
        edge.waypoints_requester = self.waypoints_changed.emit
        edge.dots_requester = self.dots_changed.emit
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
        if (gwf_type, gwf_tag, scs_token) != (
            edge.gwf_type,
            edge.gwf_tag,
            edge.edge_type,
        ) and (gwf_type, gwf_tag, scs_token) not in allowed:
            # спеллинги из загруженных документов могут не входить в таблицу
            # инструментов; undo обязан уметь их восстановить
            if not str(gwf_type).startswith(("arc/", "pair/")):
                raise ValueError(f"Unsupported SCg connector type: '{gwf_type}'.")
        edge.gwf_type = gwf_type
        edge.gwf_tag = gwf_tag
        edge.edge_type = scs_token
        edge.setToolTip(f"{gwf_tag}: {gwf_type} ({scs_token})")
        edge.update()
        if not self._loading:
            self.model_changed.emit()

    def swap_connector(self, edge: GraphEdge) -> None:
        if edge not in self.edges or edge.scene() is not self:
            raise ValueError("The connector must belong to this graph.")
        (
            edge.source,
            edge.target,
        ) = (
            edge.target,
            edge.source,
        )
        edge.begin_dot, edge.end_dot = edge.end_dot, edge.begin_dot
        edge.waypoints = list(reversed(edge.waypoints))
        edge.update_path()
        self._refresh_connected_edges(edge, set())
        self._update_scene_rect()
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
        if gwf_type != node.gwf_type:
            valid_types = {value for _, value in _NODE_TYPES}
            # типы из загруженных документов могут не входить в таблицу
            # инструментов; undo обязан уметь их восстановить, поэтому
            # отклоняем только не-спеллинги
            if gwf_type not in valid_types and not gwf_type.startswith("node/"):
                raise ValueError(f"Unsupported SCg node type: '{gwf_type}'.")
        if node.scene() is not self:
            raise ValueError("The node must belong to this graph.")
        node.gwf_type = gwf_type
        node.update()
        self.node_moved(node)

    def toggle_content_display(self, nodes=None) -> bool:
        """Switch content display of selected nodes (or the whole graph).

        ``nodes`` restricts the toggle to given nodes: with a mouse/keyboard
        selection only them change (mixed selections collapse to one state:
        expand if anyone is compact, else collapse). ``None`` targets every
        node in the graph. Returns False (and changes nothing) when no node
        with content is available. Display-only: no document modification.
        """
        candidates = self.nodes.values() if nodes is None else nodes
        targets = [node for node in candidates if node.has_content()]
        if not targets:
            return False
        expand = any(not node.content_expanded for node in targets)
        changed = False
        for node in targets:
            if node.content_expanded != expand:
                node.content_expanded = expand
                node.refresh_content_display()
                # connectors are anchored to the glyph shape; reroute them
                # to the square or back to the plain glyph immediately
                self._refresh_connected_edges(node, set())
                changed = True
        if changed:
            self._update_scene_rect()
        return changed

    def set_node_content(self, node: GraphNode, content: ET.Element) -> None:
        """Replace a node's content element and refresh its visuals."""
        if node.scene() is not self:
            raise ValueError("The node must belong to this graph.")
        node.set_node_content(content)
        self._refresh_connected_edges(node, set())
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

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
        removed_objects: set = set(removed_nodes)
        removed_objects.update(removed_edges)
        removed_objects.update(removed_aux)
        # buses of removed nodes go with the node and cascade their connector
        removed_aux.update(
            item
            for item in self.aux_objects
            if item.owner in removed_nodes and item not in removed_aux
        )
        removed_objects.update(removed_aux)
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
            for item in removed_aux:
                if item.scene() is not self:
                    self.addItem(item)
                    self.aux_objects.append(item)
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
            if not _is_connector_endpoint(endpoint) or (
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

    def _set_dragging(self, active: bool, changed: bool | None = None) -> None:
        """Item moves in progress: model_changed is deferred to the drag end
        so per-pixel moves do not trigger save-state work each frame."""
        if self._in_drag == active:
            return
        self._in_drag = active
        if not active and changed is not False:
            # flush a batch left over from an event whose hook was missed
            self._end_edge_batch()
            self._update_scene_rect()
            self.model_changed.emit()

    def _begin_edge_batch(self) -> None:
        """Collect edge refreshes for one mouse event instead of refreshing
        per moved node: an edge touching several dragged nodes would be
        recomputed twice per frame (and the first pass with stale
        endpoints)."""
        self._edge_batch = []

    def _end_edge_batch(self) -> None:
        batch = self._edge_batch
        self._edge_batch = None
        if not batch:
            return
        # insertion order keeps arcs-to-arcs: an arc is queued after its
        # parent edge, so the parent path is fresh when the child reroutes
        for edge in batch:
            if edge.scene() is self:
                edge.update_path()

    def connector_changed(self, edge: GraphEdge) -> None:
        self._refresh_connected_edges(edge, set())
        self._update_scene_rect()
        if not self._loading:
            self.model_changed.emit()

    def _glue_bus_start(self, item: GraphAuxObject) -> None:
        """Keep the first bus point attached to the owner node border."""
        if item.kind != "bus" or item.owner is None or item.scene() is not self:
            return
        scene_path = item.mapToScene(item.path())
        elements = [
            scene_path.elementAt(index)
            for index in range(scene_path.elementCount())
        ]
        if len(elements) < 2:
            return
        second = QPointF(elements[1].x, elements[1].y)
        end = QPointF(elements[-1].x, elements[-1].y)
        start = item.owner.connection_point(second)
        path = QPainterPath(item.mapFromScene(start))
        for element in elements[1:]:
            path.lineTo(item.mapFromScene(QPointF(element.x, element.y)))
        item.setPath(path)
        self._refresh_connected_edges(item, set())

    def node_moved(self, node: GraphNode) -> None:
        self._refresh_connected_edges(node, set())
        for item in self.aux_objects:
            if item.kind == "bus" and item.owner is node:
                self._glue_bus_start(item)
        if not self._in_drag:
            # during a drag the scene rect constant avoids a full-scene
            # invalidation (and the scrollbar recentering repaint) per
            # per-pixel move; it is recomputed once at the drag end
            self._update_scene_rect()
        if not self._loading and not self._in_drag:
            self.model_changed.emit()

    def _update_scene_rect(self) -> None:
        bounds = self.itemsBoundingRect().united(QRectF(0, 0, 1600, 1000))
        adjusted = bounds.adjusted(-200, -200, 200, 200)
        # an unchanged setSceneRect still invalidates the whole scene
        if adjusted != self.sceneRect():
            self.setSceneRect(adjusted)

    def _refresh_connected_edges(
        self, endpoint: GraphNode | GraphEdge, refreshed: set[GraphEdge]
    ) -> None:
        if self._in_drag and self._edge_batch is not None:
            # queue instead of immediate update; the batch flushes once per
            # mouse event with all nodes already at their final positions
            for edge in self.edges:
                if edge.source is not endpoint and edge.target is not endpoint:
                    continue
                if edge not in self._edge_batch:
                    self._edge_batch.append(edge)
                    self._refresh_connected_edges(edge, refreshed)
            return
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
            edges_in_document_order: dict[str, int] = {}
            document_edge_index = 0
            for connector in sector:
                if connector.tag in {"arc", "pair"} and connector.get("id"):
                    edges_in_document_order[
                        connector.get("id", "")
                    ] = document_edge_index
                    document_edge_index += 1
            known_tags = {"node", "arc", "pair", "bus", "contour"}
            self.gwf_sector_extras = [
                deepcopy(child)
                for child in sector
                if child.tag not in known_tags
                or child.tag in {"arc", "pair"}
                and (
                    _connector_parts(child.tag, child.get("type", "")) is None
                    or child.get("id_b") == child.get("id_e")
                )
                or child.tag == "bus"
                and child.get("owner") not in known_node_ids
            ]

            element_ids: dict[str, GraphNode | GraphEdge | GraphAuxObject] = {}
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

            # buses and contours are loaded before connectors so connectors
            # can reference contours as their endpoints
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
                    # contours and buses provide element ids for connectors
                    element_ids[item.gwf_id] = item

            pending_connectors = [
                element
                for tag in ("arc", "pair")
                for element in sector.findall(tag)
                if _connector_parts(tag, element.get("type", "")) is not None
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
                    connector.gwf_document_order = edges_in_document_order.get(
                        connector.gwf_id
                    )
                    element_ids[connector.gwf_id] = connector
                    loaded_connector = True
                if not loaded_connector:
                    self.gwf_sector_extras.extend(
                        deepcopy(item) for item in remaining
                    )
                    break
                pending_connectors = remaining
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
