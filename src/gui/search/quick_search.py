"""The toolbar search field and its result popup.

The field is intentionally thin: it forwards text to
:class:`QuickSearchController`, which parses the prefix, asks the matching
provider for ordered results and renders them in an overlay list below the
field. The overlay is a child of the main window (not a separate window), so
typing focus never leaves the field.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from src.core.signals import signals
from src.utils.search.file_index import FileIndex
from src.gui.search.graph_search import (
    available_filters,
    resolve_node_filter,
    search_nodes,
)
from src.gui.search.options import OPTIONS_BY_PREFIX, SEARCH_OPTIONS
from src.gui.search.providers import (
    CommandsProvider,
    FileSearchProvider,
    SearchCommand,
    SearchContext,
    SearchResult,
    SymbolsProvider,
    header,
    info,
    text_results,
)
from src.gui.search.query import (
    MODE_COMMANDS,
    MODE_FILES,
    MODE_GRAPH,
    MODE_NODE_CLASS,
    MODE_SYMBOLS,
    MODE_TEXT,
    PREFIX_COMMANDS,
    parse_query,
)
from src.gui.search.text_search import TextSearchController
from src.utils.search.text_search import text_files
from src.utils.config_manager import ConfigManager
from src.utils.security import get_project_root

RESULT_ROLE = Qt.ItemDataRole.UserRole + 1
HEADER_HEIGHT = 22
ROW_HEIGHT = 38
POPUP_MAX_HEIGHT = 360
POPUP_MIN_WIDTH = 620


class SearchItemDelegate(QStyledItemDelegate):
    """Paint a two-line result row with fuzzy-match highlighting."""

    def sizeHint(self, option, index) -> QSize:
        result = index.data(RESULT_ROLE)
        height = HEADER_HEIGHT if result and result.kind == "header" else ROW_HEIGHT
        return QSize(0, height)

    def paint(self, painter, option, index) -> None:
        result = index.data(RESULT_ROLE)
        if not isinstance(result, SearchResult):
            super().paint(painter, option, index)
            return

        painter.save()
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette

        if selected and result.selectable:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
            painter.drawRoundedRect(rect.adjusted(4, 1, -4, -1), 4, 4)

        if result.kind == "header":
            font = QFont(painter.font())
            font.setBold(True)
            font.setPointSizeF(max(7.5, font.pointSizeF() - 1.0))
            painter.setFont(font)
            painter.setPen(palette.color(QPalette.ColorRole.PlaceholderText))
            painter.drawText(
                rect.adjusted(12, 0, -8, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                result.title.upper(),
            )
            painter.restore()
            return

        base_color = (
            palette.color(QPalette.ColorRole.HighlightedText)
            if selected
            else palette.color(QPalette.ColorRole.Text)
        )
        muted_color = (
            palette.color(QPalette.ColorRole.HighlightedText)
            if selected
            else palette.color(QPalette.ColorRole.PlaceholderText)
        )
        accent_color = palette.color(QPalette.ColorRole.Link)

        icon = result.icon or self._icon_for(result.kind)
        icon_rect = rect.adjusted(10, 0, 0, 0)
        icon_rect.setWidth(16)
        icon_rect.setHeight(16)
        icon_rect.moveTop(rect.top() + (rect.height() - 16) // 2)
        if icon is not None and not icon.isNull():
            icon.paint(painter, icon_rect)

        text_left = rect.left() + 36
        text_right = rect.right() - 10
        painter.setClipRect(rect.adjusted(0, 0, -2, 0))

        title_font = QFont(painter.font())
        title_font.setBold(True)
        painter.setFont(title_font)
        title_y = rect.top() + 15
        self._draw_spans(
            painter,
            text_left,
            title_y,
            result.title,
            result.title_spans,
            base_color,
            accent_color,
            text_right,
        )

        second = result.detail or result.subtitle
        if second:
            detail_font = QFont(painter.font())
            detail_font.setBold(False)
            detail_font.setPointSizeF(max(7.5, detail_font.pointSizeF() - 0.5))
            painter.setFont(detail_font)
            spans: tuple[int, ...] = ()
            if result.detail and result.detail_spans is not None:
                start, length = result.detail_spans
                spans = tuple(range(start, start + length))
            metrics = painter.fontMetrics()
            text = metrics.elidedText(
                second,
                Qt.TextElideMode.ElideRight,
                max(0, text_right - text_left),
            )
            self._draw_spans(
                painter,
                text_left,
                rect.top() + 29,
                text,
                spans,
                muted_color,
                accent_color,
                text_right,
            )

        painter.restore()

    @staticmethod
    def _icon_for(kind: str) -> QIcon | None:
        try:
            from src.resources.icons import Icons

            if kind in {"text", "file"}:
                return Icons.find()
            if kind in {"node", "symbol"}:
                return Icons.new_graph()
            if kind == "command":
                return Icons.settings()
            if kind == "filter":
                return Icons.find()
        except Exception:  # pragma: no cover - icons are optional
            return None
        return None

    @staticmethod
    def _draw_spans(
        painter,
        x: float,
        baseline: float,
        text: str,
        spans: tuple[int, ...],
        base_color: QColor,
        accent_color: QColor,
        right_limit: float,
    ) -> None:
        if not spans:
            painter.setPen(base_color)
            painter.drawText(QPoint(int(x), int(baseline)), text)
            return

        highlighted = set(spans)
        metrics = painter.fontMetrics()
        run = ""
        run_is_accent = False
        cursor_x = x
        for index, char in enumerate(text):
            is_accent = index in highlighted
            if run and is_accent != run_is_accent:
                painter.setPen(accent_color if run_is_accent else base_color)
                painter.drawText(QPoint(int(cursor_x), int(baseline)), run)
                cursor_x += metrics.horizontalAdvance(run)
                run = ""
            run += char
            run_is_accent = is_accent
            if cursor_x >= right_limit:
                break
        if run:
            painter.setPen(accent_color if run_is_accent else base_color)
            painter.drawText(QPoint(int(cursor_x), int(baseline)), run)


class SearchPopup(QFrame):
    """Overlay list shown below the search field."""

    activated = Signal(object)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("searchPopup")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.list = QListWidget(self)
        self.list.setObjectName("searchPopupList")
        self.list.setItemDelegate(SearchItemDelegate(self.list))
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list.itemClicked.connect(self._on_item_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        layout.addWidget(self.list)
        self.hide()

    @property
    def results(self) -> list[SearchResult]:
        return list(self._results)

    def set_results(self, results: list[SearchResult]) -> None:
        self._results = list(results)
        self.list.clear()
        for result in self._results:
            item = QListWidgetItem()
            item.setData(RESULT_ROLE, result)
            flags = Qt.ItemFlag.ItemIsEnabled
            if result.selectable:
                flags |= Qt.ItemFlag.ItemIsSelectable
            item.setFlags(flags)
            self.list.addItem(item)

        first = self._first_selectable_row()
        if first >= 0:
            self.list.setCurrentRow(first)

        content_height = sum(
            HEADER_HEIGHT if result.kind == "header" else ROW_HEIGHT
            for result in self._results
        )
        height = min(POPUP_MAX_HEIGHT, max(64, content_height + 8))
        self.list.setFixedHeight(height)
        self.setFixedHeight(height + 8)

    def show_at(self, anchor: QWidget) -> None:
        if not self._results:
            return
        parent = self.parentWidget()
        if parent is None:
            return
        width = min(
            max(anchor.width(), POPUP_MIN_WIDTH),
            max(320, parent.width() - 24),
        )
        anchor_top = anchor.mapTo(parent, QPoint(0, 0))
        anchor_bottom = anchor.mapTo(
            parent, QPoint(0, anchor.height() + 6)
        )
        x = anchor_top.x() + (anchor.width() - width) // 2
        x = max(8, min(x, parent.width() - width - 8))
        y = anchor_bottom.y()
        if y + self.height() > parent.height() - 8:
            y = max(8, anchor_top.y() - self.height() - 6)
        self.setGeometry(x, y, width, self.height())
        self.show()
        self.raise_()

    def move_selection(self, delta: int) -> None:
        if self.list.count() == 0:
            return
        current = self.list.currentRow()
        if current < 0:
            current = 0 if delta > 0 else self.list.count() - 1
        row = current
        for _ in range(self.list.count()):
            row = (row + delta) % self.list.count()
            item = self.list.item(row)
            result = item.data(RESULT_ROLE)
            if result is not None and result.selectable:
                self.list.setCurrentRow(row)
                self.list.scrollToItem(item)
                return

    def current_result(self) -> SearchResult | None:
        item = self.list.currentItem()
        if item is None:
            return None
        result = item.data(RESULT_ROLE)
        return result if isinstance(result, SearchResult) else None

    def activate_current(self) -> None:
        result = self.current_result()
        if result is not None and result.selectable:
            self.activated.emit(result)

    def _first_selectable_row(self) -> int:
        for row in range(self.list.count()):
            result = self.list.item(row).data(RESULT_ROLE)
            if result is not None and result.selectable:
                return row
        return -1

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        result = item.data(RESULT_ROLE)
        if result is not None and result.selectable:
            self.activated.emit(result)


class QuickSearchController(QObject):
    """Owns the search field state, providers and result activation."""

    def __init__(
        self,
        window: QWidget,
        field: QLineEdit,
        workspace: QWidget,
        *,
        commands: list[SearchCommand] | None = None,
        index: FileIndex | None = None,
        pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.field = field
        self.workspace = workspace
        self.index = index if index is not None else FileIndex()
        self.popup = SearchPopup(window)
        self._results: list[SearchResult] = []
        self._text_query = ""
        self._active_kind = ""

        self.file_provider = FileSearchProvider(self.index)
        self.symbols_provider = SymbolsProvider()
        self.commands_provider = CommandsProvider(commands or [])
        self.text_search = TextSearchController(pool, self)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._run_text_search)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(300)
        self._refresh_timer.timeout.connect(self.refresh_index)

        self.field.installEventFilter(self)
        self.field.textEdited.connect(self._on_text_edited)
        self.popup.activated.connect(self._activate)
        self.text_search.results_ready.connect(self._on_text_results)
        self.text_search.failed.connect(self._on_text_failed)

        if hasattr(workspace, "kind_changed"):
            workspace.kind_changed.connect(self._on_kind_changed)
        signals.selected_new_project_folder.connect(self._on_project_changed)
        signals.project_files_changed.connect(self._schedule_index_refresh)

        self._active_kind = self._kind()
        self._update_placeholder()
        self.refresh_index()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def focus_files(self) -> None:
        self.field.setFocus()
        self.field.selectAll()
        self._search()

    def focus_text(self) -> None:
        self._set_mode("%")

    def focus_commands(self) -> None:
        self._set_mode(PREFIX_COMMANDS)

    def refresh_index(self) -> None:
        try:
            root = get_project_root()
        except ValueError:
            root = None
        if root is not None and root.is_dir():
            self.index.refresh(root)
        else:
            self.index.clear()
        self._update_placeholder()
        if self.popup.isVisible():
            self._search()

    def dismiss(self, *, clear: bool = False) -> None:
        self._debounce.stop()
        self.text_search.cancel()
        self.popup.hide()
        if clear:
            self.field.clear()
        self.field.clearFocus()
        self._focus_editor()

    # ------------------------------------------------------------------
    # Field events
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:
        if obj is not self.field:
            return super().eventFilter(obj, event)

        event_type = event.type()
        if event_type == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self.popup.move_selection(1)
                return True
            if key == Qt.Key.Key_Up:
                self.popup.move_selection(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.popup.activate_current()
                return True
            if key == Qt.Key.Key_Escape:
                self.dismiss(clear=True)
                return True
        elif event_type == QEvent.Type.FocusIn:
            self._search()
        elif event_type == QEvent.Type.FocusOut:
            QTimer.singleShot(120, self._hide_if_unfocused)
        return super().eventFilter(obj, event)

    def _hide_if_unfocused(self) -> None:
        if not self.field.hasFocus() and not self.popup.underMouse():
            self.popup.hide()

    def _on_text_edited(self, _text: str) -> None:
        self._search()

    def _on_kind_changed(self, kind: str) -> None:
        if kind == self._active_kind:
            return
        self._active_kind = kind
        self._update_placeholder()
        if self.field.hasFocus() or self.popup.isVisible():
            self._search()

    def _on_project_changed(self, _path: str = "") -> None:
        self.refresh_index()
        if self.field.text():
            self._search()

    def _schedule_index_refresh(self) -> None:
        self._refresh_timer.start()

    # ------------------------------------------------------------------
    # Search dispatch
    # ------------------------------------------------------------------
    def _search(self) -> None:
        raw = self.field.text()
        parsed = parse_query(raw, self._kind())
        self._update_placeholder(parsed)

        if not parsed.has_prefix and not parsed.text:
            self._show_suggestions()
            return

        if parsed.is_mode_only:
            self._show_mode_only(parsed.mode)
            return

        if parsed.mode == MODE_TEXT:
            self._show_results([info("Searching…", parsed.text)])
            self._text_query = parsed.text
            self._debounce.start()
            return

        self._debounce.stop()
        self.text_search.cancel()
        self._show_results(self._sync_results(parsed))

    def _sync_results(self, parsed) -> list[SearchResult]:
        context = self._context()
        if parsed.mode == MODE_FILES:
            results = self.file_provider.search(parsed.text, context)
            if not results:
                results = [
                    info(
                        f"No files match '{parsed.text}'",
                        "Try a shorter query or check the project folder.",
                    )
                ]
            return results
        if parsed.mode == MODE_GRAPH:
            return self._graph_results(parsed.text, context)
        if parsed.mode == MODE_NODE_CLASS:
            return self._node_class_results(parsed.text, context)
        if parsed.mode == MODE_SYMBOLS:
            results = self.symbols_provider.search(parsed.text, context)
            if not results:
                results = [info("No symbols found", parsed.text)]
            return results
        if parsed.mode == MODE_COMMANDS:
            return self.commands_provider.search(parsed.text, context)
        return []

    def _show_suggestions(self) -> None:
        self._debounce.stop()
        self.text_search.cancel()
        context = self._context()
        results = self.file_provider.search("", context)
        modes = self._mode_results(context)
        if modes:
            results.append(header("Search modes"))
            results.extend(modes)
        if not results:
            results = [
                info(
                    "No project files",
                    "Open a project folder to search files by name.",
                )
            ]
        self._show_results(results)

    def _show_mode_only(self, mode: str) -> None:
        self._debounce.stop()
        self.text_search.cancel()
        context = self._context()

        if mode == MODE_NODE_CLASS:
            results = [
                SearchResult(
                    title=f"#{key}",
                    subtitle=label,
                    detail=hint,
                    payload=f"#{key}",
                    kind="filter",
                    group="Node classes",
                )
                for key, label, hint in available_filters()
            ]
            self._show_results(results)
            return

        if mode == MODE_COMMANDS:
            self._show_results(self.commands_provider.search("", context))
            return

        if mode == MODE_SYMBOLS:
            self._show_results(self.symbols_provider.search("", context))
            return

        if mode == MODE_GRAPH:
            self._show_results(
                [
                    info(
                        "Search nodes in this graph",
                        "Type a node name, label or content fragment.",
                    )
                ]
            )
            return

        self._show_results(
            [
                info(
                    "Search text in project files",
                    "Type a word or phrase to scan every text file.",
                )
            ]
        )

    def _mode_results(self, context: SearchContext) -> list[SearchResult]:
        results: list[SearchResult] = []
        for option in SEARCH_OPTIONS:
            if not option.enabled(context):
                continue
            results.append(
                SearchResult(
                    title=option.title_for(context),
                    subtitle=option.hint_for(context),
                    payload=option.prefix,
                    kind="mode",
                    group="Search modes",
                )
            )
        return results

    def _graph_results(
        self, text: str, context: SearchContext
    ) -> list[SearchResult]:
        editor = context.active_widget
        if editor is None or not hasattr(editor, "scene"):
            return [
                info(
                    "No SCg graph is active",
                    "Open a .gwf tab to search graph nodes.",
                )
            ]
        nodes = search_nodes(editor.scene.nodes.values(), text)
        if not nodes:
            return [info(f"No nodes match '{text}'", "")]
        results: list[SearchResult] = []
        for node in nodes[:100]:
            content = node._content_viewer_text()
            results.append(
                SearchResult(
                    title=node.identifier,
                    subtitle=node.gwf_type,
                    detail=content.replace("\n", " ")[:120],
                    payload=("node", editor, node),
                    kind="node",
                    group="Nodes in graph",
                )
            )
        return results

    def _node_class_results(
        self, text: str, context: SearchContext
    ) -> list[SearchResult]:
        editor = context.active_widget
        if editor is None or not hasattr(editor, "scene"):
            return [
                info(
                    "No SCg graph is active",
                    "Open a .gwf tab to filter nodes by class.",
                )
            ]

        node_filter = resolve_node_filter(text)
        if node_filter is None:
            return self._show_filter_list()
        nodes = search_nodes(
            editor.scene.nodes.values(),
            node_filter.query,
            predicate=node_filter.predicate,
        )
        if not nodes:
            return [
                info(
                    f"No {node_filter.label.lower()} found",
                    node_filter.query,
                )
            ]
        results: list[SearchResult] = []
        for node in nodes[:100]:
            content = node._content_viewer_text()
            results.append(
                SearchResult(
                    title=node.identifier,
                    subtitle=node.gwf_type,
                    detail=content.replace("\n", " ")[:120],
                    payload=("node", editor, node),
                    kind="node",
                    group=node_filter.label,
                )
            )
        return results

    def _show_filter_list(self) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"#{key}",
                subtitle=label,
                detail=hint,
                payload=f"#{key}",
                kind="filter",
                group="Node classes",
            )
            for key, label, hint in available_filters()
        ]

    # ------------------------------------------------------------------
    # Text search
    # ------------------------------------------------------------------
    def _run_text_search(self) -> None:
        query = self._text_query
        if not query:
            return
        files = text_files(self.index)
        if not files:
            self._show_results(
                [info("No text files to search", "Open a project folder first.")]
            )
            return
        self.text_search.search(query, files)

    def _on_text_results(self, generation: int, matches: list) -> None:
        if generation != self.text_search.generation:
            return
        if not self.field.hasFocus() and not self.popup.isVisible():
            return
        if not matches:
            self._show_results(
                [info(f"No matches for '{self._text_query}'", "")]
            )
            return
        self._show_results(text_results(matches, self._text_query))

    def _on_text_failed(self, generation: int, message: str) -> None:
        if generation != self.text_search.generation:
            return
        self._show_results([info("Search failed", message)])

    # ------------------------------------------------------------------
    # Rendering and activation
    # ------------------------------------------------------------------
    def _show_results(self, results: list[SearchResult]) -> None:
        self._results = list(results)
        self.popup.set_results(self._results)
        if self.field.hasFocus() or self.popup.isVisible():
            self.popup.show_at(self.field)

    def _activate(self, result: SearchResult) -> None:
        if result.kind == "mode":
            self._set_mode(str(result.payload))
            return
        if result.kind == "filter":
            prefix = str(result.payload)
            self.field.setText(prefix)
            self.field.setCursorPosition(len(prefix))
            self.field.setFocus()
            self._search()
            return
        if result.kind == "file":
            self._open_file(Path(result.payload[1]))
            return
        if result.kind == "text":
            _kind, path, line, column, length = result.payload
            self._open_text(Path(path), line, column, length)
            return
        if result.kind == "node":
            _kind, editor, node = result.payload
            self._open_node(editor, node)
            return
        if result.kind == "symbol":
            self._open_symbol(result.payload)
            return
        if result.kind == "command":
            command: SearchCommand = result.payload[1]
            self.dismiss(clear=True)
            if command.run is not None:
                command.run()
            return

    def _open_file(self, path: Path) -> None:
        self.workspace.apply_file(str(path))
        self.dismiss(clear=True)

    def _open_text(
        self, path: Path, line: int, column: int, length: int
    ) -> None:
        editor = self.workspace.apply_file(str(path))
        self.dismiss(clear=True)
        if editor is not None and hasattr(editor, "goto_line"):
            editor.goto_line(line, column, length)

    def _open_node(self, editor, node) -> None:
        if hasattr(self.workspace, "tabs"):
            self.workspace.tabs.setCurrentWidget(editor)
        if hasattr(editor, "activate_search_result"):
            editor.activate_search_result(node)
        self.dismiss(clear=True)

    def _open_symbol(self, payload) -> None:
        editor = self.workspace.tabs.currentWidget()
        if payload[0] == "text_range" and hasattr(editor, "goto_range"):
            start, length = payload[1], payload[2]
            editor.goto_range(start, length)
            self.dismiss(clear=True)
        elif payload[0] == "node":
            self._open_node(payload[1], payload[2])

    def _set_mode(self, prefix: str) -> None:
        self.field.setText(prefix)
        self.field.setCursorPosition(len(prefix))
        self.field.setFocus()
        self._search()

    def _focus_editor(self) -> None:
        editor = None
        if hasattr(self.workspace, "tabs"):
            editor = self.workspace.tabs.currentWidget()
        if editor is None:
            return
        view = getattr(editor, "view", None)
        if view is not None:
            view.setFocus()
        else:
            editor.setFocus()

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------
    def _kind(self) -> str:
        if hasattr(self.workspace, "current_kind"):
            try:
                return self.workspace.current_kind()
            except Exception:  # pragma: no cover - defensive
                return ""
        return ""

    def _context(self) -> SearchContext:
        editor = None
        if hasattr(self.workspace, "tabs"):
            editor = self.workspace.tabs.currentWidget()
        return SearchContext(
            project_root=self.index.root,
            active_kind=self._kind(),
            active_widget=editor,
            recent_files=self._recent_paths(),
        )

    @staticmethod
    def _recent_paths() -> list[Path]:
        raw = ConfigManager.get("last_viewed_files")
        if not isinstance(raw, list):
            raw = []
        current = ConfigManager.get("last_viewed_file")
        ordered: list[str] = []
        if isinstance(current, str) and current:
            ordered.append(current)
        ordered.extend(
            path for path in raw if isinstance(path, str) and path not in ordered
        )
        return [Path(path) for path in ordered]

    def _update_placeholder(self, parsed=None) -> None:
        if parsed is None:
            parsed = parse_query(self.field.text(), self._kind())
        if parsed.has_prefix:
            option = OPTIONS_BY_PREFIX.get(parsed.prefix)
            placeholder = (
                option.placeholder
                if option is not None
                else "Search…"
            )
        else:
            root = self.index.root
            placeholder = self._workspace_placeholder(root)
        self.field.setPlaceholderText(placeholder)

    @staticmethod
    def _workspace_placeholder(root: Path | None) -> str:
        name = root.name if root is not None and root.name else "Workspace"
        return f"{name} (Workspace)"
