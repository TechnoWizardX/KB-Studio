import base64
import math
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (
    QBuffer,
    QEvent,
    QIODevice,
    QLineF,
    QPoint,
    QPointF,
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QUndoStack,
)
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox

from src.gui.graph_editor import scg_painter
from src.gui.graph_editor.graph_commands import (
    CommandConnectorDotsChange,
    CommandConnectorTypeChange,
    CommandCreateBus,
    CommandCreateContour,
    CommandCreateConnector,
    CommandCreateNode,
    CommandDeleteSelection,
    CommandMoveObjects,
    CommandNodeContentChange,
    CommandNodeTypeChange,
    CommandRenameNode,
    CommandSwapConnectorOrientation,
    CommandWaypointsChange,
)
from src.gui.graph_editor.graph_editor import (
    _CONNECTOR_TYPES,
    _EDGE_TYPES,
    _ContentDialog,
    _relation_for_gwf,
    GraphAuxObject,
    GraphEditorWidget,
    GraphNode,
    GraphScene,
)
from src.gui.graph_editor.gwf_codec import (
    build_content_element,
    content_elements_equal,
    empty_content_element,
)
from src.gui.graph_editor.scg_painter import ScgEdgeStyle as _ScgEdgeStyle
from src.lark_syntax.parser import SCSParser


def _send_mouse(view, event_type, pos, button=Qt.MouseButton.LeftButton):
    """Send a synthetic QMouseEvent directly to the canvas viewport.

    QTest.mouse* remaps positions through global window coordinates, which is
    unreliable for freshly shown windows (async layout can shift the lookup);
    a directly sent event keeps the exact viewport-local position.
    """
    viewport = view.viewport()
    event = QMouseEvent(
        event_type,
        QPointF(pos),
        viewport.mapToGlobal(QPoint(pos)),
        button,
        button,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport, event)
    return event


