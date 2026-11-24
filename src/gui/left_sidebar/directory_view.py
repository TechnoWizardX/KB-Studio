from PySide6.QtWidgets import (QTreeView, QFileSystemModel, QFrame, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFileDialog, QLineEdit,
                               QMessageBox, QMenu, QFileIconProvider, QSizePolicy)
from PySide6.QtCore import QStandardPaths, QSize, QPoint, QModelIndex, Qt, QEvent, QTimer
from PySide6.QtGui import QAction

from pathlib import Path
import shutil

from src.resources.icons import Icons
from src.core.signals import signals
from src.utils.config_manager import ConfigManager
from src.utils.security import safe_path, validate_filename, PathTraversalError, get_project_root


class DirectoryTreeViewWidget(QFrame):
    def __init__(self, parent: QWidget | None = None, root_path: str | None = None):
        super().__init__(parent)

        ConfigManager.set("selected_file", ConfigManager.get("last_viewed_file"))
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.project_path = root_path
        self.dir_view = DirectoryTreeView(root_path=self.project_path)
        self.dir_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.dir_view.customContextMenuRequested.connect(self.on_tree_context_menu)
        self.dir_view.clicked.connect(self.on_selection_changed)
        self.dir_view.doubleClicked.connect(self.on_double_clicked)

        self.project_manage_layout = QVBoxLayout()
        self.project_manage_layout.setContentsMargins(8, 6, 8, 6)
        self.project_manage_layout.setSpacing(4)
        self.project_struct_manage_layout = QHBoxLayout()
        self.project_struct_manage_layout.setSpacing(4)
        self.project_manage_layout.addLayout(self.project_struct_manage_layout)

        self.project_dir_label = QLabel(text=root_path)
        self.project_dir_label.setWordWrap(True)
        self.project_dir_label.setObjectName("TransparentLabel")
        self.project_dir_label.setToolTip(root_path or "")
        
        self.select_project_dir_btn = QPushButton()
        self.select_project_dir_btn.setObjectName("IconButton")
        self.select_project_dir_btn.setIcon(Icons.folder_search())
        self.select_project_dir_btn.setIconSize(QSize(24, 24))
        self.select_project_dir_btn.setFixedSize(QSize(30, 30))
        self.select_project_dir_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.select_project_dir_btn.setToolTip("Select project folder")
        self.select_project_dir_btn.clicked.connect(self.select_project)
        
        self.project_struct_manage_layout.addWidget(self.select_project_dir_btn)

        self.project_manage_layout.addWidget(self.project_dir_label)


        self.main_layout.addLayout(self.project_manage_layout)
        self.main_layout.addWidget(self.dir_view)

        #------------------------------------------------------------------------------
        # Inline creation row: a line edit overlaid on the tree
        #------------------------------------------------------------------------------
        
        self.mk_dir_btn = QPushButton()
        self.mk_dir_btn.setIcon(Icons.folder_add())
        self.mk_dir_btn.setObjectName("IconButton")
        self.mk_dir_btn.setFixedSize(QSize(30, 30))
        self.mk_dir_btn.setIconSize(QSize(24, 24))
        self.mk_dir_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.mk_dir_btn.setToolTip("New folder")
        self.project_struct_manage_layout.addWidget(self.mk_dir_btn)
        self.mk_dir_btn.clicked.connect(self.make_new_dir)

        self.mk_file_btn = QPushButton()
        self.mk_file_btn.setIcon(Icons.file_add())
        self.mk_file_btn.setObjectName("IconButton")
        self.mk_file_btn.setFixedSize(QSize(30, 30))
        self.mk_file_btn.setIconSize(QSize(24, 24))
        self.mk_file_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.mk_file_btn.setToolTip("New file")
        self.project_struct_manage_layout.addWidget(self.mk_file_btn)
        self.mk_file_btn.clicked.connect(self.make_new_file)

        signals.theme_changed.connect(self._refresh_icons)

        self.name_edit = QLineEdit(self.dir_view.viewport())
        self.name_edit.setObjectName("inlineNameEdit")
        self.name_edit_status = False
        self.name_edit.hide()
        self.name_edit.returnPressed.connect(self.create_file_or_dir)
        self.name_edit.installEventFilter(self)
        self.creation_mode = None
        self._creation_base_path: Path | None = None
        self._context_target_index = QModelIndex()

        self.dir_view.viewport().installEventFilter(self)
        self.dir_view.verticalScrollBar().valueChanged.connect(
            self._position_name_edit
        )
        self.dir_view.horizontalScrollBar().valueChanged.connect(
            self._position_name_edit
        )
        self.dir_view.expanded.connect(lambda _index: self._position_name_edit())
        self.dir_view.collapsed.connect(lambda _index: self._position_name_edit())

        self.project_struct_manage_layout.addStretch(1)

        signals.create_file_act.connect(self.make_new_file)
        signals.create_dir_act.connect(self.make_new_dir)
        signals.select_project_requested.connect(self.select_project)
        signals.execute_create_file.connect(self.execute_create_file)
        signals.execute_create_dir.connect(self.execute_create_dir)

    def _refresh_icons(self, _theme: str) -> None:
        self.select_project_dir_btn.setIcon(Icons.folder_search())
        self.mk_dir_btn.setIcon(Icons.folder_add())
        self.mk_file_btn.setIcon(Icons.file_add())

    def on_tree_context_menu(self, point: QPoint):
        index = self.dir_view.indexAt(point)
        if index.isValid():
            item_path = Path(self.dir_view.tree_model.filePath(index))
            selected_dir = (
                item_path
                if self.dir_view.tree_model.isDir(index)
                else item_path.parent
            )
        else:
            selected_dir = get_project_root()
        ConfigManager.set("selected_dir", str(selected_dir))
        self._context_target_index = index

        menu = ProjectContextMenu(tree = self.dir_view, index=index)

        menu.exec(self.dir_view.mapToGlobal(point))
        self._context_target_index = QModelIndex()

    def on_selection_changed(self, index) -> None:
        if not self.dir_view.tree_model.isDir(index):
            selected_file = Path(self.dir_view.tree_model.filePath(index))
            ConfigManager.set("selected_file", str(selected_file))
            ConfigManager.set("selected_dir", str(selected_file.parent))
        else:
            ConfigManager.set("selected_dir", self.dir_view.tree_model.filePath(index))

    def on_double_clicked(self, index) -> None:
        if not self.dir_view.tree_model.isDir(index):
            path = self.dir_view.tree_model.filePath(index)
            signals.selected_new_file.emit(path)
            ConfigManager.set("last_viewed_file", path)
            
    def select_project(self) -> None:
        new_folder = QFileDialog.getExistingDirectory(
            self,
            caption="Select project folder",
            dir=".",
            options=QFileDialog.Option.ShowDirsOnly
        )
        if new_folder:
            # Clear internal state before emitting signal
            ConfigManager.set("selected_dir", "")
            ConfigManager.set("selected_file", "")
            signals.selected_new_project_folder.emit(new_folder)
            self.project_path = new_folder
            ConfigManager.set("project_dir", new_folder)
            self.project_dir_label.setText(new_folder)
            self.project_dir_label.setToolTip(new_folder)

    def make_new_file(self) -> None:
        self._start_inline_creation("file", "New file name…")

    def make_new_dir(self) -> None:
        self._start_inline_creation("folder", "New folder name…")

    def _start_inline_creation(self, mode: str, placeholder: str) -> None:
        """Show the inline name row below the selected folder."""
        self.creation_mode = mode
        target = self._target_index_for_creation()
        self._context_target_index = QModelIndex()
        if target.isValid():
            self.dir_view.setCurrentIndex(target)
        self._creation_base_path = self._target_dir_for_creation()
        self.name_edit_status = True
        self.name_edit.clear()
        self.name_edit.setPlaceholderText(placeholder)
        self.name_edit.setToolTip("Enter to create · Esc to cancel")
        self._position_name_edit()
        self.name_edit.show()
        self.name_edit.raise_()
        self.name_edit.setFocus()

    def _target_index_for_creation(self) -> QModelIndex:
        """Return the folder row that new items should be created in."""
        index = self._context_target_index
        if not index.isValid():
            index = self.dir_view.currentIndex()
        if not index.isValid():
            return self.dir_view.rootIndex()
        if self.dir_view.tree_model.isDir(index):
            return index
        parent = index.parent()
        return parent if parent.isValid() else self.dir_view.rootIndex()

    def _target_dir_for_creation(self) -> Path:
        index = self._target_index_for_creation()
        if index.isValid():
            try:
                path = Path(self.dir_view.tree_model.filePath(index))
                path.resolve().relative_to(get_project_root())
                if path.is_dir():
                    return path
            except (OSError, ValueError):
                pass
        return get_project_root()

    def _position_name_edit(self) -> None:
        """Keep the inline row attached to its folder while the tree moves."""
        if not self.name_edit_status:
            return

        view = self.dir_view
        index = self._target_index_for_creation()
        if index.isValid() and view.tree_model.isDir(index) and index != view.rootIndex():
            if not view.isExpanded(index):
                view.expand(index)
        view.scrollTo(index)

        rect = view.visualRect(index)
        viewport = view.viewport()
        indent = view.indentation() if index.isValid() else 0
        x = 0
        y = rect.bottom() + 1 if rect.height() else 0
        width = viewport.width()
        height = max(view.sizeHintForRow(0), 24)
        self.name_edit.setTextMargins(indent, 0, 0, 0)
        self.name_edit.setGeometry(x, y, width, height)
        self.name_edit.raise_()

    def _cancel_inline_creation(self) -> None:
        self.name_edit_status = False
        self._creation_base_path = None
        self._context_target_index = QModelIndex()
        self.name_edit.hide()

    def _get_valid_base_path(self) -> Path:
        """Get validated base path within project root."""
        if self._creation_base_path is not None:
            return self._creation_base_path

        project_root = get_project_root()

        selected_dir = ConfigManager.get("selected_dir")
        if selected_dir:
            try:
                # Validate selected_dir is within project root
                selected_path = Path(selected_dir).resolve()
                selected_path.relative_to(project_root)
                if selected_path.is_dir():
                    return selected_path
            except (OSError, ValueError):
                # selected_dir is outside project root, fall back to project root
                pass

        return project_root

    def execute_create_dir(self, name: str) -> None:
        name = name.strip()
        try:
            if not validate_filename(name):
                QMessageBox.warning(
                    self, "Invalid name", f"“{name}” is not a valid folder name."
                )
                return
            
            base_path = self._get_valid_base_path()
            full_path = safe_path(base_path, name)

            if full_path.exists():
                QMessageBox.warning(
                    self,
                    "Already exists",
                    f"“{name}” already exists in this folder.",
                )
                return
            
            full_path.mkdir()
        except PathTraversalError as e:
            QMessageBox.warning(self, "Security error", str(e))
        except OSError as e:
            QMessageBox.critical(
                self, "Create failed", f"Could not create the folder “{name}”:\n{e}"
            )
        except ValueError as e:
            QMessageBox.critical(self, "Create failed", str(e))

    def execute_create_file(self, name: str) -> None:
        name = name.strip()
        try:
            if not validate_filename(name):
                QMessageBox.warning(
                    self, "Invalid name", f"“{name}” is not a valid file name."
                )
                return
            
            base_path = self._get_valid_base_path()
            full_path = safe_path(base_path, name)
            
            if full_path.exists():
                QMessageBox.warning(
                    self,
                    "Already exists",
                    f"“{name}” already exists in this folder.",
                )
                return
            
            with full_path.open("x", encoding="utf-8"):
                pass
        except PathTraversalError as e:
            QMessageBox.warning(self, "Security error", str(e))
        except OSError as e:
            QMessageBox.critical(
                self, "Create failed", f"Could not create the file “{name}”:\n{e}"
            )
        except ValueError as e:
            QMessageBox.critical(self, "Create failed", str(e))

    def create_file_or_dir(self) -> None:
        name = self.name_edit.text()
        self.name_edit_status = False
        self.name_edit.hide()
        if self.creation_mode == "folder":
            signals.execute_create_dir.emit(name)
        elif self.creation_mode == "file":
            signals.execute_create_file.emit(name)
        self._creation_base_path = None
        self._context_target_index = QModelIndex()

    def eventFilter(self, obj, event):
        if obj is self.name_edit:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self._cancel_inline_creation()
                return True
            if event.type() == QEvent.Type.FocusOut and self.name_edit_status:
                # Enter already finishes creation; a click elsewhere cancels.
                QTimer.singleShot(0, self._cancel_after_focus_out)
        elif obj is self.dir_view.viewport():
            if event.type() == QEvent.Type.Resize:
                self._position_name_edit()
        return super().eventFilter(obj, event)

    def _cancel_after_focus_out(self) -> None:
        if self.name_edit_status and not self.name_edit.hasFocus():
            self._cancel_inline_creation()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.name_edit_status:
            self._cancel_inline_creation()
            
        super().keyPressEvent(event)


