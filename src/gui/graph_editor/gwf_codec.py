from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.gui.graph_editor.graph_editor import GraphScene

from src.gui.graph_editor.graph_types import (
    builder_safe_connector_type,
    builder_safe_node_type,
)


from PySide6.QtCore import QMimeDatabase

CONTENT_TERM_MIME = "content/term"
_EMPTY_CONTENT: dict[str, str] = {
    "type": "0",
    "mime_type": "",
    "content_visibility": "false",
    "file_name": "",
}


def empty_content_element() -> ET.Element:
    """A ``<content>`` element that marks a node as having no content."""
    return ET.Element("content", dict(_EMPTY_CONTENT))


def guess_content_mime(file_name: str) -> str:
    """Best-effort MIME type for an attached file, kbe-style."""
    mime = QMimeDatabase().mimeTypeForFile(
        file_name, QMimeDatabase.MatchMode.MatchExtension
    )
    name = mime.name()
    return name if name and name != "application/octet-stream" else "application/octet-stream"


def build_content_element(
    c_type: str,
    mime_type: str,
    visible: bool,
    file_name: str,
    text: str,
) -> ET.Element:
    """Build a ``<content>`` element like the kbe GWF writer does.

    Types 1-3 (string, int, real) keep ``text`` raw, type 4 (data) carries a
    ``file_name``, a ``mime_type`` and base64-encoded ``text``; the writer
    emits the same value as CDATA in both cases.
    """
    element = ET.Element(
        "content",
        {
            "type": c_type,
            "mime_type": mime_type,
            "content_visibility": "true" if visible else "false",
            "file_name": file_name,
        },
    )
    if text:
        element.text = text
    return element


def content_elements_equal(first: ET.Element | None, second: ET.Element | None) -> bool:
    """Compare the attributes and payload of two ``<content>`` elements."""
    first_attributes = first.attrib if first is not None else {}
    second_attributes = second.attrib if second is not None else {}
    if first_attributes != second_attributes:
        return False
    return (first.text or "") == (second.text or "")


