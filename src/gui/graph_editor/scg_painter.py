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

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from src.gui.graph_editor import graph_theme

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

NODE_OUTLINE_WIDTH = 4.0
GLYPH_WIDTH = 2.5
HATCH_WIDTH = 1.0

# QPen dash pattern values are multiples of the pen width (same ratios as kbe).
DASH_VAR_PERM = (8.0, 6.0)
DASH_TEMP_CONST = (1.0, 1.0)
DASH_TEMP_VAR = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 7.0)
DASH_ACCESS_MARK = (1.0, 2.5)
DASH_FAT_VAR_INSET = (2.5, 10.0 / 4.8)
DASH_FAT_UNKNOWN = (8.0, 6.0)

_pen_cache: dict[tuple, QPen] = {}


def cached_pen(
    color: QColor,
    width: float,
    *,
    style: Qt.PenStyle = Qt.PenStyle.SolidLine,
    cap: Qt.PenCapStyle = Qt.PenCapStyle.FlatCap,
    join: Qt.PenJoinStyle = Qt.PenJoinStyle.RoundJoin,
    dash_pattern: tuple[float, ...] | None = None,
    dash_offset: float = 0.0,
) -> QPen:
    """Shared QPen instances: painting runs per item per frame, so pens are
    cached by their full configuration instead of being reallocated."""
    key = (
        color.rgba(),
        round(width, 2),
        style,
        cap,
        join,
        dash_pattern,
        dash_offset,
    )
    pen = _pen_cache.get(key)
    if pen is None:
        pen = QPen(QBrush(color, Qt.BrushStyle.SolidPattern), width, style, cap, join)
        if dash_pattern is not None:
            pen.setDashPattern(list(dash_pattern))
        pen.setDashOffset(dash_offset)
        _pen_cache[key] = pen
    return pen

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
        cached = _STYLE_CACHE.get((tag, gwf_type))
        if cached is not None:
            return cached
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
        style = cls(
            family=family,
            oriented=oriented,
            polarity=polarity,
            variable=side in {"var", "meta"},
            temporary="temp" in segments,
            unknown_side=side == "-",
        )
        _STYLE_CACHE[(tag, gwf_type)] = style
        return style


_STYLE_CACHE: dict[tuple[str, str], ScgEdgeStyle] = {}


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
    pen = cached_pen(color, NODE_OUTLINE_WIDTH)
    painter.setPen(pen)
    if structure == "not_define":
        painter.setBrush(QBrush(color, Qt.BrushStyle.SolidPattern))
        painter.drawEllipse(shape.boundingRect())
        painter.restore()
        return
    painter.setBrush(QBrush(graph_theme.color("node_fill"), Qt.BrushStyle.SolidPattern))

    # the outline stroke covers half of its width inwards; the glyph must be
    # clipped to the shape inside the border (kbe clips to bound.adjusted(1,1))
    inset = NODE_OUTLINE_WIDTH / 2 + 0.5
    inner = rect.adjusted(inset, inset, -inset, -inset)
    if permanence == "var":
        painter.drawRect(inner)
    else:
        painter.drawEllipse(inner)
    clip = QPainterPath()
    if permanence == "var":
        clip.addRect(inner)
    else:
        clip.addEllipse(inner)
    painter.setClipPath(clip, Qt.ClipOperation.IntersectClip)
    _paint_structure_glyph(painter, color, inner, structure)
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
    painter.setPen(cached_pen(color, GLYPH_WIDTH))
    if structure == "struct":
        painter.setBrush(QBrush(color, Qt.BrushStyle.SolidPattern))
        radius = rect.width() / 8.0
        painter.drawEllipse(
            QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
            )
        )
    elif structure == "abstract":
        painter.setPen(cached_pen(color, HATCH_WIDTH))
        y = top + HATCH_WIDTH
        while y < bottom:
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            y += 3.0
    elif structure == "material":
        painter.setPen(cached_pen(color, HATCH_WIDTH))
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


def polyline_points(path: QPainterPath) -> list[QPointF]:
    """Vertexes of a polyline-style QPainterPath."""
    return [
        QPointF(element.x, element.y)
        for element in (
            path.elementAt(index)
            for index in range(path.elementCount())
        )
    ]


