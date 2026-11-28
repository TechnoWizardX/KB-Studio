import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from src.gui.editor_workspace import EditorWorkspace
from src.gui.status_bar import AppStatusBar
from src.utils.config_manager import ConfigManager

GWF_SAMPLE = (
    '<GWF version="2.0"><staticSector>'
    '<node type="node/const/general_node" idtf="loaded" id="n1" x="10" y="10"/>'
    "</staticSector></GWF>"
)


class AppStatusBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.bar = AppStatusBar()
        self.bar.resize(800, 24)

    def tearDown(self):
        self.bar.deleteLater()

    def test_document_kind_switches_the_visible_sections(self):
        self.bar.set_document("/tmp/main.scs", "scs")

        self.assertEqual(self.bar.path_label.full_text(), "/tmp/main.scs")
        self.assertEqual(self.bar.kind_label.text(), "SCS")
        self.assertFalse(self.bar.cursor_label.isHidden())
        self.assertTrue(self.bar.zoom_label.isHidden())
        self.assertFalse(self.bar.save_label.isHidden())

        self.bar.set_document("/tmp/diagram.gwf", "gwf")

        self.assertEqual(self.bar.kind_label.text(), "SCg")
        self.assertTrue(self.bar.cursor_label.isHidden())
        self.assertFalse(self.bar.zoom_label.isHidden())

        self.bar.set_document("", "")

        self.assertEqual(self.bar.path_label.full_text(), "No file open")
        self.assertTrue(self.bar.kind_label.isHidden())
        self.assertTrue(self.bar.save_label.isHidden())

    def test_values_are_rendered_in_their_sections(self):
        self.bar.set_cursor(12, 34)
        self.assertEqual(self.bar.cursor_label.text(), "Ln 12, Col 34")

        self.bar.set_save_state(True)
        self.assertEqual(self.bar.save_label.text(), "Unsaved")
        self.assertTrue(self.bar.save_label.property("modified"))

        self.bar.set_save_state(False)
        self.assertEqual(self.bar.save_label.text(), "Saved")
        self.assertFalse(self.bar.save_label.property("modified"))

        self.bar.set_problems(True)
        self.assertEqual(self.bar.problems_label.text(), "1 problem")
        self.assertFalse(self.bar.problems_label.isHidden())

        self.bar.set_problems(False)
        self.assertTrue(self.bar.problems_label.isHidden())

        self.bar.set_zoom(125)
        self.assertEqual(self.bar.zoom_label.text(), "125%")
        self.bar.set_zoom(0)
        self.assertEqual(self.bar.zoom_label.text(), "")

    def test_flash_uses_the_temporary_message_channel(self):
        self.bar.flash("Saved")
        self.assertEqual(self.bar.currentMessage(), "Saved")


class EditorWorkspaceStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "main.scs").write_text("// sample", encoding="utf-8")
        (self.root / "second.scs").write_text("// second", encoding="utf-8")
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
        self._set_patcher.start()
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

    def test_document_changes_follow_the_active_tab(self):
        self.workspace.apply_file(self.root / "main.scs")
        received = []
        self.workspace.document_changed.connect(
            lambda path, kind: received.append((path, kind))
        )

        self.workspace.apply_file(self.root / "diagram.gwf")

        self.assertEqual(received[-1][1], "gwf")
        self.assertEqual(Path(received[-1][0]).name, "diagram.gwf")

        self.workspace.tabs.setCurrentIndex(0)

        self.assertEqual(received[-1][1], "scs")
        self.assertEqual(Path(received[-1][0]).name, "main.scs")

    def test_cursor_moves_are_only_reported_for_the_active_editor(self):
        first = self.workspace.apply_file(self.root / "main.scs")
        second = self.workspace.apply_file(self.root / "second.scs")
        self.assertIs(self.workspace.tabs.currentWidget(), second)
        spy = QSignalSpy(self.workspace.cursor_moved)

        first.moveCursor(QTextCursor.MoveOperation.End)
        self.app.processEvents()
        self.assertEqual(spy.count(), 0)

        second.moveCursor(QTextCursor.MoveOperation.End)
        self.app.processEvents()
        self.assertGreaterEqual(spy.count(), 1)
        self.assertEqual(
            spy.at(spy.count() - 1), [1, len("// second") + 1]
        )

    def test_save_state_tracks_the_active_text_document(self):
        editor = self.workspace.apply_file(self.root / "main.scs")
        received = []
        self.workspace.save_state_changed.connect(received.append)

        editor.insertPlainText("x")
        self.app.processEvents()
        self.assertTrue(received[-1])

        editor.save_changes()
        self.app.processEvents()
        self.assertFalse(received[-1])

    def test_graph_zoom_is_reported(self):
        graph = self.workspace.apply_file(self.root / "diagram.gwf")
        received = []
        self.workspace.zoom_changed.connect(received.append)

        graph.view.zoom_in()
        self.app.processEvents()

        self.assertGreaterEqual(received[-1], 100)
        self.assertGreater(graph.zoom_percent(), 100)

    def test_clearing_the_workspace_resets_the_status(self):
        self.workspace.apply_file(self.root / "main.scs")
        received = []
        self.workspace.document_changed.connect(
            lambda path, kind: received.append((path, kind))
        )

        self.workspace.clear_workspace()

        self.assertEqual(received[-1], ("", ""))


if __name__ == "__main__":
    unittest.main()
