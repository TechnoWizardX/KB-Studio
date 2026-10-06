from PySide6.QtWidgets import (QTreeView, QFileSystemModel, QFrame, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFileDialog, QLineEdit,
                               QMessageBox, QMenu)
from PySide6.QtCore import QStandardPaths, QSize, QPoint, QModelIndex, Qt
from PySide6.QtGui import QIcon, QAction

from pathlib import Path
import shutil

from src.resources.icons import Icons
from src.core.signals import signals
from src.utils.config_manager import ConfigManager


class DirectoryTreeViewWidget(QFrame):
    def __init__(self, parent: QWidget = None, root_path : str = None):
        super().__init__()

        ConfigManager.set("selected_file", ConfigManager.get("last_viewed_file"))
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.project_path = root_path
        self.dir_view = DirectoryTreeView(root_path=self.project_path)
        self.dir_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.dir_view.customContextMenuRequested.connect(self.on_tree_context_menu)
        self.dir_view.clicked.connect(self.on_selection_changed)
        self.dir_view.doubleClicked.connect(self.on_double_clicked)

        self.project_manage_layout = QVBoxLayout()
        self.project_struct_manage_layout = QHBoxLayout()
        self.project_manage_layout.addLayout(self.project_struct_manage_layout)

        self.project_dir_label = QLabel(text=root_path)
        self.project_dir_label.setWordWrap(True)
        self.project_dir_label.setObjectName("TransparentLabel")
        
        self.select_project_dir_btn = QPushButton()
        self.select_project_dir_btn.setObjectName("IconButton")
        self.select_project_dir_btn.setIcon(Icons.folder_search())
        self.select_project_dir_btn.setIconSize(QSize(30, 30))
        self.select_project_dir_btn.setFixedSize(QSize(30, 30))
        self.select_project_dir_btn.clicked.connect(self.select_project)
        
        self.project_struct_manage_layout.addWidget(self.select_project_dir_btn)

        self.project_manage_layout.addWidget(self.project_dir_label)


        self.main_layout.addLayout(self.project_manage_layout)
        self.main_layout.addWidget(self.dir_view)

        #------------------------------------------------------------------------------
        #Mkdir, Mkfile, name edit
        #------------------------------------------------------------------------------
        
        self.mk_dir_btn = QPushButton()
        self.mk_dir_btn.setIcon(Icons.folder_add())
        self.mk_dir_btn.setObjectName("IconButton")
        self.mk_dir_btn.setFixedSize(QSize(30, 30))
        self.mk_dir_btn.setIconSize(QSize(30, 30))
        self.project_struct_manage_layout.addWidget(self.mk_dir_btn)
        self.mk_dir_btn.clicked.connect(self.make_new_dir)

        self.mk_file_btn = QPushButton()
        self.mk_file_btn.setIcon(Icons.file_add())
        self.mk_file_btn.setObjectName("IconButton")
        self.mk_file_btn.setFixedSize(QSize(30, 30))
        self.mk_file_btn.setIconSize(QSize(30, 30))
        self.project_struct_manage_layout.addWidget(self.mk_file_btn)
        self.mk_file_btn.clicked.connect(self.make_new_file)

        self.name_edit = QLineEdit()
        self.name_edit.hide()
        self.name_edit.returnPressed.connect(self.create_file_or_dir)
        self.creation_mode = None
        self.project_manage_layout.insertWidget(1, self.name_edit)

        self.project_struct_manage_layout.addStretch(0)

        signals.create_file_act.connect(self.make_new_file)
        signals.create_dir_act.connect(self.make_new_dir)
        signals.execute_create_file.connect(self.execute_create_file)
        signals.execute_create_dir.connect(self.execute_create_dir)

    def on_tree_context_menu(self, point: QPoint):
        index = self.dir_view.indexAt(point)

        menu = ProjectContextMenu(tree = self.dir_view, index=index)

        menu.exec(self.dir_view.mapToGlobal(point))

    def on_selection_changed(self, index) -> None:
        if not self.dir_view.tree_model.isDir(index):
            ConfigManager.set("selected_file", self.dir_view.tree_model.filePath(index))
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
            caption="Select new project folder",
            dir=".",
            options=QFileDialog.Option.ShowDirsOnly
        )
        if new_folder:
            print(f"New project paths: {new_folder}. Registring new Project Tree...")
            signals.selected_new_project_folder.emit(new_folder)
            self.project_path = new_folder
            ConfigManager.set("project_dir", new_folder)
            self.project_dir_label.setText(new_folder)
        else:
            print("Choose declined")

    def make_new_file(self) -> None:
        self.creation_mode = "file"
        self.name_edit.setText("")
        self.name_edit.setPlaceholderText("Enter file name...")
        self.name_edit.show()
        self.name_edit.setFocus()

    def make_new_dir(self) -> None:
        self.creation_mode = "dir"
        self.name_edit.setText("")
        self.name_edit.setPlaceholderText("Enter dir name...")
        self.name_edit.show()
        self.name_edit.setFocus()

    def execute_create_dir(self, name: str) -> None:
        try:
            selected_dir = ConfigManager.get("selected_dir")
            if selected_dir:
                path = selected_dir
            else:
                path = ConfigManager.get("project_dir")
            full_path = Path(path) / name

            if full_path.exists():
                QMessageBox.warning(self, "Error", f"Directory with name '{name}' already exists!")
                return
            
            full_path.mkdir(parents=True, exist_ok=True)
            print(full_path)
        except Exception as e:
            print(f"ERROR: {e}")

    def execute_create_file(self, name: str) -> None:
        try:
            selected_dir = ConfigManager.get("selected_dir")
            if selected_dir:
                path = selected_dir
            else:
                path = ConfigManager.get("project_dir")
            full_path = Path(path) / name
            if full_path.exists():
                QMessageBox.warning(self, "Error", f"File with name '{name}' already exists!")  
                return
            full_path.touch()
        except Exception as e:
            print(f"ERROR {e}")

    def create_file_or_dir(self) -> None:
        name = self.name_edit.text()
        self.name_edit.hide()
        if self.creation_mode == "dir":
            signals.execute_create_dir.emit(name)
        elif self.creation_mode == "file":
            signals.execute_create_file.emit(name)

