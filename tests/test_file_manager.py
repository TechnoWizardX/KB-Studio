import tempfile
import unittest
from pathlib import Path

from src.utils.file_manager import get_context_file_content


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


if __name__ == "__main__":
    unittest.main()
