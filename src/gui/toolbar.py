from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from src.gui.settings import Settings
from src.gui.widgets import IconButton
from src.utils.config_manager import ConfigManager
from src.resources.icons import Icons
from src.core.signals import signals


class ToolBar(QWidget):
    """Top bar: active editor label, new graph action and settings."""

    def __init__(self, new_graph_func=None, parent=None):
        super().__init__(parent)
        self.setObjectName("toolBar")
        self._size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.setSizePolicy(self._size_policy)

        self.settings = Settings(self)
        self.settings_button = self.settings.call_button
        self.settings_button.setToolTip("Open settings")
        self.settings_button.clicked.connect(self.settings.exec)

        self.editor_mode_label = QLabel("No file open")
        self.editor_mode_label.setObjectName("TransparentLabel")
        self.editor_mode_label.setToolTip(
            "The editor follows the type of the active tab"
        )

        self.new_graph_button = IconButton(Icons.new_graph(), "New graph")
        if new_graph_func is not None:
            self.new_graph_button.clicked.connect(new_graph_func)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)
        self.main_layout.addWidget(self.editor_mode_label)
        self.main_layout.addWidget(self.new_graph_button)
        self.main_layout.addWidget(self.settings_button)
        self.main_layout.addStretch()

        self.left_show_btn = SideBarShowButton("show_left_bar", ConfigManager.get("show_left_bar"))
        self.bottom_show_btn = SideBarShowButton("show_bottom_bar", ConfigManager.get("show_bottom_bar"))
        self.right_show_btn = SideBarShowButton("show_right_bar", ConfigManager.get("show_right_bar"))


        self.main_layout.addWidget(self.left_show_btn)
        self.main_layout.addWidget(self.bottom_show_btn)
        self.main_layout.addWidget(self.right_show_btn)

    def set_editor_mode(self, kind: str) -> None:
        """Show which editor owns the active tab and gate the Problems panel."""
        labels = {
            "scs": "SCS text editor",
            "gwf": "SCg graph editor",
        }
        self.editor_mode_label.setText(labels.get(kind, "No file open"))

        if not hasattr(self, "bottom_show_btn"):
            return
        is_text = kind == "scs"
        self.bottom_show_btn.setEnabled(is_text)
        if is_text:
            self.bottom_show_btn.update_icon()
        else:
            self.bottom_show_btn.setToolTip(
                "Problems are only available for text files"
            )


class SideBarShowButton(IconButton):
    def __init__(self, config_name, state : bool = True):
        super().__init__()
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
                panel_name = "project file tree"
            case "show_bottom_bar":
                self.setIcon(Icons.panel_bottom_fill() if self.state else Icons.panel_bottom())
                panel_name = "problems panel"
            case "show_right_bar":
                self.setIcon(Icons.panel_right_fill() if self.state else Icons.panel_right())
                panel_name = "AI chat panel"
            case _:
                panel_name = "panel"

        action = "Hide" if self.state else "Show"
        tooltip = f"{action} the {panel_name}"
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)

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