def gwf_number(element: ET.Element, attribute: str, context: str) -> float:
    try:
        value = float(element.get(attribute, "0"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {attribute} coordinate on {context}.") from error
    if not math.isfinite(value):
        raise ValueError(f"Invalid {attribute} coordinate on {context}.")
    return value


def parse_gwf_document(source: str | bytes) -> tuple[ET.Element, ET.Element, set[str]]:
    try:
        root = ET.fromstring(source)
    except ET.ParseError as error:
        raise ValueError(f"Invalid GWF XML: {error}") from error
    if root.tag != "GWF":
        raise ValueError(f"Expected a GWF document, got <{root.tag}>.")
    version = root.get("version", "")
    if version not in {"1.6", "2.0"}:
        raise ValueError(f"Unsupported GWF version: {version or 'unspecified'}.")
    sector = root.find("staticSector")
    if sector is None:
        raise ValueError("GWF document has no <staticSector>.")

    known_node_ids: set[str] = set()
    known_object_ids: set[str] = set()
    sector_ids = {
        child.get("id") for child in sector if child.get("id") is not None
    }
    for element in sector:
        object_id = element.get("id")
        if element.tag in {"node", "arc", "pair", "bus", "contour"} and not object_id:
            raise ValueError(f"GWF {element.tag} objects must have non-empty ids.")
        if object_id:
            if object_id in known_object_ids:
                raise ValueError(f"Duplicate GWF object id: {object_id}.")
            known_object_ids.add(object_id)
        if element.tag == "node":
            if not object_id:
                raise ValueError("GWF nodes must have non-empty ids.")
            known_node_ids.add(object_id)
            gwf_number(element, "x", f"GWF node {object_id}")
            gwf_number(element, "y", f"GWF node {object_id}")
        elif element.tag in {"arc", "pair"}:
            for endpoint_attribute in ("id_b", "id_e"):
                if element.get(endpoint_attribute) not in sector_ids:
                    raise ValueError(
                        f"GWF {element.tag} {object_id or ''} has an unknown "
                        f"{'start' if endpoint_attribute == 'id_b' else 'end'}."
                    )
            for attribute in ("b_x", "b_y", "e_x", "e_y"):
                gwf_number(element, attribute, f"{element.tag} {object_id or ''}")
            for attribute in ("dotBBalance", "dotEBalance"):
                try:
                    balance = float(element.get(attribute, "0"))
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid {attribute} value on {element.tag} {object_id or ''}."
                    ) from error
                if not math.isfinite(balance):
                    raise ValueError(
                        f"Invalid {attribute} value on {element.tag} {object_id or ''}."
                    )
        elif element.tag == "bus":
            for attribute in ("b_x", "b_y", "e_x", "e_y"):
                gwf_number(element, attribute, f"bus {object_id or ''}")

        if element.tag in {"arc", "pair", "bus", "contour"}:
            for point in element.findall("./points/point"):
                gwf_number(point, "x", f"GWF object {object_id or ''}")
                gwf_number(point, "y", f"GWF object {object_id or ''}")

    for tag in ("arc", "pair"):
        for element in sector.findall(tag):
            if (
                element.get("id_b") not in known_object_ids
                or element.get("id_e") not in known_object_ids
            ):
                raise ValueError(
                    f"GWF {tag} {element.get('id', '')} has an unknown endpoint."
                )

    return root, sector, known_node_ids


def serialize_gwf(scene: GraphScene) -> str:
    root = ET.Element("GWF", scene.gwf_root_attributes)
    root.append(ET.Element("staticSector", scene.gwf_sector_attributes))
    sector = root[-1]

    for node in scene.nodes.values():
        element = (
            deepcopy(node.gwf_element)
            if node.gwf_element is not None
            else ET.Element("node")
        )
        element.attrib.update(
            {
                "type": builder_safe_node_type(node.gwf_type),
                "id": node.gwf_id,
                "parent": element.get("parent", "0"),
                "idtf": node.gwf_idtf,
                "x": str(round(node.pos().x(), 3)),
                "y": str(round(node.pos().y(), 3)),
                "haveBus": (
                    "true"
                    if any(
                        item.kind == "bus" and item.owner is node
                        for item in scene.aux_objects
                    )
                    else "false"
                ),
            }
        )
        if element.find("content") is None:
            ET.SubElement(
                element,
                "content",
                {"type": "0", "mime_type": "content/base", "file_name": ""},
            )
        sector.append(element)

    for item in scene.aux_objects:
        sector.append(item.to_gwf_element())

    edges: list = list(scene.edges)
    if any(
        getattr(edge, "gwf_document_order", None) is not None
        for edge in edges
    ):
        edges.sort(
            key=lambda edge: (
                edge.gwf_document_order
                if getattr(edge, "gwf_document_order", None) is not None
                else math.inf
            )
        )
    for edge in edges:
        element = (
            deepcopy(edge.gwf_element)
            if edge.gwf_element is not None
            else ET.Element(edge.gwf_tag)
        )
        normalized_type = builder_safe_connector_type(edge.gwf_tag, edge.gwf_type)
        # The normalized type carries the family as its first token; a meta
        # arc exported as a meta pair must keep tag and type consistent or
        # the document drops the connector on the next load.
        element.tag = normalized_type.split("/", 1)[0]
        start = edge.begin_element_point()
        end = edge.end_element_point()
        element.attrib.update(
            {
                "type": normalized_type,
                "id": edge.gwf_id,
                "parent": element.get("parent", "0"),
                "idtf": element.get("idtf", ""),
                "id_b": edge.source.gwf_id,
                "id_e": edge.target.gwf_id,
                "b_x": str(round(start.x(), 3)),
                "b_y": str(round(start.y(), 3)),
                "e_x": str(round(end.x(), 3)),
                "e_y": str(round(end.y(), 3)),
                "dotBBalance": str(round(edge.begin_dot, 6)),
                "dotEBalance": str(round(edge.end_dot, 6)),
            }
        )
        points = element.find("points")
        if points is None:
            points = ET.SubElement(element, "points")
        else:
            points.clear()
        for waypoint in edge.waypoints:
            ET.SubElement(
                points,
                "point",
                {
                    "x": str(round(waypoint.x(), 3)),
                    "y": str(round(waypoint.y(), 3)),
                },
            )
        sector.append(element)

    for child in scene.gwf_sector_extras:
        sector.append(deepcopy(child))
    for child in scene.gwf_root_extras:
        root.append(deepcopy(child))
    ET.indent(root, space="    ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
