"""SCg graph editor widget: toolbar, tool wiring, undo stack and file I/O.

Scene model lives in graph_scene.py, item classes in graph_items.py, the
content dialog in content_dialog.py. This module also re-exports the classic
graph_editor names so existing import sites keep working.
"""
from __future__ import annotations

import math
import os
import signal
import sys
import threading
import time as _time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QShortcut,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QMessageBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.signals import signals
from src.resources.icons import Icons
from src.gui.graph_editor.graph_canvas import GraphCanvasView
from src.gui.graph_editor.graph_commands import (
    CommandConnectorDotsChange,
    CommandConnectorTypeChange,
    CommandCreateBus,
    CommandCreateContour,
    CommandCreateConnector,
    CommandCreateNode,
    CommandDeleteSelection,
    CommandMoveObjects,
    CommandNodeContentChange,
    CommandNodeTypeChange,
    CommandRenameNode,
    CommandSwapConnectorOrientation,
    CommandWaypointsChange,
)
from src.gui.graph_editor.graph_items import (
    GraphAuxObject,
    GraphEdge,
    GraphNode,
)
from src.gui.graph_editor.graph_scene import GraphScene
from src.gui.graph_editor.content_dialog import _ContentDialog
from src.gui.graph_editor.graph_types import (
    CONNECTOR_TYPES as _CONNECTOR_TYPES,
    EDGE_TYPES as _EDGE_TYPES,
    IDENTIFIER as _IDENTIFIER,
    NODE_TYPES as _NODE_TYPES,
    relation_for_gwf as _relation_for_gwf,
)
from src.gui.graph_editor.gwf_codec import (
    content_elements_equal,
    empty_content_element,
)
from src.utils.security import get_project_root, safe_path

def _install_stall_recorder(canvas: "GraphEditorWidget") -> None:
    """Opt-in stall profiler (``KB_CAPTURE_STALLS=1``).

    A background thread watches two concurrency signals:
    the timestamps of a UI-thread QTimer (catches stalls that block the
    event loop even in C code) and the watchdog's own scheduling (catches
    long GIL-holding handlers). When a signal shows a gap of 150 ms or
    more, ``faulthandler`` dumps the current call stacks of all threads
    (the C signal handler runs even while the main thread is stuck), so a
    freeze reproduces with the exact offending code printed to stderr.
    Only active with the environment variable set; normal runs unaffected.
    """
    import faulthandler

    if os.environ.get("KB_CAPTURE_STALLS") != "1":
        return

    probed = {"main": _time.perf_counter()}

    tick_timer = QTimer(canvas)
    tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
    tick_timer.setInterval(10)

    def tick() -> None:
        probed["main"] = _time.perf_counter()

    tick_timer.timeout.connect(tick)
    tick_timer.start()

    signal_number = signal.SIGUSR2
    faulthandler.register(signal_number, file=sys.stderr, all_threads=True)

    def watch() -> None:
        last_own = _time.perf_counter()
        while True:
            _time.sleep(0.01)
            now = _time.perf_counter()
            own_gap = (now - last_own) * 1000
            main_gap = (now - probed["main"]) * 1000
            last_own = now
            if max(own_gap, main_gap) >= 150:
                print(
                    f"\n[stall] detected {max(own_gap, main_gap):.0f}ms "
                    f"(own={own_gap:.0f}ms main={main_gap:.0f}ms), "
                    f"dumping thread stacks:",
                    flush=True,
                )
                os.kill(os.getpid(), signal_number)
                probed["main"] = _time.perf_counter()
                last_own = _time.perf_counter()

    threading.Thread(target=watch, daemon=True).start()


