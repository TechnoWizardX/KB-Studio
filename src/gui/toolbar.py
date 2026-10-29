from PySide6.QtCore import QSignalBlocker, QSize
from PySide6.QtWidgets import QHBoxLayout, QComboBox, QSizePolicy, QWidget, QPushButton

from src.gui.settings import Settings
from src.utils.config_manager import ConfigManager
from src.resources.icons import Icons
from src.core.signals import signals
class ToolBar(QWidget):
    """Top bar: editor switcher and settings button."""

    def __init__(self, select_editor_func, parent=None):
        super().__init__(parent)
        self.setObjectName("toolBar")
        self._size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.setSizePolicy(self._size_policy)

        self._select_editor = select_editor_func

        self.settings = Settings(self)
        self.settings_button = self.settings.call_button
        self.settings_button.clicked.connect(self.settings.exec)

        self.editor_selector = QComboBox()
        self.editor_selector.setToolTip("Select editor")
        with QSignalBlocker(self.editor_selector):
            self.editor_selector.addItem("SCs text editor")
            self.editor_selector.addItem("SCg graph editor")
        self.editor_selector.setCurrentIndex(0)
        self.editor_selector.currentIndexChanged.connect(self._select_editor)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)
        self.main_layout.addWidget(self.editor_selector)
        self.main_layout.addWidget(self.settings_button)
        self.main_layout.addStretch()

        self.left_show_btn = SideBarShowButton("show_left_bar", ConfigManager.get("show_left_bar"))
        self.bottom_show_btn = SideBarShowButton("show_bottom_bar", ConfigManager.get("show_bottom_bar"))
        self.right_show_btn = SideBarShowButton("show_right_bar", ConfigManager.get("show_right_bar"))


        self.main_layout.addWidget(self.left_show_btn)
        self.main_layout.addWidget(self.bottom_show_btn)
        self.main_layout.addWidget(self.right_show_btn)

class SideBarShowButton (QPushButton):
    def __init__(self, config_name, state : bool = True):
        super().__init__()
        self.setObjectName("IconButton")
        self.setIconSize(QSize(30, 30))
        self.setFixedSize(QSize(30, 30))
        self.config_name = config_name
        self.state : bool= state

        self.update_icon()
        self.clicked.connect(self.on_clicked)
        signals.theme_changed.connect(self._refresh_icon)

    def _refresh_icon(self, theme : str):
        self.update_icon()

    def update_icon(self):
        match self.config_name:
            case "show_left_bar":
                self.setIcon(Icons.panel_left_fill() if self.state else Icons.panel_left())
            case "show_bottom_bar":
                self.setIcon(Icons.panel_bottom_fill() if self.state else Icons.panel_bottom())
            case "show_right_bar":
                self.setIcon(Icons.panel_right_fill() if self.state else Icons.panel_right())

    def on_clicked(self):
        self.state = not self.state
        
        ConfigManager.set(self.config_name, self.state)
        
        self.update_icon()
        match self.config_name:
            case "show_left_bar":
                signals.show_left_bar.emit(self.state)
            case "show_bottom_bar":
                signals.show_bottom_bar.emit(self.state)
            case "show_right_bar":
                signals.show_right_bar.emit(self.state)