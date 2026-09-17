from PySide6.QtWidgets import QTreeView, QFileSystemModel, QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog
from PySide6.QtCore import QStandardPaths, QSize
from PySide6.QtGui import QIcon

from src.resources.icons import Icons
from src.core.signals import signals
from src.utils.config_manager import ConfigManager
class DirectoryTreeViewWidget(QFrame):
    def __init__(self, parent: QWidget = None, root_path : str = None):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.project_path = root_path
        self.dir_view = DirectoryTreeView(root_path=self.project_path)

        self.dir_view.clicked.connect(self.on_selection_changed)
        self.dir_view.doubleClicked.connect(self.on_double_clicked)

        self.project_manage_layout = QVBoxLayout()
        self.project_dir_manage_layout = QHBoxLayout()
        self.project_manage_layout.addLayout(self.project_dir_manage_layout)

        self.project_dir_label = QLabel(text=root_path)
        self.project_dir_label.setObjectName("TransparentLabel")
        

        self.select_project_dir_btn = QPushButton()
        self.select_project_dir_btn.setObjectName("IconButton")
        self.select_project_dir_btn.setIcon(Icons.FOLDER_SEARCH)
        self.select_project_dir_btn.setIconSize(QSize(25, 25))
        self.select_project_dir_btn.setFixedSize(QSize(30, 30))
        self.select_project_dir_btn.clicked.connect(self.select_project)
        
        self.project_dir_manage_layout.addWidget(self.select_project_dir_btn)
        self.project_dir_manage_layout.addWidget(self.project_dir_label)


        self.main_layout.addLayout(self.project_manage_layout)
        self.main_layout.addWidget(self.dir_view)

    def on_selection_changed(self, index):
        if not self.dir_view.tree_model.isDir(index):
            ConfigManager.set("selected_file", self.dir_view.tree_model.filePath(index))
        else:
            ConfigManager.set("selected_dir", self.dir_view.tree_model.filePath(index))

    def on_double_clicked(self, index):
        if not self.dir_view.tree_model.isDir(index):
            path = self.dir_view.tree_model.filePath(index)
            signals.selected_new_file.emit(path)
            ConfigManager.set("last_viewed_file", path)
            
    def select_project(self):
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
            
class DirectoryTreeView(QTreeView):
    def __init__(self, root_path : str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)):
        super().__init__()
        self.root_path = root_path
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(self.root_path)
        
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