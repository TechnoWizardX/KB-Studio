import tempfile
import unittest
from pathlib import Path

from src.core.signals import signals
from src.utils.config_manager import ConfigManager
from src.utils.file_manager import (
    FileOperationError,
    bind_file_signals,
    create_directory,
    create_file,
    delete_path,
    get_context_file_content,
    rename_path,
)


class ContextFileContentTests(unittest.TestCase):
    def test_reads_explicit_file_outside_project_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            selected_file = Path(temporary_directory) / "README.md"
            selected_file.write_text("selected context", encoding="utf-8")

            self.assertEqual(
                get_context_file_content(str(selected_file)),
                "selected context",
            )

    def test_rejects_relative_paths(self):
        with self.assertRaises(ValueError):
            get_context_file_content("README.md")

    def test_rejects_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                get_context_file_content(temporary_directory)


class FileManagerOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.previous_config = ConfigManager._current_config
        ConfigManager._current_config = {
            "project_dir": str(self.root),
            "selected_dir": str(self.root),
        }

    def tearDown(self):
        ConfigManager._current_config = self.previous_config
        self.temp_dir.cleanup()

    def test_create_file_directory_delete_and_rename(self):
        created_file = create_file("sample.scs")
        created_directory = create_directory("folder")
        renamed = rename_path(created_file, "renamed.scs")

        self.assertTrue(created_directory.is_dir())
        self.assertTrue(renamed.is_file())
        delete_path(renamed)
        self.assertFalse(renamed.exists())

    def test_invalid_and_duplicate_names_raise(self):
        create_file("sample.scs")

        with self.assertRaises(FileOperationError):
            create_file("sample.scs")
        with self.assertRaises(FileOperationError):
            create_directory("../folder")

    def test_existing_signals_create_files_directly(self):
        status_messages = []
        changed = []
        status_slot = status_messages.append
        changed_slot = lambda: changed.append(True)

        signals.status_message.connect(status_slot)
        signals.project_files_changed.connect(changed_slot)
        bind_file_signals(signals)
        try:
            signals.execute_create_file.emit("from_signal.scs")
            signals.execute_create_dir.emit("from_signal_folder")
        finally:
            signals.status_message.disconnect(status_slot)
            signals.project_files_changed.disconnect(changed_slot)

        self.assertTrue((self.root / "from_signal.scs").is_file())
        self.assertTrue((self.root / "from_signal_folder").is_dir())
        self.assertGreaterEqual(len(status_messages), 2)
        self.assertGreaterEqual(len(changed), 2)


if __name__ == "__main__":
    unittest.main()