class GraphEditorWidget(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("graphEditorWidget")
        self.file_path: Path | None = None
        self.is_modified = False
        self.is_active = True

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        tools_toolbar = QHBoxLayout()
        layout.addLayout(toolbar)
        layout.addLayout(tools_toolbar)

        def add_button(bar, icon_kind, tooltip, slot=None, checkable=False):
            button = QToolButton(self)
            button.setIcon(icon_kind)
            button.setIconSize(QSize(20, 20))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setToolTip(tooltip)
            button.setStatusTip(tooltip)
            button.setCheckable(checkable)
            if slot is not None:
                button.clicked.connect(slot)
            bar.addWidget(button)
            return button

        self.new_button = add_button(
            toolbar, Icons.new_graph(), "New graph", self.new_graph
        )

        self.node_type_combo = QComboBox()
        self.node_type_combo.setMaximumWidth(190)
        for label, gwf_type in _NODE_TYPES:
            self.node_type_combo.addItem(label, gwf_type)
        default_node_type = self.node_type_combo.findData("node/const/general_node")
        if default_node_type >= 0:
            self.node_type_combo.setCurrentIndex(default_node_type)
        self.node_type_combo.setToolTip("Type of new nodes or the selected node")
        toolbar.addWidget(self.node_type_combo)

        self.edge_type_combo = QComboBox()
        self.edge_type_combo.setMaximumWidth(210)
        for label, gwf_type, gwf_tag, scs_token in _CONNECTOR_TYPES:
            self.edge_type_combo.addItem(label, (gwf_type, gwf_tag, scs_token))
        self.edge_type_combo.setToolTip(
            "Type of new connectors or the selected connector"
        )
        toolbar.addWidget(self.edge_type_combo)

        self.rename_edit = QLineEdit()
        self.rename_edit.setPlaceholderText("Selected node name")
        self.rename_edit.returnPressed.connect(self.rename_selected)
        toolbar.addWidget(self.rename_edit)

        self.rename_button = add_button(
            toolbar, Icons.rename(), "Rename selected node", self.rename_selected
        )

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find node")
        self.search_edit.returnPressed.connect(self.find_node)
        toolbar.addWidget(self.search_edit)

        self.find_button = add_button(
            toolbar, Icons.find(), "Find node", self.find_node
        )

        self.remove_button = add_button(
            toolbar, Icons.delete(), "Delete selection (Del)", self.remove_selected
        )

        self.save_button = add_button(
            toolbar, Icons.save(), "Save graph", self.save
        )
        toolbar.addStretch()

        self.undo_stack = QUndoStack(self)
        self.undo_button = add_button(
            tools_toolbar, Icons.undo(), "Undo (Ctrl+Z)", self.undo_stack.undo
        )
        self.undo_button.setEnabled(False)
        self.redo_button = add_button(
            tools_toolbar, Icons.redo(), "Redo (Ctrl+Shift+Z)", self.undo_stack.redo
        )
        self.redo_button.setEnabled(False)
        self.undo_stack.canUndoChanged.connect(self.undo_button.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.redo_button.setEnabled)
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self._undo_if_not_editing)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self._redo_if_not_editing)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self.save)

        self.zoom_in_button = add_button(
            tools_toolbar, Icons.zoom_in(), "Zoom in", lambda: self.view.zoom_in()
        )

        self.zoom_out_button = add_button(
            tools_toolbar, Icons.zoom_out(), "Zoom out", lambda: self.view.zoom_out()
        )

        self.fit_button = add_button(
            tools_toolbar, Icons.fit(), "Fit graph to view", self.fit_graph
        )

        for arrangement, icon_kind, label in (
            (self._arrange_grid, Icons.arrange_grid(), "Arrange as grid"),
            (self._arrange_vertical, Icons.arrange_vertical(), "Arrange in a vertical line"),
            (self._arrange_horizontal, Icons.arrange_horizontal(), "Arrange in a horizontal line"),
            (self._arrange_tuple, Icons.arrange_tuple(), "Arrange neighbours around the selected node"),
        ):
            add_button(tools_toolbar, icon_kind, label, arrangement)

        self.export_button = add_button(
            tools_toolbar,
            Icons.export_image(),
            "Export graph to PNG",
            self.export_image,
        )

        self.scene = GraphScene(self)
        self.view = GraphCanvasView(
            self.scene,
            GraphNode,
            GraphEdge,
            self._create_node_at,
            self._create_connector,
            self._create_bus,
            self._create_contour,
            self._commit_move,
            self._show_context_menu,
            self.remove_selected,
            contour_class=GraphAuxObject,
        )
        self.view.tool_error.connect(self._show_tool_error)
        self.view.tool_changed.connect(self._show_tool)
        layout.addWidget(self.view)
        _install_stall_recorder(self)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons: dict[str, QToolButton] = {}
        for tool, icon_kind, label in (
            (GraphCanvasView.SELECT, Icons.tool_select(), "Select and move (1)"),
            (GraphCanvasView.CONNECTOR, Icons.tool_connector(), "Create connectors (2)"),
            (GraphCanvasView.BUS, Icons.tool_bus(), "Create buses (3)"),
            (GraphCanvasView.CONTOUR, Icons.tool_contour(), "Create contours (4)"),
            (GraphCanvasView.NODE, Icons.tool_node(), "Create nodes (5)"),
        ):
            button = add_button(
                tools_toolbar, icon_kind, label, checkable=True
            )
            button.clicked.connect(
                lambda checked, selected_tool=tool: self.view.set_tool(selected_tool)
                if checked
                else None
            )
            self.tool_group.addButton(button)
            self.tool_buttons[tool] = button
        self.tool_buttons[GraphCanvasView.SELECT].setChecked(True)
        self.view.tool_changed.connect(self._sync_tool_button)

        self.status_label = QLineEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setObjectName("graphEditorStatus")
        layout.addWidget(self.status_label)

        self.scene.model_changed.connect(self._mark_modified)
        self.scene.selectionChanged.connect(self._sync_type_selectors)
        self.scene.rename_requested.connect(self._on_rename_requested)
        self.scene.waypoints_changed.connect(self._on_waypoints_changed)
        self.scene.dots_changed.connect(self._on_dots_changed)
        self.node_type_combo.currentIndexChanged.connect(self._apply_selected_node_type)
        self.edge_type_combo.currentIndexChanged.connect(
            self._apply_selected_connector_type
        )
        signals.selected_new_file.connect(self.apply_file)
        self._mark_modified(False)
        self.status_label.setText("Create a graph or open a .gwf file.")

    def apply_file(self, file_path: str | Path) -> None:
        if not self.is_active:
            return
        if not file_path or Path(file_path).suffix.lower() != ".gwf":
            return
        try:
            safe_file = safe_path(get_project_root(), str(file_path))
            if not safe_file.is_file():
                raise FileNotFoundError(f"Not a file: {safe_file}")
            source = safe_file.read_bytes()
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.warning(self, "Cannot open graph", str(error))
            return

        if safe_file == self.file_path:
            return
        if not self._confirm_replace_current_graph():
            return
        try:
            self.scene.load_gwf(source)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot open graph", str(error))
            return
        self.file_path = safe_file
        self._mark_modified(False)
        self.undo_stack.clear()
        self.status_label.setText(f"Opened {safe_file.name}.")

    def set_active(self, active: bool) -> None:
        self.is_active = active

    def new_graph(self) -> None:
        if not self._confirm_replace_current_graph():
            return
        self.scene.load_scs("")
        self.file_path = None
        self._mark_modified(True)
        self.undo_stack.clear()
        self.status_label.setText("New graph — save it as a .gwf file.")

    def _create_node_at(self, position: QPointF) -> None:
        index = len(self.scene.nodes) + 1
        while f"node_{index}" in self.scene.nodes:
            index += 1
        try:
            self.undo_stack.push(
                CommandCreateNode(
                    self.scene,
                    f"node_{index}",
                    position,
                    self.node_type_combo.currentData(),
                )
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def _create_connector(
        self,
        source: object,
        target: object,
        source_anchor: QPointF,
        target_anchor: QPointF,
    ) -> None:
        if (
            not isinstance(source, (GraphNode, GraphEdge, GraphAuxObject))
            or not isinstance(
                target, (GraphNode, GraphEdge, GraphAuxObject)
            )
        ):
            self._show_tool_error(
                "Connectors must join nodes, connectors, contours or buses."
            )
            return
        gwf_type, gwf_tag, token = self.edge_type_combo.currentData()
        try:
            self.undo_stack.push(
                CommandCreateConnector(
                    self.scene,
                    source,
                    target,
                    token,
                    gwf_type=gwf_type,
                    gwf_tag=gwf_tag,
                    source_anchor=source_anchor,
                    target_anchor=target_anchor,
                )
            )
            self._show_tool("connector")
        except ValueError as error:
            self._show_tool_error(str(error))

    def _create_bus(self, owner: object, endpoint: QPointF) -> None:
        if not isinstance(owner, GraphNode):
            self._show_tool_error("A bus must start on a node.")
            return
        try:
            self.undo_stack.push(CommandCreateBus(self.scene, owner, endpoint))
        except ValueError as error:
            self._show_tool_error(str(error))

    def _create_contour(self, points: list[QPointF]) -> None:
        try:
            self.undo_stack.push(
                CommandCreateContour(self.scene, points)
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def _commit_move(self, old_positions: dict) -> None:
        command = CommandMoveObjects(self.scene, old_positions)
        if not command.is_empty():
            self.undo_stack.push(command)

    def _apply_positions(self, positions: dict) -> None:
        old_positions = {
            node: QPointF(node.pos())
            for node, target in positions.items()
            if node.scene() is self.scene and node.pos() != target
        }
        for node, target in positions.items():
            node.setPos(target)
        self._commit_move(old_positions)

    def _arrange_grid(self) -> None:
        nodes = sorted(
            self.scene.nodes.values(),
            key=lambda node: (node.pos().y(), node.pos().x()),
        )
        if len(nodes) < 2:
            return
        columns = math.ceil(math.sqrt(len(nodes)))
        anchor_x = min(node.pos().x() for node in nodes)
        anchor_y = min(node.pos().y() for node in nodes)
        positions = {
            node: QPointF(
                anchor_x + (index % columns) * 150,
                anchor_y + (index // columns) * 120,
            )
            for index, node in enumerate(nodes)
        }
        self._apply_positions(positions)

    def _arrange_vertical(self) -> None:
        nodes = sorted(
            self.scene.nodes.values(), key=lambda node: node.pos().y()
        )
        if len(nodes) < 2:
            return
        anchor_x = sum(node.pos().x() for node in nodes) / len(nodes)
        anchor_y = min(node.pos().y() for node in nodes)
        positions = {
            node: QPointF(anchor_x, anchor_y + index * 130)
            for index, node in enumerate(nodes)
        }
        self._apply_positions(positions)

    def _arrange_horizontal(self) -> None:
        nodes = sorted(
            self.scene.nodes.values(), key=lambda node: node.pos().x()
        )
        if len(nodes) < 2:
            return
        anchor_y = sum(node.pos().y() for node in nodes) / len(nodes)
        anchor_x = min(node.pos().x() for node in nodes)
        positions = {
            node: QPointF(anchor_x + index * 170, anchor_y)
            for index, node in enumerate(nodes)
        }
        self._apply_positions(positions)

    def _arrange_tuple(self) -> None:
        roots = [
            item
            for item in self.scene.selectedItems()
            if isinstance(item, GraphNode)
        ]
        if len(roots) != 1:
            self._show_tool_error(
                "Select exactly one node to arrange its neighbours."
            )
            return
        root = roots[0]
        neighbours: list[GraphNode] = []
        for edge in self.scene.edges:
            if edge.source is root and isinstance(edge.target, GraphNode):
                if edge.target not in neighbours:
                    neighbours.append(edge.target)
            elif edge.target is root and isinstance(edge.source, GraphNode):
                if edge.source not in neighbours:
                    neighbours.append(edge.source)
        neighbours = [item for item in neighbours if item is not root]
        if not neighbours:
            self._show_tool_error("The selected node has no neighbours.")
            return
        center = root.scenePos()
        radius = 170.0
        positions = {
            neighbour: QPointF(
                center.x() + radius * math.cos(
                    -math.pi / 2
                    + 2 * math.pi * index / len(neighbours)
                ),
                center.y() + radius * math.sin(
                    -math.pi / 2
                    + 2 * math.pi * index / len(neighbours)
                ),
            )
            for index, neighbour in enumerate(neighbours)
        }
        self._apply_positions(positions)

    def _show_tool_error(self, message: str) -> None:
        self.status_label.setText(message)

    def _on_waypoints_changed(self, edge, old_waypoints, new_waypoints) -> None:
        self.undo_stack.push(
            CommandWaypointsChange(self.scene, edge, old_waypoints, new_waypoints)
        )

    def _on_dots_changed(self, edge, old_dots, new_dots) -> None:
        self.undo_stack.push(
            CommandConnectorDotsChange(self.scene, edge, old_dots, new_dots)
        )

    def _on_rename_requested(self, node: GraphNode, identifier: str) -> None:
        if not _IDENTIFIER.fullmatch(identifier):
            node.label.restore_text(node.identifier)
            self._show_tool_error("Node names must be valid SCs identifiers.")
            return
        if identifier != node.identifier and identifier in self.scene.nodes:
            node.label.restore_text(node.identifier)
            self._show_tool_error(
                f"A node named '{identifier}' already exists."
            )
            return
        self.undo_stack.push(CommandRenameNode(self.scene, node, identifier))

    def _show_tool(self, tool: str) -> None:
        self.status_label.setText(
            {
                GraphCanvasView.SELECT: "Select and move SCg objects.",
                GraphCanvasView.NODE: "Click the canvas to create a node.",
                GraphCanvasView.CONNECTOR:                 "Drag from a node, connector or contour to another graph object to create an arc.",
                GraphCanvasView.BUS: "Drag from an owner node to place a bus.",
                GraphCanvasView.CONTOUR: (
                    "Click contour vertices; to close, click the first "
                    "vertex again, double-click, or press Enter."
                ),
            }[tool]
        )

    def _sync_type_selectors(self) -> None:
        selected_nodes = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphNode)
        ]
        if len(selected_nodes) == 1:
            index = self.node_type_combo.findData(selected_nodes[0].gwf_type)
            if index >= 0:
                self.node_type_combo.setCurrentIndex(index)

        selected_edges = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphEdge)
        ]
        if len(selected_edges) == 1:
            edge = selected_edges[0]
            match = (edge.gwf_type, edge.gwf_tag, edge.edge_type)
            index = self.edge_type_combo.findData(match)
            if index >= 0:
                self.edge_type_combo.setCurrentIndex(index)
        selected_aux = [
            item
            for item in self.scene.selectedItems()
            if isinstance(item, GraphAuxObject)
        ]
        if len(selected_aux) == 1:
            self.rename_edit.setText(selected_aux[0].gwf_element.get("idtf", ""))

    def _sync_tool_button(self, tool: str) -> None:
        button = self.tool_buttons.get(tool)
        if button is not None:
            button.setChecked(True)

    def _apply_selected_node_type(self) -> None:
        nodes = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphNode)
        ]
        if len(nodes) != 1:
            return
        self._set_node_type(nodes[0], self.node_type_combo.currentData())

    def _set_node_type(self, node: GraphNode, gwf_type: str) -> None:
        if node.gwf_type == gwf_type:
            return
        try:
            self.undo_stack.push(
                CommandNodeTypeChange(self.scene, node, gwf_type)
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def _apply_selected_connector_type(self) -> None:
        edges = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphEdge)
        ]
        if len(edges) != 1:
            return
        gwf_type, gwf_tag, edge_type = self.edge_type_combo.currentData()
        self._set_connector_type(edges[0], gwf_type, gwf_tag, edge_type)

    def _set_connector_type(
        self, edge: GraphEdge, gwf_type: str, gwf_tag: str, edge_type: str
    ) -> None:
        if (edge.gwf_type, edge.gwf_tag, edge.edge_type) == (
            gwf_type,
            gwf_tag,
            edge_type,
        ):
            return
        try:
            self.undo_stack.push(
                CommandConnectorTypeChange(
                    self.scene, edge, gwf_type, gwf_tag, edge_type
                )
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def _show_context_menu(self, scene_pos: QPointF, item, global_pos) -> None:
        menu = QMenu(self)
        if item is None:
            add_action = menu.addAction("Add node here")
            chosen = menu.exec(global_pos)
            if chosen is add_action:
                self._create_node_at(scene_pos)
            return

        if not item.isSelected():
            self.scene.clearSelection()
            item.setSelected(True)

        rename_action = None
        content_action = None
        type_menu = None
        if isinstance(item, GraphNode):
            rename_action = menu.addAction("Rename")
            content_action = menu.addAction(
                "Edit content…" if item.has_content() else "Add content…"
            )
            type_menu = menu.addMenu("Node type")
            for label, gwf_type in _NODE_TYPES:
                type_action = type_menu.addAction(label)
                type_action.triggered.connect(
                    lambda checked=False,
                    node=item,
                    node_type=gwf_type: self._set_node_type(node, node_type)
                )
        elif isinstance(item, GraphEdge):
            if item.gwf_tag == "pair":
                menu.addAction("Reverse direction").triggered.connect(
                    lambda checked=False: self._swap_connector(item)
                )
            type_menu = menu.addMenu("Connector type")
            for label, gwf_type, gwf_tag, edge_type in _CONNECTOR_TYPES:
                type_action = type_menu.addAction(label)
                type_action.triggered.connect(
                    lambda checked=False,
                    connector=item,
                    connector_type=gwf_type,
                    connector_tag=gwf_tag,
                    connector_token=edge_type: self._set_connector_type(
                        connector, connector_type, connector_tag, connector_token
                    )
                )
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(global_pos)
        if chosen is not None and chosen is delete_action:
            self.remove_selected()
        elif rename_action is not None and chosen is rename_action:
            QTimer.singleShot(0, item.label.start_editing)
        elif content_action is not None and chosen is content_action:
            QTimer.singleShot(
                0, lambda node=item: self._open_content_editor(node)
            )

    def _open_content_editor(self, node: GraphNode) -> None:
        dialog = _ContentDialog(node, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        element = dialog.result_content()
        if element is None:
            if not node.has_content():
                return
            element = empty_content_element()
        elif content_elements_equal(element, node.content_element()):
            return
        self.undo_stack.push(CommandNodeContentChange(self.scene, node, element))

    def _swap_connector(self, edge: GraphEdge) -> None:
        if edge.gwf_tag != "pair":
            self._show_tool_error("Only pairs can swap their direction.")
            return
        try:
            self.undo_stack.push(
                CommandSwapConnectorOrientation(self.scene, edge)
            )
        except ValueError as error:
            self._show_tool_error(str(error))

    def find_node(self) -> None:
        query = self.search_edit.text().strip().casefold()
        if not query:
            self._show_tool_error("Enter a node identifier to find.")
            return
        node = next(
            (
                candidate
                for candidate in self.scene.nodes.values()
                if candidate.identifier.casefold() == query
                or candidate.gwf_idtf.casefold() == query
            ),
            None,
        )
        if node is None:
            self._show_tool_error(f"No node found for '{self.search_edit.text()}'.")
            return
        self.scene.clearSelection()
        node.setSelected(True)
        self.view.centerOn(node)
        self.view.setFocus()

    def fit_graph(self) -> None:
        bounds = self.scene.itemsBoundingRect()
        if bounds.isEmpty():
            bounds = self.scene.sceneRect()
        self.view.fitInView(
            bounds.adjusted(-24, -24, 24, 24),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def export_image(self) -> None:
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export graph image",
            "graph.png",
            "PNG images (*.png)",
        )
        if not selected_path:
            return
        output_path = Path(selected_path)
        if output_path.suffix.lower() != ".png":
            output_path = output_path.with_suffix(".png")
        bounds = self.scene.itemsBoundingRect().adjusted(-24, -24, 24, 24)
        if bounds.isEmpty():
            bounds = self.scene.sceneRect()
        image = QImage(
            max(1, math.ceil(bounds.width())),
            max(1, math.ceil(bounds.height())),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(QColor("#1e1e1e"))
        painter = QPainter(image)
        self.scene.render(painter, QRectF(image.rect()), bounds)
        painter.end()
        if not image.save(str(output_path)):
            self._show_tool_error(f"Could not export image to {output_path}.")
            return
        self.status_label.setText(f"Exported {output_path.name}.")

    def rename_selected(self) -> None:
        nodes = [
            item for item in self.scene.selectedItems() if isinstance(item, GraphNode)
        ]
        if len(nodes) != 1:
            QMessageBox.information(
                self, "Select a node", "Select exactly one node to rename."
            )
            return
        try:
            self.undo_stack.push(
                CommandRenameNode(
                    self.scene, nodes[0], self.rename_edit.text().strip()
                )
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid node name", str(error))

    def remove_selected(self) -> None:
        command = CommandDeleteSelection(self.scene, self.scene.selectedItems())
        if command.is_empty():
            return
        self.undo_stack.push(command)

    def save(self) -> None:
        if self.file_path is None:
            try:
                project_root = get_project_root()
            except ValueError as error:
                QMessageBox.warning(self, "Cannot save graph", str(error))
                return
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save graph",
                str(project_root / "graph.gwf"),
                "GWF files (*.gwf)",
            )
            if not selected_path:
                return
            selected = Path(selected_path)
            if selected.suffix.lower() != ".gwf":
                selected = selected.with_suffix(".gwf")
            try:
                self.file_path = safe_path(project_root, str(selected))
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Cannot save graph", str(error))
                return

        try:
            safe_file = safe_path(get_project_root(), str(self.file_path))
            content = self.scene.to_gwf()
            safe_file.write_text(content, encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.warning(self, "Cannot save graph", str(error))
            return
        self.file_path = safe_file
        self._mark_modified(False)
        self.status_label.setText(f"Saved {self.file_path.name}.")

    def _confirm_replace_current_graph(self) -> bool:
        if not self.is_modified:
            return True
        answer = QMessageBox.warning(
            self,
            "Unsaved graph",
            "Save changes to the current graph before replacing it?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            self.save()
            return not self.is_modified
        return answer == QMessageBox.StandardButton.Discard

    def _label_editor_active(self) -> bool:
        """True, пока активно inplace-редактирование подписи узла."""
        focus_item = self.scene.focusItem()
        return bool(getattr(focus_item, "_editing", False))

    def _undo_if_not_editing(self) -> None:
        # Ctrl+Z внутри редактируемой подписи должен откатывать текст, а не
        # исполнения команд сцены.
        if self._label_editor_active():
            return
        self.undo_stack.undo()

    def _redo_if_not_editing(self) -> None:
        if self._label_editor_active():
            return
        self.undo_stack.redo()

    def _mark_modified(self, modified: bool = True) -> None:
        self.is_modified = modified
        self.save_button.setEnabled(modified or self.file_path is None)
        title = "Save *" if modified else "Save"
        self.save_button.setText(title)
