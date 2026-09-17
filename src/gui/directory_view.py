from PySide6.QtWidgets import QTreeView, QFileSystemModel, QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import QStandardPaths, QSize
from PySide6.QtGui import QIcon

from src.resources.icons import Icons
class DirectoryTreeViewWidget(QFrame):
    def __init__(self, parent: QWidget = None, root_path : str = None):
        super().__init__()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.dir_view = DirectoryTreeView(root_path=root_path)

        self.project_manage_layout = QVBoxLayout()
        self.project_dir_manage_layout = QHBoxLayout()
        self.project_manage_layout.addLayout(self.project_dir_manage_layout)

        self.project_dir_label = QLabel(text=root_path)
        self.project_dir_label.setObjectName("TransparentLabel")

        self.select_project_dir_btn = QPushButton()
        self.select_project_dir_btn.setObjectName("IconButton")
        self.select_project_dir_btn.setIcon(Icons.FOLDER_SEARCH)
        self.select_project_dir_btn.setIconSize(QSize(25, 25))
        
        self.project_dir_manage_layout.addWidget(self.select_project_dir_btn)
        self.project_dir_manage_layout.addWidget(self.project_dir_label)


        self.main_layout.addLayout(self.project_manage_layout)
        self.main_layout.addWidget(self.dir_view)

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

        
    def update_project_dir(self, new_path):
        self.tree_model.setRootPath(new_path)
        self.setModel(self.tree_model)
        self.setRootIndex(self.tree_model.index(new_path))
        self.root_path = new_path