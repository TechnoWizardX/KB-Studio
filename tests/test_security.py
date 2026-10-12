import tempfile
import unittest
from pathlib import Path

from src.utils.security import PathTraversalError, safe_join, safe_path, validate_filename


class SafePathTests(unittest.TestCase):
    def test_relative_path_is_resolved_from_base(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)

            self.assertEqual(safe_path(base, "new_file.scs"), base / "new_file.scs")

    def test_absolute_path_inside_base_is_allowed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            target = base / "nested" / "file.scs"

            self.assertEqual(safe_path(base, str(target)), target)

    def test_absolute_path_outside_base_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory) / "project"
            base.mkdir()
            outside = Path(temporary_directory) / "outside.scs"

            with self.assertRaises(PathTraversalError):
                safe_path(base, str(outside))

    def test_relative_traversal_outside_base_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory) / "project"
            base.mkdir()

            with self.assertRaises(PathTraversalError):
                safe_path(base, "../outside.scs")

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            base = root / "project"
            outside = root / "outside"
            base.mkdir()
            outside.mkdir()
            link = base / "linked"

            try:
                link.symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError):
                self.skipTest("Symlinks are not available")

            with self.assertRaises(PathTraversalError):
                safe_path(base, "linked/new_file.scs")

    def test_safe_join_uses_base_for_relative_parts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)

            self.assertEqual(
                safe_join(base, "nested", "file.scs"),
                base / "nested" / "file.scs",
            )


class FilenameValidationTests(unittest.TestCase):
    def test_allows_regular_filename_with_multiple_dots(self):
        self.assertTrue(validate_filename("model.v1..backup.scs"))

    def test_rejects_path_components_and_invalid_names(self):
        for name in ("", ".", "..", "../file.scs", "folder\\file.scs", "bad:name"):
            with self.subTest(name=name):
                self.assertFalse(validate_filename(name))


if __name__ == "__main__":
    unittest.main()
