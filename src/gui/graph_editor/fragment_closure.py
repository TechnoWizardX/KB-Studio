"""Closure copy of the whole linked fragment.

The regular clipboard copy (``GraphScene.copy_fragment``) moves only the
selected objects and drops relationships that point outside the selection.
This module provides the older automating variant used by the
"Copy all incoming/outgoing nodes" context-menu actions: it expands the
selection into a closure, so any connector touching a copied object is
copied together with the objects at its other end (recursively), and buses
pull their owner.

Drop into a clipboard fragment with ``copy_fragment_closure(scene, selected)``
and read the closure size with ``copy_closure(scene, selected)``; paste the
result the usual way (``parse_gwf_document`` + ``prepare_paste_fragment`` +
``insert_fragment``). Refs keep the source ids; the pasting side resolves
collisions.
"""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF

from src.gui.graph_editor.graph_items import (
    GraphAuxObject,
    GraphEdge,
    GraphNode,
)

if TYPE_CHECKING:
    from src.gui.graph_editor.graph_scene import GraphScene


def copy_fragment_closure(scene: GraphScene, selected) -> str:
    """Full GWF document with a closure copy of the given selection.

    The selection closes over dependent objects: any connector touching a
    copied object is copied with the objects at its other end, buses pull
    their owner. Ids stay as in the source document, the pasting side
    resolves collisions."""
    closure = copy_closure(scene, set(selected))
    temp = _closure_scene(scene, closure)
    return temp.to_gwf()


def copy_closure(scene: GraphScene, selected: set) -> set:
    """Expand the selection: connector ends, bus owners, dependent edges."""
    objects = {
        item
        for item in selected
        if isinstance(item, (GraphNode, GraphEdge, GraphAuxObject))
    }
    while True:
        grown = set(objects)
        for edge in scene.edges:
            if not (
                edge in objects
                or edge.source in objects
                or edge.target in objects
            ):
                continue
            grown.add(edge)
            for endpoint in (edge.source, edge.target):
                if endpoint not in grown:
                    grown.add(endpoint)
        for item in scene.aux_objects:
            if item.kind == "bus" and item.owner in objects:
                grown.add(item)
        if grown == objects:
            break
        objects = grown
    return objects


def _closure_scene(scene: GraphScene, closure: set) -> GraphScene:
    """Rebuild the closure inside a fresh scene to serialize it."""
    from src.gui.graph_editor.graph_scene import GraphScene

    temp = GraphScene()
    temp._loading = True
    try:
        node_map: dict[GraphNode, GraphNode] = {}
        for node in scene.nodes.values():
            if node not in closure:
                continue
            clone = temp.add_node(
                node.identifier,
                node.pos(),
                gwf_id=node.gwf_id,
                gwf_type=node.gwf_type,
                gwf_idtf=node.gwf_idtf,
                gwf_element=deepcopy(node.gwf_element),
            )
            node_map[node] = clone
        aux_map: dict = {}
        for item in scene.aux_objects:
            if item not in closure:
                continue
            owner = node_map.get(item.owner) if item.owner is not None else None
            if item.kind == "bus" and owner is None:
                continue
            clone = GraphAuxObject(item.kind, deepcopy(item.gwf_element), owner)
            temp.addItem(clone)
            temp.aux_objects.append(clone)
            aux_map[item] = clone
        endpoint_map: dict = {}
        endpoint_map.update(node_map)
        endpoint_map.update(aux_map)
        edge_map: dict = {}
        for edge in scene.edges:
            if edge not in closure:
                continue
            source = endpoint_map.get(edge.source)
            target = endpoint_map.get(edge.target)
            if source is None or target is None:
                continue
            clone = temp.connect_nodes(
                source,
                target,
                edge.edge_type,
                gwf_id=edge.gwf_id,
                gwf_type=edge.gwf_type,
                gwf_tag=edge.gwf_tag,
                gwf_element=deepcopy(edge.gwf_element),
                waypoints=[QPointF(point) for point in edge.waypoints],
            )
            edge_map[edge] = clone
        endpoint_map.update(edge_map)
    finally:
        temp._loading = False
    return temp
