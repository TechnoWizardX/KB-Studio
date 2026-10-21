"""Visual alphabet of the SCg notation.

Rendering of nodes and connectors is separated from the scene classes: the
scene keeps responsibility for the model and interaction, this module only
paints glyphs. The drawing rules follow the reference OSTIS/KBE implementation
``sources/plugins/scg/scgalphabet.cpp`` (MIT, ostis-ai/kbe):

* a constant node is a circle, a variable node is a rectangle, and the
  structure glyph (dot, hatching, cross, ...) is drawn inside both shapes;
* "accessory" connectors (arcs and membership pairs) are thin lines with an
  optional filled arrow, dash patterns for variable/temporary connectors and
  perpendicular tick marks for negative/fuzzy ones;
* binary pairs (``pair/...`` without a membership suffix) are thick lines with
  a white core, optionally dashed for variables;
* connector types that have no distinct visual form are returned as the
  ``plain`` style so the SCs token can be drawn next to the line instead.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

# Line widths, in item units (kbe: LINE_* defines).
LINE_THIN_WIDTH = 2.0
LINE_FAT_WIDTH = 7.0
LINE_FAT_IN_WIDTH = 4.2
MARK_WIDTH = 4.0
NEG_MARK_LENGTH = 4.0
FUZ_MARK_LENGTH = 5.0
ARROW_LENGTH = 10.0
ARROW_WIDTH = 8.0
MARK_PERIOD = 28.0
MARK_OFFSET = 22.0

NODE_OUTLINE_WIDTH = 3.0
NODE_FILL = QColor(255, 255, 255, 224)

# QPen dash pattern values are multiples of the pen width (same ratios as kbe).
DASH_VAR_PERM = (8.0, 6.0)
DASH_TEMP_CONST = (1.0, 1.0)
DASH_TEMP_VAR = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 7.0)
DASH_ACCESS_MARK = (1.0, 2.5)
DASH_FAT_VAR_INSET = (2.5, 10.0 / 4.8)
DASH_FAT_UNKNOWN = (8.0, 6.0)

_POSITIVE = {"pos", "neg", "fuz"}
_PERIODS = {"perm", "temp"}
_UNORIENTED = {"noorient", "noorien"}
_MEMBERSHIP = {"membership", "accessory"}
_SIDES = {"const", "var", "meta", "-"}


@dataclass(frozen=True)
class ScgEdgeStyle:
    """Visual style of a connector, parsed from its GWF type string."""

    family: str  # "thin", "fat" or "plain"
    oriented: bool = False
    polarity: str | None = None  # "pos" | "neg" | "fuz"
    variable: bool = False
    temporary: bool = False
    unknown_side: bool = False

    @property
    def has_distinct_visual(self) -> bool:
        return self.family != "plain"

    @classmethod
    def from_connector(cls, tag: str, gwf_type: str) -> "ScgEdgeStyle":
        segments = gwf_type.split("/")
        if tag not in {"arc", "pair"} or not segments or segments[0] != tag:
            return cls(family="plain")

        membership = any(segment in _MEMBERSHIP for segment in segments)
        unoriented = any(segment in _UNORIENTED for segment in segments)
        polarity = next(
            (segment for segment in segments if segment in _POSITIVE), None
        )
        side = segments[1] if len(segments) > 1 else "-"

        if tag == "arc" or membership:
            family = "thin"
        elif segments[0] == "pair":
            family = "fat"
        else:
            family = "plain"

        oriented = (
            not unoriented
            and (tag == "arc" or segments[0] == "pair")
            and (
                family == "fat"
                or membership
                or tag == "arc"
                and any(
                    segment in _POSITIVE or segment in _PERIODS
                    or segment in ("orient", "noorient", "noorien")
                    for segment in segments[2:]
                )
                or tag == "arc"
                and len(segments) <= 3
            )
        )
        return cls(
            family=family,
            oriented=oriented,
            polarity=polarity,
            variable=side in {"var", "meta"},
            temporary="temp" in segments,
            unknown_side=side == "-",
        )


def node_shape(rect: QRectF, permanence: str, structure: str) -> QPainterPath:
    """Outline shape of a node: circle for constants, rect for variables."""
    path = QPainterPath()
    if structure == "not_define":
        inner = rect.adjusted(
            rect.width() * 0.35,
            rect.height() * 0.35,
            -rect.width() * 0.35,
            -rect.height() * 0.35,
        )
        path.addEllipse(inner)
    elif permanence == "var":
        path.addRect(rect)
    else:
        path.addEllipse(rect)
    return path


def paint_node(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    permanence: str,
    structure: str,
) -> None:
    """Draws the node border and its inner structure glyph (kbe paintNode)."""
    painter.save()
    shape = node_shape(rect, permanence, structure)
    pen = QPen(QBrush(color, Qt.BrushStyle.SolidPattern), NODE_OUTLINE_WIDTH)
    painter.setPen(pen)
    if structure == "not_define":
        painter.setBrush(QBrush(color, Qt.BrushStyle.SolidPattern))
        painter.drawEllipse(shape.boundingRect())
        painter.restore()
        return
    painter.setBrush(QBrush(NODE_FILL, Qt.BrushStyle.SolidPattern))

    if permanence == "var":
        inner = rect.adjusted(1.2, 1.2, -1.2, -1.2)
        painter.drawRect(inner)
        clip = QPainterPath()
        clip.addRect(inner)
    else:
        inner = rect.adjusted(1.2, 1.2, -1.2, -1.2)
        painter.drawEllipse(inner)
        clip = QPainterPath()
        clip.addEllipse(inner)
    painter.setClipPath(clip, Qt.ClipOperation.IntersectClip)
    _paint_structure_glyph(painter, color, rect, structure)
    painter.restore()


def _paint_structure_glyph(
    painter: QPainter,
    color: QColor,
    rect: QRectF,
    structure: str,
) -> None:
    """Inner symbols of node structures (kbe paintStruct)."""
    center = rect.center()
    left, right = rect.left(), rect.right()
    top, bottom = rect.top(), rect.bottom()
    glyph_pen = QPen(QBrush(color, Qt.BrushStyle.SolidPattern), 2)
    painter.setPen(glyph_pen)
    if structure == "struct":
        painter.setBrush(QBrush(color, Qt.BrushStyle.SolidPattern))
        radius = rect.width() / 10.0
        painter.drawEllipse(
            QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
            )
        )
    elif structure == "abstract":
        thin = QPen(QBrush(color, Qt.BrushStyle.SolidPattern), 0)
        painter.setPen(thin)
        y = top
        while y < bottom:
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            y += 3.0
    elif structure == "material":
        thin = QPen(QBrush(color, Qt.BrushStyle.SolidPattern), 0)
        painter.setPen(thin)
        distance = right - left
        step = 4.2
        offset = 0.0
        while offset <= distance:
            painter.drawLine(
                QPointF(left + offset, top), QPointF(left, min(bottom, top + offset))
            )
            painter.drawLine(
                QPointF(right - offset, bottom),
                QPointF(right, max(top, bottom - offset)),
            )
            offset += step
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


def paint_edge(
    painter: QPainter,
    path: QPainterPath,
    style: ScgEdgeStyle,
    color: QColor,
) -> None:
    """Draws a connector line with its SCg decorations (kbe paintPair)."""
    if style.family == "plain":
        _paint_plain_line(painter, path, color)
        return
    if style.family == "fat":
        _paint_fat_pair(painter, path, style, color)
        return
    _paint_thin_connector(painter, path, style, color)


def _paint_plain_line(painter: QPainter, path: QPainterPath, color: QColor) -> None:
    painter.save()
    painter.setPen(QPen(color, LINE_THIN_WIDTH))
    painter.drawPath(path)
    painter.restore()


def _paint_thin_connector(
    painter: QPainter,
    path: QPainterPath,
    style: ScgEdgeStyle,
    color: QColor,
) -> None:
    painter.save()
    pen = QPen(color, LINE_THIN_WIDTH)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if style.variable:
        pattern = DASH_TEMP_VAR if style.temporary else DASH_VAR_PERM
    elif style.temporary:
        pattern = DASH_TEMP_CONST
    else:
        pattern = None
    if pattern is not None:
        pen.setDashPattern(list(pattern))
    painter.setPen(pen)
    painter.drawPath(path)

    if style.oriented and path.length() > ARROW_LENGTH:
        _paint_arrow(painter, path, color)

    if style.has_distinct_visual and style.polarity in {"neg", "fuz"}:
        mark_pen = QPen(color, MARK_WIDTH)
        mark_pen.setDashPattern(list(DASH_ACCESS_MARK))
        painter.setPen(mark_pen)
        length = path.length() - ARROW_LENGTH - 3
        distance = MARK_OFFSET
        index = 0
        while distance < length:
            percent = distance / path.length()
            painter.save()
            painter.translate(path.pointAtPercent(percent))
            painter.rotate(-path.angleAtPercent(percent))
            if style.polarity == "neg":
                painter.drawLine(
                    QPointF(0, -NEG_MARK_LENGTH), QPointF(0, NEG_MARK_LENGTH)
                )
            else:
                half = FUZ_MARK_LENGTH if index % 2 else -FUZ_MARK_LENGTH
                painter.drawLine(QPointF(0, half), QPointF(0, 0))
            painter.restore()
            index += 1
            distance += MARK_PERIOD
    painter.restore()


def _paint_fat_pair(
    painter: QPainter,
    path: QPainterPath,
    style: ScgEdgeStyle,
    color: QColor,
) -> None:
    painter.save()
    fat_pen = QPen(color, LINE_FAT_WIDTH)
    fat_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    fat_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(fat_pen)
    painter.drawPath(path)

    inset_pen = QPen(QColor("#1e1e1e"), LINE_FAT_IN_WIDTH)
    inset_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    inset_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if style.variable:
        inset_pen.setDashPattern(list(DASH_FAT_VAR_INSET))
        inset_pen.setDashOffset(20)
    painter.setPen(inset_pen)
    painter.drawPath(path)

    if style.unknown_side and not style.variable:
        overlay = QPen(color, LINE_THIN_WIDTH)
        overlay.setDashPattern(list(DASH_FAT_UNKNOWN))
        painter.setPen(overlay)
        painter.drawPath(path)

    if style.oriented and path.length() > ARROW_LENGTH:
        _paint_arrow(painter, path, color, inset=False)
    painter.restore()


def _paint_arrow(
    painter: QPainter,
    path: QPainterPath,
    color: QColor,
    inset: bool = True,
) -> None:
    """Filled triangle arrowhead at the end of the polyline."""
    end = path.pointAtPercent(1.0)
    near = path.pointAtPercent(max(0.0, 1.0 - min(ARROW_LENGTH / path.length(), 0.5)))
    direction = end - near
    length = math.hypot(direction.x(), direction.y())
    if not length:
        return
    unit = QPointF(direction.x() / length, direction.y() / length)
    perpendicular = QPointF(-unit.y(), unit.x())
    base = end - unit * ARROW_LENGTH
    tip = end
    corner_a = base + perpendicular * (ARROW_WIDTH / 2)
    corner_b = base - perpendicular * (ARROW_WIDTH / 2)
    painter.save()
    if inset:
        painter.setPen(QPen(NODE_FILL, LINE_THIN_WIDTH))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color, Qt.BrushStyle.SolidPattern))
    painter.drawPolygon([tip, corner_a, corner_b])
    painter.restore()
