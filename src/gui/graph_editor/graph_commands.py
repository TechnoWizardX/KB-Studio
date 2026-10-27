"""Undoable commands for the SCg graph editor.

Commands capture no state on construction; ``redo`` applies the change through
the graph scene, and ``undo`` reverts it. Instances of scene objects are cached
so repeated undo/redo cycles reuse the same SCg objects and GWF identities.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from copy import deepcopy
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF
from PySide6.QtGui import QUndoCommand

from src.gui.graph_editor.gwf_codec import empty_content_element

if TYPE_CHECKING:
    from src.gui.graph_editor.graph_scene import GraphScene


class _GraphCommand(QUndoCommand):
    def __init__(self, scene: GraphScene, text: str):
        super().__init__(text)
        self.scene = scene


class CommandCreateNode(_GraphCommand):
    def __init__(
        self,
        scene: GraphScene,
        identifier: str,
        position: QPointF,
        gwf_type: str,
    ):
        super().__init__(scene, f"Create node {identifier}")
        if identifier in scene.nodes:
            raise ValueError(f"A node named '{identifier}' already exists.")
        self.identifier = identifier
        self.position = QPointF(position)
        self.gwf_type = gwf_type
        self.node = None

    def redo(self) -> None:
        if self.node is None:
            self.node = self.scene.add_node(
                self.identifier, self.position, gwf_type=self.gwf_type
            )
        else:
            self.scene._insert_node_instance(self.node, self.position)

    def undo(self) -> None:
        self.scene._remove_node_instance(self.node)


class CommandCreateConnector(_GraphCommand):
    def __init__(
        self,
        scene: GraphScene,
        source,
        target,
        edge_type: str,
        *,
        gwf_type: str,
        gwf_tag: str,
        source_anchor: QPointF | None = None,
        target_anchor: QPointF | None = None,
    ):
        super().__init__(scene, f"Connect objects with {edge_type}")
        self.source = source
        self.target = target
        self.edge_type = edge_type
        self.gwf_type = gwf_type
        self.gwf_tag = gwf_tag
        self.source_anchor = source_anchor
        self.target_anchor = target_anchor
        self.edge = None

    def redo(self) -> None:
        if self.edge is None:
            self.edge = self.scene.connect_nodes(
                self.source,
                self.target,
                self.edge_type,
                gwf_type=self.gwf_type,
                gwf_tag=self.gwf_tag,
                source_anchor=self.source_anchor,
                target_anchor=self.target_anchor,
            )
        else:
            self.scene._insert_edge_instance(self.edge)

    def undo(self) -> None:
        self.scene._remove_edge_instance(self.edge)


class CommandCreateBus(_GraphCommand):
    def __init__(self, scene: GraphScene, owner, endpoint: QPointF):
        super().__init__(scene, "Create bus")
        self.owner = owner
        self.endpoint = QPointF(endpoint)
        self.bus = None

    def redo(self) -> None:
        if self.bus is None:
            self.bus = self.scene.add_bus(self.owner, self.endpoint)
        else:
            self.scene._insert_aux_instance(self.bus)

    def undo(self) -> None:
        self.scene._remove_aux_instance(self.bus)


class CommandCreateContour(_GraphCommand):
    def __init__(self, scene: GraphScene, points: list[QPointF]):
        super().__init__(scene, "Create contour")
        self.points = [QPointF(point) for point in points]
        self.contour = None

    def redo(self) -> None:
        if self.contour is None:
            self.contour = self.scene.add_contour(self.points)
        else:
            self.scene._insert_aux_instance(self.contour)

    def undo(self) -> None:
        self.scene._remove_aux_instance(self.contour)


class CommandDeleteSelection(_GraphCommand):
    def __init__(self, scene: GraphScene, selected):
        super().__init__(scene, "Delete selection")
        removed_nodes, removed_edges, removed_aux = scene._collect_removal(
            list(selected)
        )
        self.removed_nodes = [
            node for node in scene.nodes.values() if node in removed_nodes
        ]
        self.removed_edges = [
            edge for edge in scene.edges if edge in removed_edges
        ]
        self.removed_aux = [
            item for item in scene.aux_objects if item in removed_aux
        ]
        # _remove_objects prunes unknown document elements that reference
        # the removed gwf ids; undo must bring them back.
        self.extras_snapshot = list(scene.gwf_sector_extras)

    def is_empty(self) -> bool:
        return not (self.removed_nodes or self.removed_edges or self.removed_aux)

    def redo(self) -> None:
        self.scene._remove_objects(
            self.removed_nodes, self.removed_edges, self.removed_aux
        )

    def undo(self) -> None:
        self.scene._restore_objects(
            self.removed_nodes, self.removed_edges, self.removed_aux
        )
        self.scene.gwf_sector_extras = list(self.extras_snapshot)


class CommandSwapConnectorOrientation(_GraphCommand):
    def __init__(self, scene: GraphScene, edge):
        super().__init__(scene, "Swap connector direction")
        self.edge = edge
        self.old_source = edge.source
        self.old_target = edge.target
        self.old_begin_dot = edge.begin_dot
        self.old_end_dot = edge.end_dot
        self.old_waypoints = [QPointF(point) for point in edge.waypoints]

    def redo(self) -> None:
        if self.edge.source is self.old_source:
            self.scene.swap_connector(self.edge)

    def undo(self) -> None:
        if self.edge.source is not self.old_source:
            self.scene.swap_connector(self.edge)


class CommandWaypointsChange(_GraphCommand):
    def __init__(
        self,
        scene: GraphScene,
        edge,
        old_waypoints: list[QPointF],
        new_waypoints: list[QPointF],
    ):
        super().__init__(scene, "Change connector route")
        self.edge = edge
        self.old_waypoints = [QPointF(point) for point in old_waypoints]
        self.new_waypoints = [QPointF(point) for point in new_waypoints]

    def _apply(self, waypoints: list[QPointF]) -> None:
        self.edge.waypoints = [QPointF(point) for point in waypoints]
        self.edge.update_path()
        self.scene.connector_changed(self.edge)

    def redo(self) -> None:
        self._apply(self.new_waypoints)

    def undo(self) -> None:
        self._apply(self.old_waypoints)


class CommandConnectorDotsChange(_GraphCommand):
    def __init__(
        self,
        scene: GraphScene,
        edge,
        old_dots: tuple[float, float],
        new_dots: tuple[float, float],
    ):
        super().__init__(scene, "Move connector attach point")
        self.edge = edge
        self.old_dots = (float(old_dots[0]), float(old_dots[1]))
        self.new_dots = (float(new_dots[0]), float(new_dots[1]))

    def _apply(self, dots: tuple[float, float]) -> None:
        self.edge.begin_dot, self.edge.end_dot = dots
        self.edge.update_path()
        self.scene.connector_changed(self.edge)

    def redo(self) -> None:
        self._apply(self.new_dots)

    def undo(self) -> None:
        self._apply(self.old_dots)


class CommandMoveObjects(_GraphCommand):
    def __init__(self, scene: GraphScene, old_positions: dict):
        super().__init__(scene, "Move objects")
        self.moves = [
            (item, QPointF(old), QPointF(item.pos()))
            for item, old in old_positions.items()
            if item.scene() is scene and item.pos() != old
        ]

    def is_empty(self) -> bool:
        return not self.moves

    def redo(self) -> None:
        for item, _old, new in self.moves:
            item.setPos(new)

    def undo(self) -> None:
        for item, old, _new in self.moves:
            item.setPos(old)


class CommandRenameNode(_GraphCommand):
    def __init__(self, scene: GraphScene, node, identifier: str):
        super().__init__(scene, f"Rename node to {identifier}")
        self.node = node
        self.new_identifier = identifier
        self.old_identifier = node.identifier

    def redo(self) -> None:
        if self.node.identifier != self.new_identifier:
            self.scene.rename_node(self.node, self.new_identifier)

    def undo(self) -> None:
        self.scene.rename_node(self.node, self.old_identifier)


class CommandNodeTypeChange(_GraphCommand):
    def __init__(self, scene: GraphScene, node, gwf_type: str):
        super().__init__(scene, f"Change node type to {gwf_type}")
        self.node = node
        self.new_type = gwf_type
        self.old_type = node.gwf_type

    def redo(self) -> None:
        if self.node.gwf_type != self.new_type:
            self.scene.set_node_type(self.node, self.new_type)

    def undo(self) -> None:
        self.scene.set_node_type(self.node, self.old_type)


class CommandNodeContentChange(_GraphCommand):
    def __init__(self, scene: GraphScene, node, content: ET.Element):
        super().__init__(scene, f"Edit content of {node.identifier}")
        self.node = node
        old = node.content_element()
        self.old_content = (
            deepcopy(old) if old is not None else empty_content_element()
        )
        self.new_content = deepcopy(content)

    def redo(self) -> None:
        self.scene.set_node_content(self.node, self.new_content)

    def undo(self) -> None:
        self.scene.set_node_content(self.node, self.old_content)


class CommandConnectorTypeChange(_GraphCommand):
    def __init__(
        self,
        scene: GraphScene,
        edge,
        gwf_type: str,
        gwf_tag: str,
        edge_type: str,
    ):
        super().__init__(scene, f"Change connector type to {edge_type}")
        self.edge = edge
        self.new_type = (gwf_type, gwf_tag, edge_type)
        self.old_type = (edge.gwf_type, edge.gwf_tag, edge.edge_type)

    def redo(self) -> None:
        if (self.edge.gwf_type, self.edge.gwf_tag, self.edge.edge_type) != (
            self.new_type
        ):
            self.scene.set_connector_type(
                self.edge, *self.new_type
            )

    def undo(self) -> None:
        self.scene.set_connector_type(self.edge, *self.old_type)
