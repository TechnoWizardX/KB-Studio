import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from src.utils.search.file_index import FileIndex
from src.utils.search.fuzzy import fuzzy_match
from src.gui.search.providers import FileSearchProvider, SearchContext, SearchResult, text_results
from src.gui.search.quick_search import QuickSearchController
from src.gui.search.quick_search import QuickSearchController
from src.gui.search.query import parse_query
from src.utils.search.text_search import (
    MAX_RESULTS,
    TextMatch,
    compile_query,
    make_snippet,
)


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fuzzy_match_finds_file_initialisms_and_highlights_positions(self):
        match = fuzzy_match("mw", "src/gui/main_window.py")

        self.assertIsNotNone(match)
        self.assertEqual(match.positions, (8, 13))

    def test_file_index_skips_common_generated_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "ignored.py").write_text("ignored", encoding="utf-8")

            index = FileIndex()
            index.refresh(root)

            self.assertEqual([item.rel for item in index.files], ["src/main.py"])

    def test_file_provider_ranks_by_name_and_returns_compact_result_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "main_window.py"
            path.write_text("pass", encoding="utf-8")

            index = FileIndex()
            index.refresh(root)
            results = FileSearchProvider(index).search("mw", SearchContext(project_root=root))

            self.assertEqual(results[0].title, "main_window.py")
            self.assertEqual(results[0].payload, ("file", path.resolve()))

    def test_snippet_contains_relative_highlight_for_long_lines(self):
        line = "x" * 80 + "needle" + "y" * 80
        snippet, span = make_snippet(line, 81, 6, width=40)

        self.assertIn("needle", snippet)
        self.assertIsNotNone(span)

    def test_mode_selection_inserts_prefix_not_menu_payload(self):
        window = QWidget()
        field = QLineEdit(window)
        workspace = QWidget()
        controller = QuickSearchController(window, field, workspace)

        result = SearchResult(title="Text in project files", payload="%", kind="mode")
        controller._activate(result)

        self.assertEqual(field.text(), "%")
        window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_empty_placeholder_uses_project_folder_and_workspace_label(self):
        root = Path("/tmp/MyProject")

        self.assertEqual(
            QuickSearchController._workspace_placeholder(root),
            "MyProject (Workspace)",
        )

    def test_text_query_prefix_is_context_sensitive(self):
        self.assertEqual(parse_query("%needle").mode, "text")
        self.assertEqual(parse_query("%needle", active_kind="gwf").mode, "graph")

    def test_text_results_group_matches_by_relative_file_path(self):
        path = Path("/tmp/example.py")
        matches = [
            TextMatch(path=path, rel="example.py", line=3, column=5, length=6, line_text="a needle here")
        ]

        results = text_results(matches, "needle")

        self.assertEqual(results[0].kind, "header")
        self.assertEqual(results[0].title, "example.py")
        self.assertEqual(results[1].kind, "text")

    def test_text_results_show_more_indicator_at_limit(self):
        matches = [
            TextMatch(
                path=Path(f"/tmp/file_{number}.py"),
                rel=f"file_{number}.py",
                line=1,
                column=1,
                length=6,
                line_text="needle",
            )
            for number in range(MAX_RESULTS + 1)
        ]

        results = text_results(matches, "needle", limit=MAX_RESULTS)

        self.assertTrue(any(result.kind == "info" and "more matches" in result.title for result in results))

    def test_regex_compile_supports_case_sensitive_and_whole_word(self):
        pattern = compile_query("needle", case_sensitive=True, whole_word=True)

        self.assertIsNotNone(pattern.search(" needle "))
        self.assertIsNone(pattern.search("needlework"))


if __name__ == "__main__":
    unittest.main()