def _send_key(view, key: int) -> None:
    """Deliver a key press directly to the canvas view widget."""
    event = QKeyEvent(
        QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(view, event)
    return event


def _closest_point_on_polyline(path: QPainterPath, point: QPointF) -> QPointF:
    """Nearest point on a polyline path (used by bus attachment tests)."""
    best = QPointF(path.elementAt(0).x, path.elementAt(0).y)
    best_distance = math.inf
    for index in range(path.elementCount() - 1):
        first = path.elementAt(index)
        second = path.elementAt(index + 1)
        start = QPointF(first.x, first.y)
        end = QPointF(second.x, second.y)
        vector = end - start
        squared = vector.x() ** 2 + vector.y() ** 2
        if not squared:
            candidate = start
        else:
            fraction = max(
                0.0,
                min(
                    1.0,
                    ((point.x() - start.x()) * vector.x()
                     + (point.y() - start.y()) * vector.y())
                    / squared,
                ),
            )
            candidate = start + vector * fraction
        distance = (
            (point.x() - candidate.x()) ** 2 + (point.y() - candidate.y()) ** 2
        )
        if distance < best_distance:
            best_distance = distance
            best = candidate
    return best


class GraphSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.scene = GraphScene()

    def test_simple_relations_round_trip_and_keep_unsupported_statements(self):
        source = (
            "// preserve comments\n"
            "node_a -> node_b;;\n"
            "node_b;;\n"
            "node_c => nrel_main_idtf: [label];;\n"
        )

        self.scene.load_scs(source)

        self.assertEqual(set(self.scene.nodes), {"node_a", "node_b"})
        self.assertEqual(len(self.scene.edges), 1)
        output = self.scene.to_scs()
        self.assertIn("// preserve comments\n", output)
        self.assertIn("node_c => nrel_main_idtf: [label];;\n", output)
        SCSParser().parse(output)

    def test_added_and_renamed_nodes_serialize_as_valid_scs(self):
        left = self.scene.add_node("left")
        right = self.scene.add_node("right")
        self.scene.connect_nodes(left, right, "=>")
        self.scene.rename_node(left, "source")

        output = self.scene.to_scs()

        self.assertEqual(output, "source => right;;\n")
        SCSParser().parse(output)

    def test_unsupported_edge_types_and_duplicate_names_are_rejected(self):
        node = self.scene.add_node("existing")

        with self.assertRaises(ValueError):
            self.scene.add_node("existing")
        with self.assertRaises(ValueError):
            self.scene.connect_nodes(node, self.scene.add_node("other"), "invalid")
        with self.assertRaises(ValueError):
            self.scene.rename_node(node, "not valid")

    def test_connectors_can_use_other_connectors_as_endpoints(self):
        source = self.scene.add_node("source")
        target = self.scene.add_node("target")
        self.scene.connect_nodes(source, target, "->")
        connector = self.scene.edges[0]

        attribute = self.scene.connect_nodes(source, connector, "->")
        self.assertIs(attribute.source, source)
        self.assertIs(attribute.target, connector)
        self.assertEqual(len(self.scene.edges), 2)

    def test_removing_a_node_also_removes_its_relations(self):
        left = self.scene.add_node("left")
        right = self.scene.add_node("right")
        self.scene.connect_nodes(left, right, "->")
        left.setSelected(True)

        self.scene.remove_selected()

        self.assertEqual(self.scene.nodes, {"right": right})
        self.assertEqual(self.scene.edges, [])
        self.assertEqual(self.scene.to_scs(), "right;;\n")

    def test_removing_a_node_removes_all_dependent_attribute_arcs(self):
        source = self.scene.add_node("source")
        left = self.scene.add_node("left")
        right = self.scene.add_node("right")
        relation = self.scene.connect_nodes(left, right, "->")
        attribute = self.scene.connect_nodes(source, relation, "->")
        relation.setSelected(True)

        self.scene.remove_selected()

        self.assertEqual(self.scene.edges, [])
        self.assertNotIn(relation, self.scene.items())
        self.assertNotIn(attribute, self.scene.items())

    def test_graph_editor_widget_initializes_and_can_start_a_new_graph(self):
        editor = GraphEditorWidget()

        editor.new_graph()

        self.assertTrue(editor.is_modified)
        self.assertIsNone(editor.file_path)
        self.assertTrue(editor.save_button.isEnabled())

    def test_inactive_graph_editor_does_not_open_text_editor_selections(self):
        editor = GraphEditorWidget()
        editor.set_active(False)

        editor.apply_file("/not/a/project/text.scs")

        self.assertIsNone(editor.file_path)
        self.assertEqual(editor.scene.nodes, {})

    def test_graph_editor_ignores_scs_files_until_graphical_scs_is_supported(self):
        editor = GraphEditorWidget()

        editor.apply_file("/not/a/project/text.scs")

        self.assertIsNone(editor.file_path)
        self.assertEqual(editor.scene.nodes, {})

    def test_middle_mouse_drag_pans_the_graph_view(self):
        editor = GraphEditorWidget()
        editor.resize(800, 500)
        editor.show()
        self.app.processEvents()
        before = editor.view.horizontalScrollBar().value()
        start = QPoint(350, 250)
        finish = QPoint(420, 300)

        QTest.mousePress(
            editor.view.viewport(), Qt.MouseButton.MiddleButton, pos=start
        )
        QTest.mouseMove(editor.view.viewport(), finish, 100)
        QTest.mouseRelease(
            editor.view.viewport(), Qt.MouseButton.MiddleButton, pos=finish
        )

        self.assertNotEqual(editor.view.horizontalScrollBar().value(), before)
        editor.close()

    def test_graphical_drag_moves_a_node_and_updates_connected_edge(self):
        editor = GraphEditorWidget()
        editor.resize(900, 600)
        editor.show()
        source = editor.scene.add_node("source", QPoint(100, 100))
        target = editor.scene.add_node("target", QPoint(350, 100))
        editor.scene.connect_nodes(source, target, "->")
        self.app.processEvents()
        original_source = source.pos()
        original_path = editor.scene.edges[0].path()
        start = editor.view.mapFromScene(source.mapToScene(source.boundingRect().center()))
        finish = start + QPoint(70, 55)

        QTest.mousePress(
            editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start
        )
        QTest.mouseMove(editor.view.viewport(), finish, 100)
        QTest.mouseRelease(
            editor.view.viewport(), Qt.MouseButton.LeftButton, pos=finish
        )
        self.app.processEvents()

        self.assertNotEqual(source.pos(), original_source)
        self.assertNotEqual(editor.scene.edges[0].path(), original_path)
        editor.close()

    def test_canvas_node_tool_creates_a_node_at_the_clicked_position(self):
        editor = GraphEditorWidget()
        editor.resize(900, 600)
        editor.show()
        self.app.processEvents()
        editor.view.set_tool(editor.view.NODE)
        scene_point = QPointF(500, 400)
        click = editor.view.mapFromScene(scene_point)

        QTest.mouseClick(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=click)
        self.app.processEvents()

        self.assertEqual(len(editor.scene.nodes), 1)
        node = next(iter(editor.scene.nodes.values()))
        self.assertAlmostEqual(node.pos().x(), 500, delta=2)
        self.assertAlmostEqual(node.pos().y(), 400, delta=2)
        self.assertEqual(node.gwf_type, "node/const/general_node")
        editor.close()

    def test_graph_search_selects_and_centers_matching_node(self):
        editor = GraphEditorWidget()
        editor.resize(900, 600)
        editor.show()
        node = editor.scene.add_node("SearchTarget", QPoint(900, 250))
        editor.search_edit.setText("searchtarget")

        editor.find_node()

        self.assertTrue(node.isSelected())
        self.assertAlmostEqual(
            editor.view.mapToScene(editor.view.viewport().rect().center()).x(),
            node.sceneBoundingRect().center().x(),
            delta=2,
        )
        editor.close()

    def test_zoom_controls_and_png_export(self):
        editor = GraphEditorWidget()
        editor.scene.add_node("visible")
        original_scale = editor.view.transform().m11()
        editor.view.zoom_in()
        self.assertGreater(editor.view.transform().m11(), original_scale)
        editor.view.zoom_out()
        self.assertAlmostEqual(editor.view.transform().m11(), original_scale)

        with tempfile.TemporaryDirectory() as directory:
            output_path = os.path.join(directory, "graph.png")
            with patch(
                "src.gui.graph_editor.graph_editor.QFileDialog.getSaveFileName",
                return_value=(output_path, "PNG images (*.png)"),
            ):
                editor.export_image()
            self.assertTrue(os.path.isfile(output_path))
            self.assertGreater(os.path.getsize(output_path), 0)
        editor.close()

    def test_canvas_connector_tool_can_target_an_existing_connector(self):
        editor = GraphEditorWidget()
        editor.resize(900, 600)
        editor.show()
        source = editor.scene.add_node("source", QPoint(100, 100))
        target = editor.scene.add_node("target", QPoint(350, 100))
        self.app.processEvents()
        editor.view.set_tool(editor.view.CONNECTOR)

        start = editor.view.mapFromScene(source.mapToScene(QPointF(0, 0)))
        finish = editor.view.mapFromScene(target.mapToScene(QPointF(0, 0)))
        _send_mouse(
            editor.view, QEvent.Type.MouseButtonPress, start
        )
        _send_mouse(editor.view, QEvent.Type.MouseMove, finish)
        _send_mouse(
            editor.view, QEvent.Type.MouseButtonRelease, finish
        )
        self.app.processEvents()
        self.assertEqual(len(editor.scene.edges), 1)

        # the first connector grew the scene rect; QGraphicsView recenters
        # its scrollbars asynchronously, so recompute the pressed positions
        self.app.processEvents()
        start = editor.view.mapFromScene(source.mapToScene(QPointF(0, 0)))
        edge_middle = editor.scene.edges[0].path().pointAtPercent(0.5)
        edge_position = editor.view.mapFromScene(edge_middle)
        _send_mouse(
            editor.view, QEvent.Type.MouseButtonPress, start
        )
        _send_mouse(editor.view, QEvent.Type.MouseMove, edge_position)
        _send_mouse(
            editor.view, QEvent.Type.MouseButtonRelease, edge_position
        )
        self.app.processEvents()

        self.assertEqual(
            len(editor.scene.edges),
            2,
            f"status: {editor.status_label.text()!r}",
        )
        self.assertIs(editor.scene.edges[1].target, editor.scene.edges[0])
        editor.close()

    def test_canvas_connector_tool_can_create_an_attribute_arc(self):
        editor = GraphEditorWidget()
        editor.resize(1000, 600)
        editor.show()
        source = editor.scene.add_node("source", QPoint(100, 120))
        left = editor.scene.add_node("left", QPoint(360, 80))
        right = editor.scene.add_node("right", QPoint(360, 240))
        relation = editor.scene.connect_nodes(left, right, "->")
        self.app.processEvents()
        editor.view.set_tool(editor.view.CONNECTOR)

        start = editor.view.mapFromScene(source.scenePos())
        end = editor.view.mapFromScene(relation.path().pointAtPercent(0.5))
        QTest.mousePress(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(editor.view.viewport(), end, 100)
        QTest.mouseRelease(
            editor.view.viewport(), Qt.MouseButton.LeftButton, pos=end
        )
        self.app.processEvents()

        self.assertEqual(len(editor.scene.edges), 2)
        attribute = editor.scene.edges[-1]
        self.assertIs(attribute.source, source)
        self.assertIs(attribute.target, relation)
        self.assertAlmostEqual(attribute.end_dot, 0.5, delta=0.05)

        exported = ET.fromstring(editor.scene.to_gwf())
        arcs = exported.findall("staticSector/arc")
        self.assertEqual(arcs[-1].get("id_e"), relation.gwf_id)
        self.assertEqual(arcs[-1].get("id_b"), source.gwf_id)
        self.assertAlmostEqual(float(arcs[-1].get("dotEBalance")), attribute.end_dot)
        self.assertEqual((arcs[-1].get("e_x"), arcs[-1].get("e_y")), ("0.0", "0.0"))
        editor.close()

    def test_gwf_loads_scg2_spelled_node_and_pair_types(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/perm/general" idtf="concept_question"
                id="n1" x="80" y="140"/>
          <node type="node/const/perm/group" idtf="concept_answer"
                id="n2" x="300" y="80"/>
          <node type="node/const/perm/relation" idtf="nrel_answer"
                id="n3" x="300" y="260"/>
          <pair type="pair/const/pos/perm/orient/membership" id="p1"
                id_b="n1" id_e="n2"
                b_x="80" b_y="140" e_x="300" e_y="80"
                dotBBalance="0" dotEBalance="0"/>
          <pair type="pair/const/-/perm/orient" id="p2"
                id_b="n3" id_e="n2"
                b_x="300" b_y="260" e_x="300" e_y="80"
                dotBBalance="0" dotEBalance="0"/>
          <pair type="pair/const/-/perm/noorien" id="p3"
                id_b="n2" id_e="n3"
                b_x="300" b_y="80" e_x="300" e_y="260"
                dotBBalance="0" dotEBalance="0"/>
        </staticSector></GWF>"""

        self.scene.load_gwf(source)

        self.assertEqual(
            {node.identifier for node in self.scene.nodes.values()},
            {"concept_question", "concept_answer", "nrel_answer"},
        )
        self.assertEqual(len(self.scene.edges), 3)
        self.assertEqual(len(self.scene.gwf_sector_extras), 0)
        edges = {edge.gwf_id: edge for edge in self.scene.edges}
        self.assertEqual(
            edges["p1"].gwf_type, "pair/const/pos/perm/orient/membership"
        )
        self.assertEqual(edges["p1"].edge_type, "=>")
        self.assertEqual(edges["p2"].gwf_type, "pair/const/-/perm/orient")
        self.assertEqual(edges["p2"].edge_type, "=>")
        self.assertEqual(edges["p3"].gwf_type, "pair/const/-/perm/noorien")
        self.assertEqual(edges["p3"].edge_type, "<=>")

        exported = ET.fromstring(self.scene.to_gwf())
        sector = exported.find("staticSector")
        types = [
            (item.get("id"), item.get("type"))
            for item in sector.findall("pair")
        ]
        self.assertEqual(
            types,
            [
                ("p1", "pair/const/pos/perm/orient/membership"),
                ("p2", "pair/const/-/perm/orient"),
                ("p3", "pair/const/-/perm/noorien"),
            ],
        )
        node_types = [
            (item.get("id"), item.get("type"))
            for item in sector.findall("node")
        ]
        self.assertEqual(
            node_types,
            [
                ("n1", "node/const/perm/general"),
                ("n2", "node/const/perm/group"),
                ("n3", "node/const/perm/relation"),
            ],
        )

    def test_string_content_round_trip_and_viewer_label(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/perm/relation" idtf="" id="n1"
                x="100" y="100">
            <content type="1" mime_type="content/term"
                     content_visibility="true" file_name=""><![CDATA[дать список своих возможностей]]></content>
          </node>
          <node type="node/const/perm/relation" idtf="" id="n2"
                x="400" y="100">
            <content type="0" mime_type=""
                     content_visibility="false" file_name=""/>
          </node>
        </staticSector></GWF>"""

        self.scene.load_gwf(source)
        linked, empty = self.scene.nodes["node_1"], self.scene.nodes["node_2"]

        self.assertTrue(linked.has_content())
        self.assertFalse(empty.has_content())
        # compact display (default): marker only, no content text
        self.assertIsNone(linked._content_item)
        self.assertIsNone(linked._content_panel_rect())
        self.assertEqual(linked._content_viewer_text(), "дать список своих возможностей")

        self.scene.toggle_content_display()
        self.assertTrue(linked._content_item.isVisible())
        self.assertEqual(
            linked._content_item.toPlainText(), "дать список своих возможностей"
        )
        self.assertFalse(empty.has_content() and empty._content_item)

        self.scene.toggle_content_display()
        self.assertIsNone(linked._content_panel_rect())
        self.assertFalse(linked._content_item.isVisible())

        output = self.scene.to_gwf()
        reloaded = GraphScene()
        reloaded.load_gwf(output)
        round_trip = reloaded.nodes["node_1"]
        content = round_trip.content_element()
        self.assertEqual(content.get("type"), "1")
        self.assertEqual(content.get("mime_type"), "content/term")
        self.assertEqual(content.get("content_visibility"), "true")
        self.assertEqual(content.text, "дать список своих возможностей")
        self.assertIsNone(round_trip._content_item)

    def test_hidden_content_stays_in_file_without_a_viewer_label(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/perm/relation" idtf="" id="n1"
                x="100" y="100">
            <content type="1" mime_type="content/term"
                     content_visibility="false" file_name=""><![CDATA[скрытый текст]]></content>
          </node>
        </staticSector></GWF>"""

        self.scene.load_gwf(source)
        node = self.scene.nodes["node_1"]

        self.assertTrue(node.has_content())
        self.assertTrue(node._content_item is None or not node._content_item.isVisible())

        output = self.scene.to_gwf()
        content = ET.fromstring(output).find("staticSector/node/content")
        self.assertEqual(content.get("content_visibility"), "false")
        self.assertEqual(content.text, "скрытый текст")

    def test_file_content_round_trips_base64_and_file_name(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/perm/relation" idtf="" id="n1"
                x="100" y="100">
            <content type="4" mime_type="image/png"
                     content_visibility="true" file_name="picture.png"><![CDATA[aGVsbG8=]]></content>
          </node>
        </staticSector></GWF>"""

        self.scene.load_gwf(source)
        node = self.scene.nodes["node_1"]

        self.assertEqual(node._content_viewer_text(), "📎 picture.png (5 B)")

        output = self.scene.to_gwf()
        content = ET.fromstring(output).find("staticSector/node/content")
        self.assertEqual(content.get("type"), "4")
        self.assertEqual(content.get("file_name"), "picture.png")
        self.assertEqual(content.get("mime_type"), "image/png")
        self.assertEqual(content.text, "aGVsbG8=")

    def test_content_display_toggle_switches_to_square_form(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/perm/relation" idtf="" id="n1"
                x="100" y="100">
            <content type="1" mime_type="content/term"
                     content_visibility="true" file_name=""><![CDATA[длинный текст вложения]]></content>
          </node>
        </staticSector></GWF>"""
        self.scene.load_gwf(source)
        node = self.scene.nodes["node_1"]

        self.scene.toggle_content_display()
        panel = node._content_panel_rect()
        self.assertIsNotNone(panel)
        self.assertGreaterEqual(panel.width(), 100)
        self.assertTrue(node._content_item.isVisible())
        self.assertEqual(node._content_item.toPlainText(), "длинный текст вложения")
        # the square form replaces the glyph for connectors
        inside = node.mapFromScene(node.mapToScene(panel.topLeft() + QPointF(10, 10)))
        self.assertTrue(node.shape().contains(inside))
        outside = node.mapFromScene(
            node.mapToScene(QPointF(panel.width() / 2, panel.bottom() + 12))
        )
        self.assertFalse(node.shape().contains(outside))

        self.scene.toggle_content_display()
        self.assertIsNone(node._content_panel_rect())
        self.assertFalse(node._content_item.isVisible())

    def test_content_display_toggle_without_content_is_rejected(self):
        self.scene.add_node("plain")

        self.assertFalse(self.scene.toggle_content_display())
        self.assertFalse(self.scene.content_expanded)

    def test_content_display_key_toggles_with_content(self):
        editor = GraphEditorWidget()
        node = editor.scene.add_node("term")
        editor.scene.set_node_content(
            node,
            build_content_element("1", "content/term", True, "", "текст вложения"),
        )

        _send_key(editor.view, Qt.Key.Key_C)

        self.assertTrue(editor.scene.content_expanded)
        self.assertIsNotNone(node._content_panel_rect())

        _send_key(editor.view, Qt.Key.Key_C)

        self.assertFalse(editor.scene.content_expanded)
        self.assertIsNone(node._content_panel_rect())

    def test_content_display_key_without_content_is_rejected(self):
        editor = GraphEditorWidget()
        editor.scene.add_node("plain")

        _send_key(editor.view, Qt.Key.Key_C)

        self.assertFalse(editor.scene.content_expanded)

    def test_image_content_displays_a_pixmap_in_the_square_form(self):
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image = QImage(40, 30, QImage.Format.Format_RGB32)
        image.fill(QColor("#22aa66"))
        image.save(buffer, "PNG")
        raw = bytes(buffer.data())
        source = (
            "<GWF version=\"2.0\"><staticSector>\n"
            "  <node type=\"node/const/perm/relation\" idtf=\"\" id=\"n1\"\n"
            "        x=\"100\" y=\"100\">\n"
            "    <content type=\"4\" mime_type=\"image/png\"\n"
            "             content_visibility=\"true\" file_name=\"shot.png\">"
            + base64.b64encode(raw).decode("ascii")
            + "</content>\n"
            "  </node>\n"
            "</staticSector></GWF>"
        )

        self.scene.load_gwf(source)
        node = self.scene.nodes["node_1"]
        self.assertIsNotNone(node._content_image())

        self.scene.toggle_content_display()

        self.assertIsNotNone(node._content_panel_rect())
        self.assertTrue(node._content_pixmap.isVisible())
        self.assertTrue(node._content_item is None or not node._content_item.isVisible())

    def test_content_dialog_result_and_removal(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/perm/relation" idtf="" id="n1"
                x="100" y="100">
            <content type="1" mime_type="content/term"
                     content_visibility="true" file_name=""><![CDATA[текст вложения]]></content>
          </node>
        </staticSector></GWF>"""
        self.scene.load_gwf(source)
        node = self.scene.nodes["node_1"]

        dialog = _ContentDialog(node)
        self.assertTrue(dialog.remove_button.isEnabled())
        self.assertEqual(dialog.text_edit.toPlainText(), "текст вложения")
        self.assertTrue(dialog.visible_checkbox.isChecked())
        kept = dialog.result_content()
        self.assertEqual(kept.get("type"), "1")
        self.assertEqual(kept.get("mime_type"), "content/term")

        dialog.text_edit.setPlainText("обновлённый текст")
        edited = dialog.result_content()
        self.assertEqual(edited.text, "обновлённый текст")

        dialog._remove_content()
        self.assertIsNone(dialog.result_content())

        dialog.text_edit.setPlainText("")
        dialog._deleted = False
        self.assertEqual(
            dialog.result_content().get("type"), empty_content_element().get("type")
        )

        fresh = _ContentDialog(self.scene.add_node("fresh"))
        self.assertFalse(fresh.remove_button.isEnabled())

    def test_attached_file_content_dialog_result(self):
        node = self.scene.add_node("holder")
        dialog = _ContentDialog(node)
        self.assertTrue(dialog.text_edit.isEnabled())

        dialog._attached = ("image/png", "photo.png", "aGk=")
        result = dialog.result_content()

        self.assertEqual(result.get("type"), "4")
        self.assertEqual(result.get("file_name"), "photo.png")
        self.assertEqual(result.get("mime_type"), "image/png")
        self.assertEqual(result.text, "aGk=")
        self.assertTrue(dialog.visible_checkbox.isChecked())

    def test_scg2_node_glyphs_follow_the_scg_alphabet(self):
        general = self.scene.add_node(
            "general_node", QPointF(40, 40), gwf_type="node/const/perm/general"
        )
        group = self.scene.add_node(
            "group_node", QPointF(140, 40), gwf_type="node/const/perm/group"
        )
        var_group = self.scene.add_node(
            "var_group", QPointF(240, 40), gwf_type="node/var/perm/group"
        )

        corner = QPointF(11, 11)
        self.assertFalse(
            general._glyph_shape().contains(corner),
            "const node glyph must be a circle",
        )
        self.assertFalse(
            group._glyph_shape().contains(corner),
            "const group node must be a circle with an inner glyph",
        )
        self.assertTrue(
            var_group._glyph_shape().contains(corner),
            "var node glyph must be a rectangle",
        )

    def test_scg2_structure_glyphs_differ_between_node_types(self):
        def ink_count(gwf_type: str) -> int:
            node = GraphNode("test", "1", gwf_type, "test", None)
            image = QImage(48, 48, QImage.Format.Format_ARGB32)
            image.fill(QColor("#1e1e1e"))
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.translate(24, 24)
            node.paint(painter, None, None)
            painter.end()
            # glyph centre sits at image (24, 24); border ring is outside this
            # window; the node interior is dark, so any bright pixel here is
            # an inner structure glyph
            count = 0
            for x in range(18, 31):
                for y in range(18, 31):
                    if image.pixelColor(x, y).value() > 215:
                        count += 1
            return count

        self.assertEqual(
            ink_count("node/const/perm/general"), 0,
            "plain general node has no inner glyph",
        )
        self.assertGreater(ink_count("node/const/perm/struct"), 0)
        self.assertGreater(ink_count("node/const/perm/relation"), 10)
        self.assertGreater(ink_count("node/const/perm/group"), 10)
        self.assertGreater(ink_count("node/const/perm/abstract"), 10)

    def test_scg_edge_styles_follow_the_visual_alphabet(self):
        arc = _ScgEdgeStyle.from_connector(
            "arc", "arc/const/pos/perm/orient/membership"
        )
        self.assertEqual(arc.family, "thin")
        self.assertTrue(arc.oriented)

        var_temp = _ScgEdgeStyle.from_connector(
            "arc", "arc/var/neg/temp/orient/membership"
        )
        self.assertTrue(var_temp.variable)
        self.assertTrue(var_temp.temporary)
        self.assertEqual(var_temp.polarity, "neg")

        fat_pair = _ScgEdgeStyle.from_connector("pair", "pair/const/-/perm/orient")
        self.assertEqual(fat_pair.family, "fat")
        self.assertTrue(fat_pair.oriented)

        fat_var = _ScgEdgeStyle.from_connector("pair", "pair/var/-/perm/noorien")
        self.assertEqual(fat_var.family, "fat")
        self.assertFalse(fat_var.oriented)
        self.assertTrue(fat_var.variable)

        unknown = _ScgEdgeStyle.from_connector("edge", "edge/const/pos")
        self.assertEqual(unknown.family, "plain")
        self.assertFalse(unknown.has_distinct_visual)

    def test_scg_connectors_render_alphabet_styles(self):
        def render(style: _ScgEdgeStyle, oriented: bool = False) -> QImage:
            path = QPainterPath(QPointF(0, -40))
            path.lineTo(QPointF(0, 40))
            image = QImage(100, 100, QImage.Format.Format_ARGB32)
            image.fill(QColor("#1e1e1e"))
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.translate(50, 50)
            scg_painter.paint_edge(painter, path, style, QColor("#a0a0a0"))
            painter.end()
            return image

        fat = render(
            _ScgEdgeStyle.from_connector("pair", "pair/const/-/perm/orient")
        )
        self.assertLess(
            fat.pixelColor(50, 50).value(), 90,
            "fat pair core must be hollow (background colour)",
        )
        rail = max(
            fat.pixelColor(x, 50).value() for x in range(42, 50)
        )
        self.assertGreater(
            rail, 100, "fat pair rails must be visible",
        )

        arc_image = render(
            _ScgEdgeStyle.from_connector(
                "arc", "arc/const/pos/perm/orient/membership"
            ),
            oriented=True,
        )
        self.assertGreater(
            arc_image.pixelColor(50, 87).value(), 100,
            "oriented arc must draw a filled arrowhead",
        )

    def test_membership_pair_draws_an_orientation_arrow(self):
        source_id = self.scene.add_node("source", QPointF(60, 60))
        target_id = self.scene.add_node("target", QPointF(340, 60))

        membership = self.scene.connect_nodes(
            source_id,
            target_id,
            "=>",
            gwf_type="pair/const/pos/perm/orient/membership",
            gwf_tag="pair",
        )
        oriented_pair = self.scene.connect_nodes(
            target_id,
            source_id,
            "=>",
            gwf_type="pair/const/-/perm/orient",
            gwf_tag="pair",
        )
        nooriented_pair = self.scene.connect_nodes(
            source_id,
            target_id,
            "<=>",
            gwf_type="pair/const/-/perm/noorien",
            gwf_tag="pair",
        )

        self.assertTrue(membership._is_oriented_type())
        self.assertTrue(oriented_pair._is_oriented_type())
        self.assertFalse(nooriented_pair._is_oriented_type())

    def test_scg2_types_are_selectable_and_change_is_undoable(self):
        editor = GraphEditorWidget()
        node = editor.scene.add_node("changeable", QPointF(40, 40))
        index = editor.node_type_combo.findData("node/const/perm/group")
        self.assertGreaterEqual(index, 0)

        editor.node_type_combo.setCurrentIndex(index)
        editor._set_node_type(node, "node/const/perm/group")
        self.assertEqual(node.gwf_type, "node/const/perm/group")
        editor.undo_stack.undo()
        self.assertEqual(node.gwf_type, "node/const/general_node")

        membership_tuple = (
            "pair/const/pos/perm/orient/membership",
            "pair",
            "=>",
        )
        membership_index = next(
            (
                index
                for index in range(editor.edge_type_combo.count())
                if editor.edge_type_combo.itemData(index) == membership_tuple
            ),
            -1,
        )
        self.assertGreaterEqual(membership_index, 0)
        editor.close()

    def test_gwf_round_trip_loads_connector_references_in_dependency_order(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/general_node" idtf="source" id="n1" x="80" y="140"/>
          <node type="node/const/general_node" idtf="left" id="n2" x="260" y="80"/>
          <node type="node/const/general_node" idtf="right" id="n3" x="260" y="220"/>
          <arc type="arc/const/pos" id="attribute" id_b="n1" id_e="relation"
               dotBBalance="0" dotEBalance="0.6"/>
          <arc type="arc/const/pos" id="relation" id_b="n2" id_e="n3"/>
        </staticSector></GWF>"""

        self.scene.load_gwf(source)

        self.assertEqual(len(self.scene.edges), 2)
        relation, attribute = self.scene.edges
        self.assertEqual(relation.gwf_id, "relation")
        self.assertEqual(attribute.gwf_id, "attribute")
        self.assertIs(attribute.target, relation)
        exported = ET.fromstring(self.scene.to_gwf())
        arcs = {
            item.get("id"): item
            for item in exported.findall("staticSector/arc")
        }
        self.assertEqual(arcs["attribute"].get("id_e"), "relation")
        self.assertEqual(arcs["attribute"].get("dotEBalance"), "0.6")
        self.assertEqual(arcs["relation"].get("id_e"), "n3")

    def test_node_label_has_full_bounded_geometry(self):
        node = self.scene.add_node("a_very_long_node_identifier")
        label_rect = node.label.boundingRect().translated(node.label.pos())

        self.assertTrue(node.boundingRect().contains(label_rect))
        self.assertAlmostEqual(label_rect.center().y(), 0, delta=0.1)

    def test_node_label_is_rendered_inside_its_full_text_bounds(self):
        self.scene.setBackgroundBrush(Qt.BrushStyle.NoBrush)
        node = self.scene.add_node(
            "visible_long_graph_node_label",
            QPointF(60, 50),
        )
        image = QImage(500, 120, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        self.scene.render(
            painter,
            QRectF(0, 0, 500, 120),
            QRectF(0, 0, 500, 120),
        )
        painter.end()
        label_rect = node.label.boundingRect().translated(node.label.pos())
        label_rect.translate(60, 50)
        rendered_text_pixels = sum(
            1
            for y in range(max(0, int(label_rect.top())), min(120, int(label_rect.bottom()) + 1))
            for x in range(max(0, int(label_rect.left())), min(500, int(label_rect.right()) + 1))
            if image.pixelColor(x, y).alpha() > 0
            and image.pixelColor(x, y).red() > 150
        )

        self.assertGreater(rendered_text_pixels, 0)

    def test_canvas_bus_and_contour_tools_create_gwf_objects(self):
        editor = GraphEditorWidget()
        editor.resize(900, 600)
        editor.show()
        owner = editor.scene.add_node("owner", QPoint(100, 100))
        self.app.processEvents()
        editor.view.set_tool(editor.view.BUS)
        start = editor.view.mapFromScene(owner.mapToScene(QPointF(0, 0)))
        finish = editor.view.mapFromScene(QPointF(250, 240))
        QTest.mousePress(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(editor.view.viewport(), finish, 100)
        QTest.mouseRelease(
            editor.view.viewport(), Qt.MouseButton.LeftButton, pos=finish
        )
        self.app.processEvents()
        self.assertEqual([item.kind for item in editor.scene.aux_objects], ["bus"])

        editor.view.set_tool(editor.view.CONTOUR)
        for point in (QPointF(400, 300), QPointF(500, 300), QPointF(450, 380)):
            QTest.mouseClick(
                editor.view.viewport(),
                Qt.MouseButton.LeftButton,
                pos=editor.view.mapFromScene(point),
            )
        editor.view.setFocus()
        QTest.keyClick(editor.view, Qt.Key.Key_Return)
        self.app.processEvents()

        self.assertEqual(
            [item.kind for item in editor.scene.aux_objects], ["bus", "contour"]
        )
        editor.close()

    def test_connector_attaches_to_contour_endpoint(self):
        node = self.scene.add_node("source", QPointF(120, 120))
        contour = self.scene.add_contour(
            [
                QPointF(300, 200),
                QPointF(420, 200),
                QPointF(420, 320),
                QPointF(300, 320),
            ]
        )

        edge = self.scene.connect_nodes(node, contour, "->")

        self.assertEqual(len(self.scene.edges), 1)
        end = edge.path().pointAtPercent(1.0)
        # attachment lands on the contour border (left edge), not the centre
        self.assertAlmostEqual(end.x(), 300.0, delta=0.5)
        self.assertGreaterEqual(end.y(), 200)
        self.assertLessEqual(end.y(), 320)

        bus = self.scene.add_bus(node, QPointF(700, 300))
        attached = self.scene.connect_nodes(
            node, bus, "->", target_anchor=QPointF(400, 300)
        )
        # the connector ends on the bus line, projected at the drop point
        bus_end = attached.path().pointAtPercent(1.0)
        closest_point = _closest_point_on_polyline(
            bus.mapToScene(bus.path()), bus_end
        )
        self.assertLess(QLineF(bus_end, closest_point).length(), 0.5)

    def test_connector_to_bus_follows_owner_node_movement(self):
        node = self.scene.add_node("source", QPointF(120, 120))
        target = self.scene.add_node("bus_owner", QPointF(500, 260))
        bus = self.scene.add_bus(target, QPointF(600, 300))
        edge = self.scene.connect_nodes(
            node, bus, "->", target_anchor=QPointF(600, 300)
        )
        # the connector is pinned to its anchor point on the bus line
        self.assertAlmostEqual(
            edge.path().pointAtPercent(1.0).x(), 600.0, delta=1.0
        )

        target.setPos(QPointF(560, 320))

        # the bus start stays glued to the owner node border
        glued = bus.cross(0.0)
        node_border = target.connection_point(
            bus.mapToScene(bus.path()).pointAtPercent(1.0)
        )
        self.assertLess(QLineF(glued, node_border).length(), 1.0)
        # and the connector still ends on the bus polyline
        self.assertAlmostEqual(
            edge.path().pointAtPercent(1.0).x(), 600.0, delta=1.0
        )

    def test_connector_to_contour_follows_contour_movement(self):
        node = self.scene.add_node("source", QPointF(120, 120))
        contour = self.scene.add_contour(
            [
                QPointF(300, 200),
                QPointF(420, 200),
                QPointF(420, 320),
                QPointF(300, 320),
            ]
        )
        edge = self.scene.connect_nodes(node, contour, "->")

        contour.setPos(30, 0)

        end = edge.path().pointAtPercent(1.0)
        self.assertAlmostEqual(end.x(), 330.0, delta=0.5)

    def test_connector_to_bus_starts_and_attaches_and_round_trips_gwf(self):
        node = self.scene.add_node("source", QPointF(120, 120))
        owner = self.scene.add_node("bus_owner", QPointF(500, 220))
        bus = self.scene.add_bus(owner, QPointF(600, 300))

        # connector drawn FROM the bus to a node
        from_edge = self.scene.connect_nodes(
            bus, node, "->", source_anchor=QPointF(620, 320)
        )
        begin = from_edge.path().pointAtPercent(0.0)
        closest_point = _closest_point_on_polyline(
            bus.mapToScene(bus.path()), begin
        )
        self.assertLess(QLineF(begin, closest_point).length(), 0.5)

        # connector drawn TO the bus
        to_edge = self.scene.connect_nodes(
            node, bus, "->", target_anchor=QPointF(630, 340)
        )
        end = to_edge.path().pointAtPercent(1.0)
        closest_point = _closest_point_on_polyline(
            bus.mapToScene(bus.path()), end
        )
        self.assertLess(QLineF(end, closest_point).length(), 0.5)

        reloaded = GraphScene()
        reloaded.load_gwf(self.scene.to_gwf())
        self.assertEqual(len(reloaded.edges), 2)
        reloaded_bus = next(
            item for item in reloaded.aux_objects if item.kind == "bus"
        )
        bus_edges = [
            edge
            for edge in reloaded.edges
            if reloaded_bus in (edge.source, edge.target)
        ]
        # both connectors survive with the bus as an endpoint
        self.assertEqual(len(bus_edges), 2)
        for edge in reloaded.edges:
            endpoint = edge.source if edge.source is not reloaded_bus else edge.target
            self.assertIs(endpoint, reloaded.nodes["source"])

    def test_deleting_bus_owner_removes_bus_and_attached_connectors(self):
        node = self.scene.add_node("source", QPointF(120, 120))
        owner = self.scene.add_node("bus_owner", QPointF(500, 220))
        bus = self.scene.add_bus(owner, QPointF(600, 300))
        self.scene.connect_nodes(node, bus, "->")

        removed_nodes, removed_edges, removed_aux = (
            self.scene._collect_removal([owner])
        )
        self.assertIn(bus, removed_aux)
        self.assertEqual(len(removed_edges), 1)
        self.scene._remove_objects(removed_nodes, removed_edges, removed_aux)
        self.assertEqual(self.scene.edges, [])
        self.assertEqual(self.scene.aux_objects, [])

    def test_deleting_bus_keeps_owner_and_removes_its_connectors(self):
        node = self.scene.add_node("source", QPointF(120, 120))
        owner = self.scene.add_node("bus_owner", QPointF(500, 220))
        bus = self.scene.add_bus(owner, QPointF(600, 300))
        self.scene.connect_nodes(node, bus, "->")

        removed_nodes, removed_edges, removed_aux = (
            self.scene._collect_removal([bus])
        )
        self.assertNotIn(owner, removed_nodes)
        self.assertEqual(len(removed_edges), 1)
        self.scene._remove_objects(removed_nodes, removed_edges, removed_aux)
        self.assertIn(owner, self.scene.nodes.values())
        self.assertEqual(self.scene.aux_objects, [])
        self.assertEqual(self.scene.edges, [])

    def test_connector_to_bus_created_through_canvas_widget(self):
        editor = GraphEditorWidget()
        node = editor.scene.add_node("node", QPointF(120, 120))
        owner = editor.scene.add_node("bus_owner", QPointF(500, 220))
        bus = editor.scene.add_bus(owner, QPointF(600, 300))
        editor._create_connector(node, bus, QPointF(200, 150), QPointF(610, 310))
        self.assertEqual(len(editor.scene.edges), 1)
        edge = editor.scene.edges[0]
        self.assertIs(edge.target, bus)
        self.assertAlmostEqual(edge.end_dot, 1.0, delta=0.2)
        editor.close()

    def test_kbe_gwf_with_bus_referencing_arcs_loads_connectors(self):
        reloaded = GraphScene()
        reloaded.load_gwf(
            """<?xml version="1.0" encoding="UTF-8"?>
<GWF version="2.0">
    <staticSector>
        <node type="node/const/perm/general" idtf="owner" shapeColor="0" id="111" parent="0" left="0" top="0" right="110" bottom="28" textColor="164" text_angle="0" text_font="Times New Roman [Arial]" font_size="10" x="500" y="260" haveBus="true" idtf_pos="0">
            <content type="0" mime_type="content/base" file_name="">c2MgdGV4dA==</content>
        </node>
        <node type="node/const/perm/general" idtf="attr" shapeColor="0" id="222" parent="0" left="0" top="0" right="110" bottom="28" textColor="164" text_angle="0" text_font="Times New Roman [Arial]" font_size="10" x="120" y="120" haveBus="false" idtf_pos="0">
            <content type="0" mime_type="content/base" file_name="">c2MgdGV4dA==</content>
        </node>
        <bus type="" idtf="" shapeColor="0" id="333" parent="0" owner="111" b_x="515" b_y="241" e_x="600" e_y="300" haveBus="false" idtf_pos="0">
            <points>
                <point x="560" y="280" />
            </points>
        </bus>
        <arc type="arc/const/neg" idtf="" shapeColor="0" id="444" parent="0" id_b="222" id_e="333" b_x="130" b_y="150" e_x="545" e_y="260" dotBBalance="0.5" dotEBalance="1.2" haveBus="false">
            <points>
                <point x="300" y="200" />
            </points>
        </arc>
    </staticSector>
</GWF>
            """
        )

        self.assertEqual(len(reloaded.aux_objects), 1)
        bus = reloaded.aux_objects[0]
        self.assertEqual(bus.kind, "bus")
        self.assertEqual(len(reloaded.edges), 1)
        edge = reloaded.edges[0]
        self.assertIs(edge.source, reloaded.nodes["attr"])
        self.assertIs(edge.target, bus)
        # dotBBalance on the bus: sector 1 at 20% (attach on the second segment)
        end = edge.path().pointAtPercent(1.0)
        closest_point = _closest_point_on_polyline(
            bus.mapToScene(bus.path()), end
        )
        self.assertLess(QLineF(end, closest_point).length(), 0.5)
        self.assertLessEqual(
            QLineF(QPointF(560.0, 280.0), closest_point).length(), 15.0
        )

    def test_deleting_contour_removes_attached_connector_and_undo_restores(self):
        node = self.scene.add_node("source", QPointF(120, 120))
        contour = self.scene.add_contour(
            [
                QPointF(300, 200),
                QPointF(420, 200),
                QPointF(420, 320),
                QPointF(300, 320),
            ]
        )
        edge = self.scene.connect_nodes(node, contour, "->")
        self.assertEqual(edge.scene(), self.scene)

        contour.setSelected(True)
        stack = QUndoStack()
        stack.push(CommandDeleteSelection(self.scene, [contour]))
        self.assertEqual(self.scene.edges, [])
        self.assertNotIn(contour, self.scene.aux_objects)

        stack.undo()

        self.assertEqual(self.scene.edges, [edge])
        self.assertIn(contour, self.scene.aux_objects)
        self.assertEqual(edge.scene(), self.scene)

    def test_connector_to_contour_survives_gwf_round_trip(self):
        node = self.scene.add_node("source", QPointF(120, 120))
        contour = self.scene.add_contour(
            [
                QPointF(300, 200),
                QPointF(420, 200),
                QPointF(420, 320),
                QPointF(300, 320),
            ]
        )
        self.scene.connect_nodes(node, contour, "->")

        reloaded = GraphScene()
        reloaded.load_gwf(self.scene.to_gwf())

        self.assertEqual(len(reloaded.edges), 1)
        edge = reloaded.edges[0]
        self.assertIsInstance(edge.source, GraphNode)
        self.assertIs(edge.source, reloaded.nodes["source"])
        target = edge.target if isinstance(edge.target, GraphAuxObject) else None
        self.assertIsNotNone(target)
        self.assertTrue(target.is_contour())
        document = ET.fromstring(self.scene.to_gwf())
        sector = document.find("staticSector")
        arc = sector.find("arc")
        self.assertEqual(arc.get("id_e"), target.gwf_id)

    def test_contour_tool_closes_by_clicking_near_the_first_point(self):
        editor = GraphEditorWidget()
        editor.resize(900, 600)
        editor.show()
        editor.view.set_tool(editor.view.CONTOUR)
        for point in (QPointF(400, 300), QPointF(500, 300), QPointF(450, 380)):
            QTest.mouseClick(
                editor.view.viewport(),
                Qt.MouseButton.LeftButton,
                pos=editor.view.mapFromScene(point),
            )
            self.app.processEvents()
        self.assertEqual(editor.scene.aux_objects, [], "far click must not close")
        # a click far from the first vertex keeps collecting points
        far_point = QPointF(600, 250)
        QTest.mouseClick(
            editor.view.viewport(),
            Qt.MouseButton.LeftButton,
            pos=editor.view.mapFromScene(far_point),
        )
        self.app.processEvents()
        self.assertEqual(len(editor.view._contour_points), 4)

        near_first = QPointF(408, 304)
        QTest.mouseClick(
            editor.view.viewport(),
            Qt.MouseButton.LeftButton,
            pos=editor.view.mapFromScene(near_first),
        )
        self.app.processEvents()

        self.assertEqual(
            [item.kind for item in editor.scene.aux_objects], ["contour"]
        )
        contour = editor.scene.aux_objects[0]
        self.assertGreater(contour.path().elementCount(), 3)
        editor.close()

    def test_gwf_load_edit_export_preserves_types_and_unknown_elements(self):
        source = """<?xml version="1.0" encoding="UTF-8"?>
<GWF version="1.6">
  <staticSector>
    <node type="node/const/general_node" idtf="source" shapeColor="5"
          id="n1" parent="0" x="120" y="140" haveBus="false">
      <content type="0" mime_type="content/base" file_name=""/>
    </node>
    <node type="node/var/general_node" idtf="target" id="n2" parent="0"
          x="360" y="140" haveBus="false">
      <content type="0" mime_type="content/base" file_name=""/>
    </node>
    <arc type="arc/var/pos" idtf="" id="e1" parent="0" id_b="n1" id_e="n2"
         b_x="256" b_y="150" e_x="360" e_y="150" dotBBalance="0" dotEBalance="0">
      <points><point x="300" y="190"/></points>
    </arc>
    <bus id="unmodified"/>
  </staticSector>
  <metadata value="preserved"/>
</GWF>
"""

        self.scene.load_gwf(source)
        self.scene.nodes["source"].setPos(180, 210)
        exported = ET.fromstring(self.scene.to_gwf())
        sector = exported.find("staticSector")
        nodes = {node.get("id"): node for node in sector.findall("node")}
        arc = sector.find("arc")

        self.assertEqual(exported.find("metadata").get("value"), "preserved")
        self.assertEqual(sector.find("bus").get("id"), "unmodified")
        self.assertEqual(nodes["n1"].get("type"), "node/const/general_node")
        self.assertEqual(nodes["n1"].get("shapeColor"), "5")
        self.assertEqual(nodes["n1"].get("x"), "180.0")
        self.assertEqual(arc.get("type"), "arc/var/pos")
        self.assertEqual((arc.get("id_b"), arc.get("id_e")), ("n1", "n2"))
        self.assertEqual((arc.get("b_x"), arc.get("b_y")), ("180.0", "210.0"))
        self.assertEqual((arc.get("e_x"), arc.get("e_y")), ("360.0", "140.0"))
        self.assertIsNotNone(arc.find("points"))
        self.assertAlmostEqual(float(arc.find("points/point").get("x")), 300)

    def test_node_glyph_and_connector_are_anchored_at_visible_node_borders(self):
        source = self.scene.add_node("source", QPoint(100, 100))
        target = self.scene.add_node("target", QPoint(300, 100))
        self.scene.set_node_type(source, "node/const/general_node")
        self.scene.set_node_type(target, "node/const/general_node")
        self.scene.connect_nodes(source, target, "->")
        edge = self.scene.edges[0]
        path_start = edge.path().pointAtPercent(0)
        path_end = edge.path().pointAtPercent(1)

        self.assertAlmostEqual(
            path_start.x(), 100 + GraphNode.ICON_SIZE / 2, delta=1
        )
        self.assertAlmostEqual(
            path_end.x(), 300 - GraphNode.ICON_SIZE / 2, delta=1
        )
        self.assertTrue(source.shape().contains(QPointF(0, 0)))
        self.assertTrue(source.boundingRect().contains(source.shape().boundingRect()))

    def test_node_type_can_be_changed_to_const_var_meta_and_special_structures(self):
        node = self.scene.add_node("typed")
        for gwf_type in (
            "node/const/general_node",
            "node/var/attribute",
            "node/meta/group",
        ):
            self.scene.set_node_type(node, gwf_type)
            self.assertEqual(node.gwf_type, gwf_type)
            self.assertFalse(node.shape().isEmpty())

        self.assertEqual(self.scene.to_gwf().count('type="node/meta/group"'), 1)

        self.scene.set_node_type(node, "node/var/not_define")
        # kbe renders var_not_define as a variable (rectangular) node; the
        # small "not defined" circle is reserved for constants
        self.assertTrue(node.shape().contains(QPointF(4, 4)))

        self.scene.set_node_type(node, "node/const/not_define")
        self.assertTrue(node.shape().contains(QPointF(0, 0)))
        self.assertFalse(
            node.shape().contains(QPointF(4, 4)),
            "const not_define must be the small circle",
        )

    def test_connector_type_selector_only_offers_parseable_scs_tokens(self):
        parser = SCSParser()
        for _, _, _, token in _CONNECTOR_TYPES:
            with self.subTest(token=token):
                self.assertIn(token, _EDGE_TYPES)
                parser.parse(f"source {token} target;;")
        self.assertEqual(
            _relation_for_gwf("arc", "arc/const/neg"),
            "-|>",
        )
        self.assertEqual(
            _relation_for_gwf("arc", "arc/var/neg"),
            "_-|>",
        )
        self.assertEqual(
            _relation_for_gwf("arc", "arc/const/pos/temp"),
            "..>",
        )
        self.assertFalse(any("rail" in gwf_type for _, gwf_type, _, _ in _CONNECTOR_TYPES))

    def test_new_bus_and_contour_are_serialized_as_editable_gwf_objects(self):
        owner = self.scene.add_node(
            "owner",
            QPoint(100, 100),
            gwf_type="node/const/general_node",
        )
        bus = self.scene.add_bus(owner, QPointF(240, 180))
        bus.setPos(30, 40)
        old_bus_path = bus.mapToScene(bus.path())
        bus_end_before_move = old_bus_path.pointAtPercent(1)
        contour = self.scene.add_contour(
            [
                QPointF(60, 60),
                QPointF(280, 60),
                QPointF(280, 220),
                QPointF(60, 220),
            ]
        )
        owner.setPos(110, 115)
        contour.setPos(20, 25)
        updated_bus_path = bus.mapToScene(bus.path())
        expected_bus_start = owner.connection_point(bus_end_before_move)
        self.assertAlmostEqual(
            updated_bus_path.pointAtPercent(0).x(),
            expected_bus_start.x(),
            delta=0.001,
        )
        self.assertAlmostEqual(
            updated_bus_path.pointAtPercent(1).x(),
            bus_end_before_move.x(),
            delta=0.001,
        )

        root = ET.fromstring(self.scene.to_gwf())
        sector = root.find("staticSector")

        self.assertEqual(root.get("version"), "2.0")
        self.assertEqual(sector.find("bus").get("owner"), owner.gwf_id)
        expected_bus_start = owner.connection_point(bus_end_before_move)
        self.assertAlmostEqual(
            float(sector.find("bus").get("b_x")),
            expected_bus_start.x(),
            delta=0.001,
        )
        self.assertAlmostEqual(
            float(sector.find("bus").get("b_y")),
            expected_bus_start.y(),
            delta=0.001,
        )
        self.assertAlmostEqual(
            float(sector.find("bus").get("e_x")),
            bus_end_before_move.x(),
            delta=0.001,
        )
        self.assertEqual(len(sector.find("contour/points")), 4)


    def test_gwf_rejects_invalid_xml_and_unknown_versions(self):
        for source in (
            "<GWF version='1.6'><staticSector>",
            "<GWF version='9.0'><staticSector/></GWF>",
        ):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    self.scene.load_gwf(source)

    def test_gwf_load_is_transactional_and_preserves_unsupported_connectors(self):
        original = self.scene.add_node("original")
        malformed = """<GWF version="2.0"><staticSector>
          <node type="node/const/not_define" id="n1" x="nan" y="0"/>
        </staticSector></GWF>"""
        with self.assertRaisesRegex(ValueError, "Invalid x coordinate"):
            self.scene.load_gwf(malformed)
        self.assertIs(self.scene.nodes["original"], original)
        invalid_balance = """<GWF version="2.0"><staticSector>
          <node type="node/const/general_node" id="n1" x="0" y="0"/>
          <node type="node/const/general_node" id="n2" x="100" y="0"/>
          <arc type="arc/const/pos" id="a1" id_b="n1" id_e="n2"
               dotEBalance="nan"/>
        </staticSector></GWF>"""
        with self.assertRaisesRegex(ValueError, "Invalid dotEBalance"):
            self.scene.load_gwf(invalid_balance)
        self.assertIs(self.scene.nodes["original"], original)

        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/general_node" idtf="left" id="n1" x="0" y="0"/>
          <node type="node/const/general_node" idtf="right" id="n2" x="100" y="0"/>
          <arc type="arc/future/unknown" id="KBStudioEdge1" id_b="n1" id_e="n2"/>
        </staticSector></GWF>"""
        self.scene.load_gwf(source)
        self.scene.connect_nodes(self.scene.nodes["left"], self.scene.nodes["right"], "->")

        self.assertEqual(len(self.scene.edges), 1)
        self.assertEqual(
            self.scene._existing_gwf_ids(),
            {"n1", "n2", "KBStudioEdge1", "KBStudioEdge2"},
        )
        exported = ET.fromstring(self.scene.to_gwf())
        arcs = exported.findall("staticSector/arc")
        preserved = next(arc for arc in arcs if arc.get("type") == "arc/future/unknown")
        editable = next(arc for arc in arcs if arc.get("type") == "arc/-/-")
        self.assertEqual(preserved.get("id"), "KBStudioEdge1")
        self.assertEqual(editable.get("id"), "KBStudioEdge2")

    def test_gwf_preserves_self_referential_connectors_as_opaque_objects(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/general_node" idtf="node" id="n1" x="20" y="30"/>
          <arc type="arc/const/pos" id="a1" id_b="n1" id_e="n1"/>
        </staticSector></GWF>"""

        self.scene.load_gwf(source)

        self.assertEqual(self.scene.edges, [])
        exported = ET.fromstring(self.scene.to_gwf())
        arc = exported.find("staticSector/arc")
        self.assertIsNotNone(arc)
        self.assertEqual((arc.get("id_b"), arc.get("id_e")), ("n1", "n1"))

    def test_loading_a_new_gwf_replaces_previous_auxiliary_objects(self):
        first = """<GWF version="2.0"><staticSector>
          <node type="node/const/general_node" idtf="owner" id="n1" x="0" y="0"/>
          <bus id="b1" owner="n1" b_x="10" b_y="10" e_x="80" e_y="80"/>
        </staticSector></GWF>"""
        second = """<GWF version="2.0"><staticSector>
          <node type="node/const/general_node" idtf="other" id="n2" x="0" y="0"/>
        </staticSector></GWF>"""

        self.scene.load_gwf(first)
        self.assertEqual(len(self.scene.aux_objects), 1)
        self.scene.load_gwf(second)

        self.assertEqual(self.scene.aux_objects, [])
        self.assertNotIn("<bus", self.scene.to_gwf())

    def test_gwf_reads_legacy_windows_1251_xml_declaration(self):
        source = """<?xml version="1.0" encoding="windows-1251"?>
<GWF version="1.6">
  <staticSector>
    <node type="node/const/not_define" idtf="узел" id="n1" parent="0"
          x="10" y="20" haveBus="false">
      <content type="0" mime_type="content/base" file_name=""/>
    </node>
  </staticSector>
</GWF>
""".encode("cp1251")

        self.scene.load_gwf(source)

        self.assertEqual(self.scene.nodes["node_1"].gwf_idtf, "узел")
        self.assertIn('idtf="узел"', self.scene.to_gwf())


class GraphEditorUndoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.scene = GraphScene()
        self.stack = QUndoStack()

    def test_create_node_undo_redo_keeps_identity(self):
        self.stack.push(
            CommandCreateNode(
                self.scene, "alpha", QPointF(10, 20), "node/const/general_node"
            )
        )
        node = self.scene.nodes["alpha"]
        gwf_id = node.gwf_id

        self.stack.undo()

        self.assertNotIn("alpha", self.scene.nodes)
        self.assertEqual(self.scene.items(), [])

        self.stack.redo()

        self.assertIs(self.scene.nodes["alpha"], node)
        self.assertEqual(node.gwf_id, gwf_id)
        self.assertEqual(node.scenePos(), QPointF(10, 20))
        self.assertEqual(node.pos(), QPointF(10, 20))

    def test_rename_command_undo_restores_identifier(self):
        node = self.scene.add_node("alpha")
        self.scene.add_node("beta")
        self.stack.push(CommandRenameNode(self.scene, node, "gamma"))
        self.assertEqual(self.scene.nodes["gamma"], node)

        self.stack.undo()

        self.assertEqual(self.scene.nodes["alpha"], node)

    def test_node_type_change_command_undo(self):
        node = self.scene.add_node("alpha")
        self.stack.push(CommandNodeTypeChange(self.scene, node, "node/var/atom"))
        self.assertEqual(node.gwf_type, "node/var/atom")

        self.stack.undo()

        self.assertEqual(node.gwf_type, "node/const/general_node")

    def test_connector_type_change_command_undo(self):
        source = self.scene.add_node("source")
        target = self.scene.add_node("target")
        edge = self.scene.connect_nodes(source, target, "->")
        self.stack.push(
            CommandConnectorTypeChange(self.scene, edge, "pair/const/orient", "pair", "=>")
        )
        self.assertEqual(edge.gwf_tag, "pair")

        self.stack.undo()

        self.assertEqual((edge.gwf_type, edge.gwf_tag, edge.edge_type), ("arc/-/-", "arc", "->"))

    def test_node_content_change_command_undo_redo(self):
        node = self.scene.add_node("term")
        content = build_content_element(
            "1", "content/term", True, "", "новое вложение"
        )
        self.stack.push(CommandNodeContentChange(self.scene, node, content))
        self.assertTrue(node.has_content())
        self.assertEqual(node._content_viewer_text(), "новое вложение")
        self.assertIn("новое вложение", self.scene.to_gwf())

        self.stack.undo()

        self.assertFalse(node.has_content())
        self.assertNotIn("новое вложение", self.scene.to_gwf())

        self.stack.redo()

        self.assertTrue(node.has_content())
        self.assertEqual(node._content_viewer_text(), "новое вложение")

    def test_node_content_change_undo_restores_file_content(self):
        source = """<GWF version="2.0"><staticSector>
          <node type="node/const/perm/relation" idtf="" id="n1"
                x="100" y="100">
            <content type="1" mime_type="content/term"
                     content_visibility="true" file_name=""><![CDATA[исходный текст]]></content>
          </node>
        </staticSector></GWF>"""
        self.scene.load_gwf(self.scene.to_gwf()) if False else None
        node = self.scene.add_node("term")
        content = build_content_element(
            "4", "image/png", True, "photo.png", "aGk="
        )
        self.scene.set_node_content(node, content)
        self.assertEqual(node._content_viewer_text(), "📎 photo.png (2 B)")

        command = CommandNodeContentChange(
            self.scene, node, build_content_element(
                "1", "content/term", True, "", "string replacement"
            )
        )
        self.stack.push(command)

        self.assertIn("string replacement", self.scene.to_gwf())

        self.stack.undo()

        restored = node.content_element()
        self.assertEqual(restored.get("type"), "4")
        self.assertEqual(restored.get("file_name"), "photo.png")
        self.assertEqual(restored.text, "aGk=")

    def test_delete_selection_undo_restores_edges_and_bindings(self):
        source = self.scene.add_node("source", QPointF(100, 120))
        left = self.scene.add_node("left", QPointF(360, 80))
        right = self.scene.add_node("right", QPointF(360, 240))
        relation = self.scene.connect_nodes(left, right, "->")
        attribute = self.scene.connect_nodes(
            source, relation, "->", target_anchor=relation.path().pointAtPercent(0.5)
        )
        command = CommandDeleteSelection(self.scene, [relation])
        self.stack.push(command)
        self.assertEqual(self.scene.edges, [])
        self.assertEqual(set(self.scene.nodes.values()), {source, left, right})

        self.stack.undo()

        self.assertEqual(self.scene.edges, [relation, attribute])
        self.assertLess(self.scene.edges.index(relation), self.scene.edges.index(attribute))
        self.assertIs(attribute.source, source)
        self.assertIs(attribute.target, relation)
        root = ET.fromstring(self.scene.to_gwf())
        arcs = {arc.get("id"): arc for arc in root.findall("staticSector/arc")}
        self.assertEqual(arcs[attribute.gwf_id].get("id_e"), relation.gwf_id)

    def test_create_bus_and_contour_undo(self):
        owner = self.scene.add_node("owner", QPointF(100, 100))
        self.stack.push(CommandCreateBus(self.scene, owner, QPointF(240, 180)))
        self.stack.push(
            CommandCreateContour(
                self.scene,
                [QPointF(60, 60), QPointF(280, 60), QPointF(280, 220)],
            )
        )
        bus, contour = self.scene.aux_objects
        self.stack.undo()
        self.assertEqual(self.scene.aux_objects, [bus])
        self.stack.undo()
        self.assertEqual(self.scene.aux_objects, [])
        self.stack.redo()
        self.assertEqual(self.scene.aux_objects, [bus])
        self.stack.redo()
        self.assertEqual([item.kind for item in self.scene.aux_objects], ["bus", "contour"])
        self.assertEqual(self.scene.aux_objects[0].gwf_id, bus.gwf_id)

    def test_move_objects_command_undo_restores_positions(self):
        source = self.scene.add_node("source", QPointF(0, 0))
        target = self.scene.add_node("target", QPointF(200, 0))
        old_positions = {source: QPointF(source.pos()), target: QPointF(target.pos())}
        source.setPos(50, 60)
        target.setPos(240, 30)
        self.stack.push(CommandMoveObjects(self.scene, old_positions))

        self.stack.undo()

        self.assertEqual(source.pos(), QPointF(0, 0))
        self.assertEqual(target.pos(), QPointF(200, 0))

        self.stack.redo()

        self.assertEqual(source.pos(), QPointF(50, 60))
        self.assertEqual(target.pos(), QPointF(240, 30))

    def test_dragging_a_node_is_recorded_and_undoable(self):
        editor = GraphEditorWidget()
        editor.resize(900, 600)
        editor.show()
        source = editor.scene.add_node("source", QPointF(100, 100))
        target = editor.scene.add_node("target", QPointF(350, 100))
        editor.scene.connect_nodes(source, target, "->")
        self.app.processEvents()
        original_source = QPointF(source.pos())
        start = editor.view.mapFromScene(source.mapToScene(source.boundingRect().center()))
        finish = start + QPoint(70, 55)
        QTest.mousePress(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(editor.view.viewport(), finish, 100)
        QTest.mouseRelease(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=finish)
        self.app.processEvents()
        self.assertTrue(editor.undo_stack.canUndo())
        self.assertTrue(editor.undo_button.isEnabled())

        editor.undo_stack.undo()

        self.assertEqual(source.pos(), original_source)
        self.assertFalse(editor.undo_stack.canUndo())
        self.assertTrue(editor.undo_stack.canRedo())
        editor.close()

    def test_widget_creation_and_selection_sync_do_not_pollute_undo_stack(self):
        editor = GraphEditorWidget()
        editor._create_node_at(QPointF(100, 100))
        self.assertEqual(editor.undo_stack.count(), 1)
        node = editor.scene.nodes["node_1"]

        node.setSelected(True)
        self.app.processEvents()

        self.assertEqual(editor.undo_stack.count(), 1)

        index = editor.node_type_combo.findData("node/var/atom")
        editor.node_type_combo.setCurrentIndex(index)
        self.assertEqual(editor.undo_stack.count(), 2)
        self.assertEqual(node.gwf_type, "node/var/atom")
        editor.undo_stack.setIndex(0)
        self.assertEqual(node.gwf_type, "node/const/general_node")
        editor.close()

    def test_widget_delete_uses_undo_stack(self):
        editor = GraphEditorWidget()
        source = editor.scene.add_node("source", QPointF(100, 100))
        target = editor.scene.add_node("target", QPointF(350, 100))
        editor.scene.connect_nodes(source, target, "->")
        source.setSelected(True)
        editor.remove_selected()

        self.assertEqual(editor.scene.nodes, {"target": target})
        self.assertEqual(editor.scene.edges, [])

        editor.undo_stack.undo()

        self.assertIn("source", editor.scene.nodes)
        self.assertEqual(editor.scene.edges, editor.scene.edges)
        self.assertEqual(len(editor.scene.edges), 1)
        self.assertIs(editor.scene.edges[0].source, source)
        editor.close()

    def test_opening_a_file_clears_the_undo_stack(self):
        editor = GraphEditorWidget()
        editor._create_node_at(QPointF(50, 50))
        self.assertTrue(editor.undo_stack.canUndo())
        with tempfile.TemporaryDirectory() as directory:
            graph_path = os.path.join(directory, "graph.gwf")
            with open(graph_path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<GWF version="2.0"><staticSector>'
                    '<node type="node/const/general_node" idtf="loaded" id="n1" x="10" y="10"/>'
                    "</staticSector></GWF>"
                )
            with patch(
                "src.gui.graph_editor.graph_editor.get_project_root",
                return_value=Path(directory),
            ), patch.object(
                QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard
            ):
                editor.apply_file(graph_path)

        self.assertFalse(editor.undo_stack.canUndo())
        self.assertFalse(editor.undo_stack.canRedo())
        self.assertIn("loaded", editor.scene.nodes)
        editor.close()

    def test_inplace_label_rename_goes_through_undo_stack(self):
        editor = GraphEditorWidget()
        node = editor.scene.add_node("alpha")
        self.app.processEvents()

        node._on_label_committed("beta")

        self.assertEqual(node.identifier, "beta")
        self.assertIn("beta", editor.scene.nodes)
        self.assertEqual(editor.undo_stack.count(), 1)

        editor.undo_stack.undo()

        self.assertEqual(node.identifier, "alpha")
        self.assertEqual(node.gwf_idtf, "alpha")
        self.assertEqual(node.label.toPlainText(), "alpha")
        editor.close()

    def test_inplace_duplicate_rename_is_rejected_and_reverted(self):
        editor = GraphEditorWidget()
        editor.scene.add_node("alpha")
        other = editor.scene.add_node("gamma")
        count = editor.undo_stack.count()

        other._on_label_committed("alpha")

        self.assertIn("gamma", editor.scene.nodes)
        self.assertEqual(other.label.toPlainText(), "gamma")
        self.assertEqual(editor.undo_stack.count(), count)
        editor.close()

    def test_inplace_rename_keeps_name_unchanged_without_command(self):
        editor = GraphEditorWidget()
        node = editor.scene.add_node("alpha")
        count = editor.undo_stack.count()

        node._on_label_committed("alpha")

        self.assertEqual(editor.undo_stack.count(), count)
        editor.close()

    def test_waypoint_commands_change_connector_route(self):
        source = self.scene.add_node("source", QPointF(100, 100))
        target = self.scene.add_node("target", QPointF(400, 100))
        edge = self.scene.connect_nodes(source, target, "->")
        old_waypoints = []
        new_waypoints = [QPointF(250, 200), QPointF(320, 60)]
        self.stack.push(
            CommandWaypointsChange(self.scene, edge, old_waypoints, new_waypoints)
        )
        self.assertEqual(edge.waypoints, new_waypoints)

        exported = ET.fromstring(self.scene.to_gwf())
        points = exported.findall("staticSector/arc/points/point")
        self.assertEqual(len(points), 2)
        self.assertEqual(float(points[0].get("x")), 250.0)

        self.stack.undo()

        self.assertEqual(edge.waypoints, [])
        self.assertEqual(
            ET.fromstring(self.scene.to_gwf()).findall("staticSector/arc/points/point"),
            [],
        )

        self.stack.redo()

        self.assertEqual(edge.waypoints, new_waypoints)

    def test_dot_handles_are_only_shown_for_connector_endpoints(self):
        source = self.scene.add_node("source", QPointF(0, 0))
        target = self.scene.add_node("target", QPointF(300, 0))
        edge = self.scene.connect_nodes(source, target, "->")
        attribute = self.scene.connect_nodes(
            self.scene.add_node("attr", QPointF(150, 200)),
            edge,
            "->",
            target_anchor=edge.path().pointAtPercent(0.5),
        )

        midpoint = edge.path().pointAtPercent(0.5)
        self.assertIsNone(edge._dot_handle_at(midpoint))
        hit = attribute._dot_handle_at(
            attribute.path().pointAtPercent(1.0)
        )
        self.assertEqual(hit, "end")
        self.assertIsNone(
            attribute._dot_handle_at(attribute.path().pointAtPercent(0.0))
        )

    def test_dot_drag_moves_attach_point_and_stays_on_connector(self):
        source = self.scene.add_node("source", QPointF(0, 0))
        target = self.scene.add_node("target", QPointF(300, 0))
        edge = self.scene.connect_nodes(source, target, "->")
        attribute = self.scene.connect_nodes(
            self.scene.add_node("attr", QPointF(150, 200)),
            edge,
            "->",
            target_anchor=edge.path().pointAtPercent(0.25),
        )
        self.assertLess(attribute.end_dot, 0.5)

        attribute._drag_dot_side = "end"
        attribute._drag_original_dots = (attribute.begin_dot, attribute.end_dot)
        attribute._apply_dragged_dot(edge.dot_position(edge.path().pointAtPercent(0.75)))

        self.assertGreater(attribute.end_dot, 0.5)
        anchor = attribute.path().pointAtPercent(1.0)
        self.assertEqual(edge.mapFromScene(anchor).y(), 0)

    def test_dot_requester_routes_through_widget_undo_stack(self):
        editor = GraphEditorWidget()
        source = editor.scene.add_node("source", QPointF(0, 0))
        target = editor.scene.add_node("target", QPointF(300, 0))
        edge = editor.scene.connect_nodes(source, target, "->")
        attribute = editor.scene.connect_nodes(
            editor.scene.add_node("attr", QPointF(150, 200)),
            edge,
            "->",
            target_anchor=edge.path().pointAtPercent(0.25),
        )
        old_dots = (attribute.begin_dot, attribute.end_dot)
        new_dots = (old_dots[0], old_dots[1] + 0.5)
        count = editor.undo_stack.count()

        attribute.dots_requester(attribute, old_dots, new_dots)

        self.assertEqual(editor.undo_stack.count(), count + 1)
        self.assertAlmostEqual(attribute.end_dot, new_dots[1], delta=1e-9)

        editor.undo_stack.undo()

        self.assertAlmostEqual(attribute.end_dot, old_dots[1], delta=1e-9)
        editor.close()

    def test_connector_dots_command_round_trips(self):
        source = self.scene.add_node("source", QPointF(0, 0))
        target = self.scene.add_node("target", QPointF(300, 0))
        edge = self.scene.connect_nodes(source, target, "->")
        attribute = self.scene.connect_nodes(
            self.scene.add_node("attr", QPointF(150, 200)),
            edge,
            "->",
            target_anchor=edge.path().pointAtPercent(0.25),
        )
        old_dots = (attribute.begin_dot, attribute.end_dot)
        new_dots = (old_dots[0], old_dots[1] + 0.25)

        self.stack.push(CommandConnectorDotsChange(self.scene, attribute, old_dots, new_dots))
        self.assertAlmostEqual(attribute.end_dot, new_dots[1], delta=1e-9)

        self.stack.undo()
        self.assertAlmostEqual(attribute.end_dot, old_dots[1], delta=1e-9)
        self.stack.redo()
        self.assertAlmostEqual(attribute.end_dot, new_dots[1], delta=1e-9)

    def test_waypoint_requester_routes_through_widget_undo_stack(self):
        editor = GraphEditorWidget()
        source = editor.scene.add_node("source", QPointF(100, 100))
        target = editor.scene.add_node("target", QPointF(400, 100))
        edge = editor.scene.connect_nodes(source, target, "->")
        old_waypoints = []
        new_waypoints = [QPointF(250, 200)]
        count = editor.undo_stack.count()

        edge.waypoints_requester(edge, old_waypoints, new_waypoints)

        self.assertEqual(editor.undo_stack.count(), count + 1)
        self.assertEqual(edge.waypoints, new_waypoints)

        editor.undo_stack.undo()

        self.assertEqual(edge.waypoints, [])
        editor.close()

    def test_waypoint_insert_index_matches_nearest_segment(self):
        source = self.scene.add_node("source", QPointF(0, 0))
        target = self.scene.add_node("target", QPointF(300, 0))
        edge = self.scene.connect_nodes(source, target, "->")
        self.assertEqual(edge._waypoint_insert_index(QPointF(290, 0)), 0)

        edge.waypoints = [QPointF(200, 150)]
        edge.update_path()

        self.assertEqual(edge._waypoint_insert_index(QPointF(250, 100)), 1)
        self.assertEqual(edge._waypoint_insert_index(QPointF(100, 100)), 0)

    def test_swap_connector_orientation_reverses_route_and_dots(self):
        source = self.scene.add_node("source", QPointF(0, 0))
        target = self.scene.add_node("target", QPointF(300, 0))
        edge = self.scene.connect_nodes(
            source,
            target,
            "=>",
            gwf_type="pair/orient",
            gwf_tag="pair",
            target_anchor=QPointF(300, 0),
        )
        attribute = self.scene.connect_nodes(
            self.scene.add_node("attr", QPointF(100, 200)),
            edge,
            "->",
            target_anchor=edge.path().pointAtPercent(0.5),
        )
        edge.waypoints = [QPointF(100, 50), QPointF(200, 150)]
        edge.update_path()

        self.stack.push(CommandSwapConnectorOrientation(self.scene, edge))

        self.assertIs(edge.source, target)
        self.assertIs(edge.target, source)
        self.assertEqual(len(edge.waypoints), 2)
        self.assertAlmostEqual(edge.waypoints[1].x(), 100, delta=0.01)

        exported = ET.fromstring(self.scene.to_gwf())
        pair = next(
            pair
            for pair in exported.findall("staticSector/pair")
            if pair.get("id") == edge.gwf_id
        )
        self.assertEqual(pair.get("id_b"), target.gwf_id)
        self.assertEqual(pair.get("id_e"), source.gwf_id)

        self.stack.undo()

        self.assertIs(edge.source, source)
        self.assertEqual([point.x() for point in edge.waypoints], [100.0, 200.0])

    def test_swap_connector_rejects_arcs_and_unknown_edges(self):
        node = self.scene.add_node("node")
        removed = self.scene.add_node("gone")
        arc = self.scene.connect_nodes(node, removed, "->")
        removed.setSelected(True)
        self.scene.remove_selected()
        with self.assertRaises(ValueError):
            self.scene.swap_connector(arc)

    def test_arrange_grid_uses_sorted_layout_and_is_undoable(self):
        editor = GraphEditorWidget()
        node_c = editor.scene.add_node("node_c", QPointF(500, 900))
        node_a = editor.scene.add_node("node_a", QPointF(100, 100))
        node_b = editor.scene.add_node("node_b", QPointF(700, 400))
        grid_anchor = QPointF(min(node_a.pos().x(), node_b.pos().x(), node_c.pos().x()),
                              min(node_a.pos().y(), node_b.pos().y(), node_c.pos().y()))

        editor._arrange_grid()

        columns = math.ceil(math.sqrt(3))
        sorted_nodes = sorted(
            editor.scene.nodes.values(),
            key=lambda node: (node.pos().y(), node.pos().x()),
        )
        self.assertEqual(sorted_nodes[0].pos(), grid_anchor)
        self.assertEqual(
            sorted_nodes[0].identifier, "node_a"
        )
        self.assertEqual(
            editor.scene.nodes["node_b"].pos(),
            QPointF(grid_anchor.x() + 150, grid_anchor.y()),
        )
        self.assertEqual(
            editor.scene.nodes["node_c"].pos(),
            QPointF(grid_anchor.x(), grid_anchor.y() + 120),
        )
        self.assertTrue(editor.undo_stack.canUndo())

        editor.undo_stack.undo()

        self.assertEqual(node_a.pos().x(), 100)
        self.assertEqual(node_c.pos().y(), 900)
        editor.close()

    def test_arrange_vertical_and_horizontal_lines(self):
        editor = GraphEditorWidget()
        editor.scene.add_node("a", QPointF(700, 100))
        editor.scene.add_node("b", QPointF(100, 500))

        editor._arrange_vertical()

        positions = [node.pos() for node in editor.scene.nodes.values()]
        self.assertEqual(len({pos.x() for pos in positions}), 1)
        self.assertEqual(
            [node.pos().y() for node in editor.scene.nodes.values()],
            sorted(node.pos().y() for node in editor.scene.nodes.values()),
        )

        editor.undo_stack.undo()
        editor._arrange_horizontal()

        positions = [node.pos() for node in editor.scene.nodes.values()]
        self.assertEqual(len({pos.y() for pos in positions}), 1)
        editor.close()

    def test_arrange_tuple_spreads_neighbours_on_circle(self):
        editor = GraphEditorWidget()
        root = editor.scene.add_node("root", QPointF(400, 300))
        first = editor.scene.add_node("first", QPointF(100, 100))
        second = editor.scene.add_node("second", QPointF(600, 100))
        editor.scene.connect_nodes(root, first, "->")
        editor.scene.connect_nodes(root, second, "->")
        root.setSelected(True)

        editor._arrange_tuple()

        for neighbour in (first, second):
            delta = neighbour.scenePos() - root.scenePos()
            self.assertAlmostEqual(
                math.hypot(delta.x(), delta.y()), 170.0, delta=0.5
            )
        self.assertEqual(root.pos().x(), 400)
        self.assertTrue(editor.undo_stack.canUndo())

        editor.undo_stack.undo()

        self.assertEqual(first.pos(), QPointF(100, 100))
        editor.close()

    def test_widget_set_node_and_connector_types_route_through_stack(self):
        editor = GraphEditorWidget()
        source = editor.scene.add_node("source")
        target = editor.scene.add_node("target")
        edge = editor.scene.connect_nodes(source, target, "->")
        count = editor.undo_stack.count()

        editor._set_node_type(source, "node/var/atom")
        self.assertEqual(editor.undo_stack.count(), count + 1)
        self.assertEqual(source.gwf_type, "node/var/atom")

        editor._set_connector_type(edge, "pair/const/orient", "pair", "=>")
        self.assertEqual(editor.undo_stack.count(), count + 2)
        self.assertEqual(edge.gwf_tag, "pair")

        editor._swap_connector(edge)
        self.assertIs(edge.target, source)

        editor.undo_stack.undo()
        self.assertIs(edge.target, target)
        editor.close()

    def test_full_cycle_create_save_reload_round_trip(self):
        editor = GraphEditorWidget()
        source = editor.scene.add_node("source", QPointF(100, 100))
        target = editor.scene.add_node("target", QPointF(380, 140))
        middle = editor.scene.add_node("middle", QPointF(240, 60))
        first = editor.scene.connect_nodes(source, target, "->")
        editor.scene.connect_nodes(middle, target, "=>", gwf_type="pair/orient", gwf_tag="pair")
        first.waypoints = [QPointF(240, 150)]
        first.update_path()
        editor.scene.add_bus(source, QPointF(220, 260))
        editor.scene.add_contour(
            [QPointF(60, 40), QPointF(420, 40), QPointF(420, 300), QPointF(60, 300)]
        )
        with tempfile.TemporaryDirectory() as directory:
            graph_path = os.path.join(directory, "cycle.gwf")
            with patch(
                "src.gui.graph_editor.graph_editor.get_project_root",
                return_value=Path(directory),
            ), patch(
                "src.gui.graph_editor.graph_editor.QFileDialog.getSaveFileName",
                return_value=(graph_path, "GWF files (*.gwf)"),
            ):
                editor.save()
            self.assertTrue(os.path.isfile(graph_path))

            reloaded = GraphEditorWidget()
            with patch(
                "src.gui.graph_editor.graph_editor.get_project_root",
                return_value=Path(directory),
            ):
                reloaded.apply_file(graph_path)

            self.assertEqual(
                {node.identifier for node in reloaded.scene.nodes.values()},
                {"source", "target", "middle"},
            )
            self.assertEqual(len(reloaded.scene.edges), 2)
            route = reloaded.scene.edges[0].waypoints
            self.assertEqual(len(route), 1)
            self.assertAlmostEqual(route[0].x(), 240, delta=0.01)
            self.assertEqual([item.kind for item in reloaded.scene.aux_objects], ["bus", "contour"])
            self.assertFalse(reloaded.undo_stack.canUndo())
            self.assertFalse(reloaded.undo_stack.canRedo())
            editor.close()
            reloaded.close()

    def test_main_window_switches_to_graph_editor_for_gwf_files(self):
        try:
            from src.gui.main_window import MainWindow
        except ModuleNotFoundError as error:
            self.skipTest(f"main_window dependency missing: {error}")

        window = MainWindow.__new__(MainWindow)
        window.editor_selector = QComboBox()
        window.editor_selector.addItem("SCs text editor")
        window.editor_selector.addItem("SCg graph editor")
        window.editor_selector.setCurrentIndex(0)

        window._on_file_selected("/project/diagram.gwf")

        self.assertEqual(window.editor_selector.currentIndex(), 1)
        window._on_file_selected("/project/code.scs")
        self.assertEqual(window.editor_selector.currentIndex(), 1)


if __name__ == "__main__":
    unittest.main()