class DirectoryTreeView(QTreeView):
    def __init__(self, root_path : str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)):
        super().__init__()
        self.root_path = root_path
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(self.root_path)
        self.tree_model.setReadOnly(False)
        self.tree_model.setIconProvider(QFileIconProvider())
        
        self.setModel(self.tree_model)
        self.setRootIndex(self.tree_model.index(root_path))
        for column in range(1, self.model().columnCount()):
            self.setColumnHidden(column, True)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setMouseTracking(True)
        self.setToolTip("Double-click a file to open it")
        signals.selected_new_project_folder.connect(self.update_project_dir)

    def update_project_dir(self, new_path):
        self.tree_model.setRootPath(new_path)
        self.setRootIndex(self.tree_model.index(new_path))
        self.root_path = new_path
        # Clear selection to avoid stale indices
        self.clearSelection()
        self.setCurrentIndex(self.model().index(new_path))

    def mouseMoveEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            path = self.tree_model.filePath(index)
            kind = "Folder" if self.tree_model.isDir(index) else "File"
            self.setToolTip(f"{kind}: {path}")
        else:
            self.setToolTip("Double-click a file to open it")
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F2:
            current_index = self.currentIndex()
            if current_index.isValid():
                self.edit(current_index)

        if event.key() == Qt.Key.Key_Delete:
            current_index = self.currentIndex()
            if current_index.isValid():
                self._delete_index(current_index)

        super().keyPressEvent(event)

    def _delete_index(self, index: QModelIndex) -> None:
        path_str = self.tree_model.filePath(index)
        try:
            path = safe_path(get_project_root(), path_str)
        except PathTraversalError as e:
            QMessageBox.critical(self.window(), "Security error", str(e))
            return

        reply = QMessageBox.question(
            self.window(),
            "Delete",
            f"Delete “{Path(path_str).name}”?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if self.tree_model.isDir(index):
                shutil.rmtree(path)
            else:
                path.unlink()
        except Exception as e:
            QMessageBox.critical(
                self.window(),
                "Delete failed",
                f"Could not delete “{Path(path_str).name}”:\n{e}",
            )

    def mouseDoubleClickEvent(self, event):
            index = self.indexAt(event.position().toPoint())
            if not index.isValid():
                return
            
            if self.tree_model.isDir(index):
                if self.isExpanded(index):
                    self.collapse(index)
                else:
                    self.expand(index)
            else:
                self.doubleClicked.emit(index)
    

class ProjectContextMenu(QMenu):
    def __init__(self, tree: DirectoryTreeView, index: QModelIndex):
        super().__init__()
        self.tree = tree
        self.index = index
        self.model = tree.tree_model

        self.target_path = self.model.filePath(index) if self.index.isValid() else None
        self.is_directory = self.model.isDir(index) if self.index.isValid() else False

        self.setObjectName("ContextMenu")
        self._build_menu()

    def _build_menu(self):
        create_file_act = QAction("New File", self)
        create_file_act.setToolTip("Create a file in the selected folder")
        create_file_act.triggered.connect(self._create_file_act)
        self.addAction(create_file_act)

        create_dir_act = QAction("New Folder", self)
        create_dir_act.setToolTip("Create a folder in the selected folder")
        create_dir_act.triggered.connect(self._create_dir_act)
        self.addAction(create_dir_act)

        if self.target_path:
            self.addSeparator()
            delete_act = QAction("Delete", self)
            delete_act.setShortcut("Del")
            delete_act.triggered.connect(self._delete_act)
            self.addAction(delete_act)

            rename_act = QAction("Rename", self)
            rename_act.setShortcut("F2")
            rename_act.triggered.connect(self._rename_act)
            self.addAction(rename_act)

    def _create_file_act(self):
        signals.create_file_act.emit()

    def _create_dir_act(self):
        signals.create_dir_act.emit()

    def _rename_act(self):
        if self.index.isValid():
            self.tree.edit(self.index)

    def _delete_act(self):
        path_str = self.target_path
        try:
            path = safe_path(get_project_root(), path_str)
        except PathTraversalError as e:
            QMessageBox.critical(self.window(), "Security error", str(e))
            return
        
        reply = QMessageBox.question(
            self.window(),
            "Delete",
            f"Delete “{Path(path_str).name}”?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if self.is_directory:
                shutil.rmtree(path)
            else:
                path.unlink()
        except Exception as e:
            QMessageBox.critical(
                self.window(),
                "Delete failed",
                f"Could not delete “{Path(path_str).name}”:\n{e}",
            )
