from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.gui.right_sidebar.chat import ChatBot

from src.core.signals import signals

class RightSidebarWidget(QWidget):
    """Right side panel host: AI chat."""

    def __init__(self, parent: QWidget | None = None, show : bool = True):
        super().__init__(parent)
        self.setObjectName("rightSidebar")

        self.panel = ChatBot()
        self.show_self = show
        if show:
            self.show()
        else:
            self.hide()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.addWidget(self.panel)
        signals.show_right_bar.connect(self._change_show)

    def _change_show(self, show):
            if show:
                self.show()
            else:
                self.hide()