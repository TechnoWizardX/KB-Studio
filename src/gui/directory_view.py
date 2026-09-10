from PySide6.QtWidgets import QTreeView, QFileSystemModel, QFrame, QWidget, QVBoxLayout
from PySide6.QtCore import QStandardPaths
class DirectoryTreeViewWidget(QFrame):
    def __init__(self, parent: QWidget = None):
        super().__init__()
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.dir_view = DirectoryTreeView()

        self.main_layout.addWidget(self.dir_view)
class DirectoryTreeView(QTreeView):
    def __init__(self, root_path : str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)):
        super().__init__()
        self.root_path = root_path
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath(self.root_path)
        
        self.setModel(self.tree_model)
        self.setRootIndex(self.tree_model.index(root_path))
