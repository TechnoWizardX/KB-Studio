import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from src.core.signals import signals
from src.gui.code_editor import CodeEditor
from src.gui.editor_workspace import EditorWorkspace
from src.gui.empty_editor_state import EmptyEditorState
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

    def test_empty_state_stays_until_the_first_file_opens(self):
        self.assertIsInstance(self.workspace.empty_state, EmptyEditorState)
        self.assertIs(
            self.workspace.editor_area.currentWidget(),
            self.workspace.empty_state,
        )

        self._open_text()

        self.assertIs(
            self.workspace.editor_area.currentWidget(), self.workspace.tabs
        )

    def test_closing_the_last_tab_brings_the_empty_state_back(self):
        received_kinds = []
        self.workspace.kind_changed.connect(received_kinds.append)
        self._open_text()

        self.assertTrue(self.workspace.close_tab(0))

        self.assertEqual(self.workspace.tabs.count(), 0)
        self.assertIs(
            self.workspace.editor_area.currentWidget(),
            self.workspace.empty_state,
        )
        self.assertEqual(received_kinds, ["scs", ""])

    def test_empty_state_new_graph_button_opens_a_graph_tab(self):
        self.workspace.empty_state.new_graph_button.click()
        self.app.processEvents()

        self.assertEqual(self.workspace.tabs.count(), 1)
        self.assertIsInstance(
            self.workspace.tabs.currentWidget(), GraphEditorWidget
        )
        self.assertIs(
            self.workspace.editor_area.currentWidget(), self.workspace.tabs
        )

    def test_empty_state_delegates_new_file_and_folder_requests(self):
        file_requests = QSignalSpy(signals.create_file_act)
        folder_requests = QSignalSpy(signals.select_project_requested)

        self.workspace.empty_state.new_file_button.click()
        self.workspace.empty_state.open_project_button.click()
        self.app.processEvents()

        self.assertEqual(file_requests.count(), 1)
        self.assertEqual(folder_requests.count(), 1)

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

    def test_graph_autosave_writes_pending_edits_after_a_short_delay(self):
        editor = self._open_graph()

        editor._create_node_at(QPointF(60, 60))

        self.assertTrue(editor.save_timer.isActive())
        QTest.qWait(700)

        content = (self.root / "diagram.gwf").read_text(encoding="utf-8")
        self.assertIn("node_1", content)
        self.assertFalse(editor.is_modified)
        self.assertFalse(editor.save_timer.isActive())

    def test_loading_a_graph_does_not_autosave_it(self):
        editor = self._open_graph()

        self.assertFalse(editor.is_modified)
        self.assertFalse(editor.save_timer.isActive())

    def test_untitled_graph_is_never_autosaved(self):
        editor = self.workspace.new_graph()

        editor._create_node_at(QPointF(60, 60))
        QTest.qWait(700)

        self.assertTrue(editor.is_modified)
        self.assertEqual(
            sorted(entry.name for entry in self.root.iterdir()),
            ["diagram.gwf", "main.scs"],
        )

    def test_text_and_graph_share_the_auto_save_setting(self):
        text_editor = self._open_text()
        graph_editor = self._open_graph()

        ConfigManager._current_config["auto_save"] = False
        text_editor.insertPlainText("extra text")
        graph_editor._create_node_at(QPointF(60, 60))

        self.assertFalse(text_editor.save_timer.isActive())
        self.assertFalse(graph_editor.save_timer.isActive())

        ConfigManager._current_config["auto_save"] = True
        text_editor.insertPlainText(" more")
        graph_editor.on_auto_save_changed(True)

        self.assertTrue(text_editor.save_timer.isActive())
        self.assertTrue(graph_editor.save_timer.isActive())

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
