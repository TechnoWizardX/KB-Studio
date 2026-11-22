import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from src.gui.code_editor import CodeEditor
from src.gui.editor_workspace import EditorWorkspace
from src.gui.graph_editor import GraphEditorWidget
from src.utils.config_manager import ConfigManager

GWF_SAMPLE = (
    '<GWF version="2.0"><staticSector>'
    '<node type="node/const/general_node" idtf="loaded" id="n1" x="10" y="10"/>'
    "</staticSector></GWF>"
)


class EditorWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "main.scs").write_text("// sample", encoding="utf-8")
        (self.root / "diagram.gwf").write_text(GWF_SAMPLE, encoding="utf-8")
        self._previous_config = ConfigManager._current_config
        ConfigManager._current_config = ConfigManager.DEFAULT_CONFIG.copy()
        ConfigManager._current_config.update(
            {
                "project_dir": str(self.root),
                "selected_dir": "",
                "selected_file": "",
                "last_viewed_file": "",
                "last_viewed_files": [],
                "show_bottom_bar": True,
                "theme": "dark",
            }
        )
        self._set_patcher = patch.object(ConfigManager, "set")
        self._set_mock = self._set_patcher.start()
        self.workspace = EditorWorkspace()
        self.workspace.resize(900, 600)
        self.workspace.show()
        self.app.processEvents()

    def tearDown(self):
        self._set_patcher.stop()
        self.workspace.close()
        self.workspace.deleteLater()
        ConfigManager._current_config = self._previous_config
        self.temp_dir.cleanup()

    def _open_text(self):
        return self.workspace.apply_file(self.root / "main.scs")

    def _open_graph(self):
        return self.workspace.apply_file(self.root / "diagram.gwf")

    def test_text_and_graph_files_share_one_tab_bar(self):
        received_kinds = []
        self.workspace.kind_changed.connect(received_kinds.append)

        self._open_text()
        self._open_graph()

        self.assertEqual(self.workspace.tabs.count(), 2)
        self.assertIsInstance(self.workspace.tabs.widget(0), CodeEditor)
        self.assertIsInstance(self.workspace.tabs.widget(1), GraphEditorWidget)
        self.assertEqual(received_kinds, ["scs", "gwf"])
        self.assertEqual(self.workspace.current_kind(), "gwf")

    def test_reopening_a_file_activates_its_existing_tab(self):
        text_editor = self._open_text()
        self._open_graph()
        reopened = self._open_text()

        self.assertIs(reopened, text_editor)
        self.assertEqual(self.workspace.tabs.count(), 2)
        self.assertIs(self.workspace.tabs.currentWidget(), text_editor)

    def test_new_graph_opens_an_untitled_tab(self):
        editor = self.workspace.new_graph()

        self.assertIsInstance(editor, GraphEditorWidget)
        self.assertIsNone(editor.file_path)
        self.assertTrue(editor.modified_changed is not None)
        self.assertEqual(self.workspace.tabs.count(), 1)
        self.assertEqual(self.workspace.tabs.tabText(0), "Untitled graph *")
        self.assertEqual(self.workspace.current_kind(), "gwf")

    def test_new_graph_button_in_a_graph_tab_opens_another_tab(self):
        editor = self._open_graph()

        editor.new_graph_requested.emit()
        self.app.processEvents()

        self.assertEqual(self.workspace.tabs.count(), 2)
        self.assertIsInstance(self.workspace.tabs.currentWidget(), GraphEditorWidget)
        self.assertIsNot(self.workspace.tabs.currentWidget(), editor)

    def test_modified_graph_gets_an_asterisk_in_the_tab_title(self):
        editor = self._open_graph()

        editor._create_node_at(QPointF(40, 40))
        self.app.processEvents()

        self.assertTrue(self.workspace.tabs.tabText(0).endswith("*"))

    def test_activating_a_graph_fits_it_into_view(self):
        text_editor = self._open_text()
        graph_editor = self.workspace.apply_file(
            self.root / "diagram.gwf", activate=False
        )
        self.assertIs(self.workspace.tabs.currentWidget(), text_editor)

        self.workspace.tabs.setCurrentWidget(graph_editor)
        self.app.processEvents()
        self.app.processEvents()

        node = next(iter(graph_editor.scene.nodes.values()))
        view_position = graph_editor.view.mapFromScene(node.scenePos())
        self.assertTrue(graph_editor.view.viewport().rect().contains(view_position))

    def test_problems_panel_is_hidden_for_graph_tabs(self):
        self._open_text()
        self.app.processEvents()
        self.assertTrue(self.workspace.dev_panel_widget.isVisible())

        self._open_graph()
        self.app.processEvents()
        self.assertFalse(self.workspace.dev_panel_widget.isVisible())

        self.workspace.tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.assertTrue(self.workspace.dev_panel_widget.isVisible())

    def test_closing_a_graph_tab_asks_the_editor_first(self):
        editor = self._open_graph()

        with patch.object(
            GraphEditorWidget, "confirm_close", return_value=False
        ) as confirm:
            self.assertFalse(self.workspace.close_tab(0))

        confirm.assert_called_once_with()
        self.assertEqual(self.workspace.tabs.count(), 1)

        with patch.object(GraphEditorWidget, "confirm_close", return_value=True):
            self.assertTrue(self.workspace.close_tab(0))

        self.assertEqual(self.workspace.tabs.count(), 0)
        self.assertEqual(self.workspace.current_kind(), "")
        self.assertIsNotNone(editor)

    def test_restores_mixed_tabs_and_the_last_active_file(self):
        self.workspace.clear_workspace()
        self.workspace.deleteLater()

        ConfigManager._current_config["last_viewed_files"] = [
            str(self.root / "main.scs"),
            str(self.root / "diagram.gwf"),
        ]
        ConfigManager._current_config["last_viewed_file"] = str(
            self.root / "diagram.gwf"
        )
        self.workspace = EditorWorkspace()
        self.app.processEvents()

        self.assertEqual(self.workspace.tabs.count(), 2)
        self.assertIsInstance(self.workspace.tabs.widget(0), CodeEditor)
        self.assertIsInstance(self.workspace.tabs.widget(1), GraphEditorWidget)
        self.assertEqual(self.workspace.current_kind(), "gwf")
        self.assertTrue(self.workspace.dev_panel_widget.isHidden())
