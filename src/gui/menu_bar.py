from PySide6.QtWidgets import QWidget, QMenuBar, QMenu
from src.core.signals import signals

class MenuBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("menuBar")
        self._create_menus()
        
    def _create_menus(self):
        self.addMenu(Files())
        self.addMenu(Edit())
        self.addMenu(View())
        self.addMenu(Help())

class Files(QMenu):
    def __init__(self, parent=None):
        super().__init__("Files", parent)
        self.setObjectName("filesMenu")
        self._create_actions()

    def _create_actions(self):
        

class Edit(QMenu):
    def __init__(self, parent=None):
        super().__init__("Edit", parent)
        self.setObjectName("editMenu")
        self._create_actions()

    def _create_actions(self):
        pass

class View(QMenu):
    def __init__(self, parent=None):
        super().__init__("View", parent)
        self.setObjectName("viewMenu")
        self._create_actions()

    def _create_actions(self):
        pass

class Help(QMenu):
    def __init__(self, parent=None):
        super().__init__("Help", parent)
        self.setObjectName("helpMenu")
        self._create_actions()

    def _create_actions(self):
        pass