class DirectoryTreeView(QTreeView):
    def __init__(self, root_path : str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)):
        super().__init__()
        self.root_path = root_path
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(self.root_path)
        self.tree_model.setReadOnly(False)
        
        self.setModel(self.tree_model)
        self.setRootIndex(self.tree_model.index(root_path))
        for column in range(1, self.model().columnCount()):
            self.setColumnHidden(column, True)
        self.setAnimated(True)
        signals.selected_new_project_folder.connect(self.update_project_dir)

    def update_project_dir(self, new_path):
        self.tree_model.setRootPath(new_path)
        self.setModel(self.tree_model)
        self.setRootIndex(self.tree_model.index(new_path))
        self.root_path = new_path

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F2:
            current_index = self.currentIndex()
            if current_index.isValid():
                self.edit(current_index)

        if event.key() == Qt.Key.Key_Delete:
            current_index = self.currentIndex()
            if current_index.isValid():
                path = self.tree_model.filePath(current_index)
                reply = QMessageBox.question(self.window(), "Confirmation", f"Are you sure to delete: \n{path}?", 
                                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
                match reply:
                    case QMessageBox.StandardButton.Yes:
                        try:
                            if self.tree_model.isDir(current_index):
                                shutil.rmtree(path)
                            else:
                                path.unlink()
                        except Exception as e:
                            QMessageBox.critical(self.window(), "Ошибка", f"Не удалось удалить:\n{e}")
                    case QMessageBox.StandardButton.Cancel:
                        pass
                    case _:
                        pass

        super().keyPressEvent(event)

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
        self.is_directory = self.model.isDir(index) if self.index.isValid else False

        self.setObjectName("ContextMenu")
        self._build_menu()

    def _build_menu(self):
        create_file_act = QAction("Create new file", self)
        create_file_act.triggered.connect(self._create_file_act)
        self.addAction(create_file_act)

        create_dir_act = QAction("Create new dir", self)
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
        path = Path(self.target_path)
        reply = QMessageBox.question(self.window(), "Confirmation", f"Are you sure to delete: \n{path}?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        match reply:
            case QMessageBox.StandardButton.Yes:
                try:
                    if self.is_directory:
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                except Exception as e:
                    QMessageBox.critical(self.window(), "Ошибка", f"Не удалось удалить:\n{e}")
            case QMessageBox.StandardButton.Cancel:
                pass
            case _:
                pass