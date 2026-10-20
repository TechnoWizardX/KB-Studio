import math
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QUndoStack
from PySide6.QtGui import QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox

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
    CommandSwapConnectorOrientation,
    CommandWaypointsChange,
)
from src.gui.graph_editor.graph_editor import (
    _CONNECTOR_TYPES,
    _EDGE_TYPES,
    _relation_for_gwf,
    GraphEditorWidget,
    GraphScene,
)
from src.lark_syntax.parser import SCSParser


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
        QTest.mousePress(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(editor.view.viewport(), finish, 100)
        QTest.mouseRelease(
            editor.view.viewport(), Qt.MouseButton.LeftButton, pos=finish
        )
        self.app.processEvents()
        self.assertEqual(len(editor.scene.edges), 1)

        edge_middle = editor.scene.edges[0].path().pointAtPercent(0.5)
        edge_position = editor.view.mapFromScene(edge_middle)
        QTest.mousePress(editor.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(editor.view.viewport(), edge_position, 100)
        QTest.mouseRelease(
            editor.view.viewport(), Qt.MouseButton.LeftButton, pos=edge_position
        )
        self.app.processEvents()

        self.assertEqual(len(editor.scene.edges), 2)
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

        self.assertAlmostEqual(path_start.x(), 112, delta=1)
        self.assertAlmostEqual(path_end.x(), 288, delta=1)
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
        self.assertTrue(node.shape().contains(QPointF(0, 0)))
        self.assertFalse(node.shape().contains(QPointF(4, 4)))

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