def _trimmed_polyline(
    points: list[QPointF], trim: float
) -> list[QPointF] | None:
    """Polyline shortened by ``trim`` units at the end (kbe corrects the
    last pair point so the line stops at the arrow base)."""
    if len(points) < 2 or trim <= 0:
        return None
    total = 0.0
    lengths: list[float] = []
    for index in range(len(points) - 1):
        segment = QLineF(points[index], points[index + 1]).length()
        lengths.append(segment)
        total += segment
    remaining = total - trim
    if remaining <= 1.0:
        return None
    result = [points[0]]
    covered = 0.0
    for index, segment in enumerate(lengths):
        if covered + segment <= remaining:
            result.append(points[index + 1])
            covered += segment
        else:
            fraction = (remaining - covered) / segment
            start = points[index]
            end = points[index + 1]
            result.append(start + (end - start) * fraction)
            break
    return result


def _polyline_path(points: list[QPointF]) -> QPainterPath:
    path = QPainterPath(points[0])
    for point in points[1:]:
        path.lineTo(point)
    return path


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


def _line_and_arrow_base(
    path: QPainterPath, style: ScgEdgeStyle
) -> tuple[QPainterPath, QPointF | None, QPointF | None]:
    """Line path shortened at the arrow side plus the arrow direction.

    Returns (line_path, unit_direction, end_point); the direction and end
    point are None when no arrow must be drawn.
    """
    if not style.oriented:
        return path, None, None
    total = path.length()
    if total <= ARROW_LENGTH * 1.5:
        return path, None, None
    end = path.pointAtPercent(1.0)
    before = path.pointAtPercent(
        max(0.0, 1.0 - min(ARROW_LENGTH / total, 0.5))
    )
    direction = end - before
    length = math.hypot(direction.x(), direction.y())
    if not length:
        return path, None, None
    unit = QPointF(direction.x() / length, direction.y() / length)
    points = _trimmed_polyline(polyline_points(path), ARROW_LENGTH)
    if points is None:
        return path, None, None
    return _polyline_path(points), unit, end


def _paint_plain_line(painter: QPainter, path: QPainterPath, color: QColor) -> None:
    painter.save()
    painter.setPen(cached_pen(color, LINE_THIN_WIDTH))
    painter.drawPath(path)
    painter.restore()


def _paint_thin_connector(
    painter: QPainter,
    path: QPainterPath,
    style: ScgEdgeStyle,
    color: QColor,
) -> None:
    painter.save()
    pattern: tuple[float, ...] | None = None
    if style.variable:
        pattern = DASH_TEMP_VAR if style.temporary else DASH_VAR_PERM
    elif style.temporary:
        pattern = DASH_TEMP_CONST
    line_path, unit, end = _line_and_arrow_base(path, style)
    pen = cached_pen(color, LINE_THIN_WIDTH, dash_pattern=pattern)
    painter.setPen(pen)
    painter.drawPath(line_path)

    if unit is not None and end is not None:
        _paint_arrow(painter, unit, end, color)

    if style.has_distinct_visual and style.polarity in {"neg", "fuz"}:
        mark_pen = cached_pen(
            color, MARK_WIDTH, dash_pattern=DASH_ACCESS_MARK
        )
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
    line_path, unit, end = _line_and_arrow_base(path, style)
    painter.setPen(cached_pen(color, LINE_FAT_WIDTH))
    painter.drawPath(line_path)

    inset_pattern = DASH_FAT_VAR_INSET if style.variable else None
    inset_pen = cached_pen(
        graph_theme.color("canvas_bg"),
        LINE_FAT_IN_WIDTH,
        dash_pattern=inset_pattern,
        dash_offset=20 if style.variable else 0.0,
    )
    painter.setPen(inset_pen)
    painter.drawPath(line_path)

    if style.unknown_side and not style.variable:
        painter.setPen(
            cached_pen(color, LINE_THIN_WIDTH, dash_pattern=DASH_FAT_UNKNOWN)
        )
        painter.drawPath(line_path)

    if unit is not None and end is not None:
        _paint_arrow(painter, unit, end, color)
    painter.restore()


def _paint_arrow(
    painter: QPainter,
    unit: QPointF,
    end: QPointF,
    color: QColor,
) -> None:
    """Solid filled triangle arrowhead at the end of the polyline (kbe draws
    it with Qt::NoPen and shortens the line up to the arrow base)."""
    perpendicular = QPointF(-unit.y(), unit.x())
    base = end - unit * ARROW_LENGTH
    corner_a = base + perpendicular * (ARROW_WIDTH / 2)
    corner_b = base - perpendicular * (ARROW_WIDTH / 2)
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color, Qt.BrushStyle.SolidPattern))
    painter.drawPolygon([end, corner_a, corner_b])
    painter.restore()
