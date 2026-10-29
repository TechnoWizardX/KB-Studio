from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.gui.left_sidebar.directory_view import DirectoryTreeViewWidget

from src.core.signals import signals

class LeftSidebarWidget(QWidget):
    """Left side panel host: project directory tree."""

    def __init__(self, parent: QWidget | None = None, root_path: str | None = None, show : bool = True):
        super().__init__(parent)
        self.setObjectName("leftSidebar")

        self.panel = DirectoryTreeViewWidget(parent=self, root_path=root_path)

        self.show_self = show
        if show:
            self.show()
        else:
            self.hide()

        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.addWidget(self.panel)
        signals.show_left_bar.connect(self._change_show)

    def _change_show(self, show):
        if show:
            self.show()
        else:
            self.hide()