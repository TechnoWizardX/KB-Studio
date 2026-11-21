import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.gui.left_sidebar.directory_view import DirectoryTreeViewWidget
from src.utils.config_manager import ConfigManager


class DirectoryViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "src").mkdir()
        (self.root / "README.scs").write_text("// sample", encoding="utf-8")
        self._previous_config = ConfigManager._current_config
        ConfigManager._current_config = {
            "project_dir": str(self.root),
            "selected_dir": "",
            "selected_file": "",
            "last_viewed_file": "",
        }
        self._set_patcher = patch.object(ConfigManager, "set")
        self._set_patcher.start()
        self.widget = DirectoryTreeViewWidget(root_path=str(self.root))
        self.widget.resize(320, 480)
        self.widget.show()
        self.app.processEvents()

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()
        self._set_patcher.stop()
        ConfigManager._current_config = self._previous_config
        self.temp_dir.cleanup()

    def _select_source_dir(self):
        index = self.widget.dir_view.tree_model.index(str(self.root / "src"))
        self.widget.dir_view.setCurrentIndex(index)
        self.widget.dir_view.clicked.emit(index)
        self.app.processEvents()
        return index

    def test_tree_header_is_hidden_and_buttons_explain_themselves(self):
        self.assertTrue(self.widget.dir_view.isHeaderHidden())
        self.assertEqual(self.widget.mk_file_btn.toolTip(), "New file")
        self.assertEqual(self.widget.mk_dir_btn.toolTip(), "New folder")
        self.assertEqual(
            self.widget.select_project_dir_btn.toolTip(), "Select project folder"
        )

    def test_inline_editor_is_placed_under_the_selected_folder(self):
        source_index = self._select_source_dir()

        self.widget.make_new_file()
        self.app.processEvents()

        editor = self.widget.name_edit
        row = self.widget.dir_view.visualRect(source_index)
        self.assertTrue(editor.isVisible())
        self.assertGreaterEqual(editor.y(), row.bottom())
        self.assertEqual(editor.x(), 0)
        self.assertEqual(
            editor.width(), self.widget.dir_view.viewport().width()
        )
        self.assertEqual(self.widget._creation_base_path, self.root / "src")

    def test_enter_creates_the_file_in_the_selected_folder(self):
        self._select_source_dir()
        self.widget.make_new_file()
        self.widget.name_edit.setText("new_module.scs")

        self.widget.name_edit.returnPressed.emit()
        self.app.processEvents()

        self.assertTrue((self.root / "src" / "new_module.scs").exists())
        self.assertFalse(self.widget.name_edit_status)

    def test_escape_cancels_creation_without_touching_the_filesystem(self):
        self._select_source_dir()
        self.widget.make_new_dir()

        QTest.keyClick(self.widget.name_edit, Qt.Key.Key_Escape)
        self.app.processEvents()

        self.assertFalse(self.widget.name_edit_status)
        self.assertTrue(self.widget.name_edit.isHidden())
        self.assertFalse(any((self.root / "src").iterdir()))
