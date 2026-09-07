from PySide6.QtWidgets import QTreeView, QFileSystemModel, QFrame, QWidget, QVBoxLayout
class DirectoryTreeViewWidget(QFrame):
    def __init__(self, parent: QWidget = None):
        super().__init__()
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.dir_view = DirectoryTreeView()

        self.main_layout.addWidget(self.dir_view)
class DirectoryTreeView(QTreeView):
    def __init__(self, root_path : str = None):
        super().__init__()
        self.tree_model = QFileSystemModel
    