from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QSizePolicy,
    QWidget,
)
from PySide6.QtCore import Qt

from src.core.signals import signals
from src.gui.settings import Settings
from src.gui.widgets import IconButton
from src.resources.icons import Icons
from src.utils.config_manager import ConfigManager


class MenuBar(QWidget):
    """Single top row combining application menus and former toolbar controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("menuBarContainer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.menu_bar = QMenuBar(self)
        self.menu_bar.setObjectName("menuBar")
        self.menu_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._create_menus()

        self.editor_mode_label = QLabel("No file open", self)
        self.editor_mode_label.setObjectName("TransparentLabel")
        self.editor_mode_label.setToolTip(
            "The editor follows the type of the active tab"
        )

        self.settings = Settings(self)
        self.settings_button = self.settings.call_button
        self.settings_button.setToolTip("Open settings")
        self.settings_button.clicked.connect(self.settings.exec)

        self.search_field = QLineEdit(self)
        self.search_field.setObjectName("quickSearchField")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.setMinimumWidth(280)
        self.search_field.setMaximumWidth(460)
        self.search_field.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.search_field.setToolTip(
            "Search files by name · % text · # nodes · @ symbols · > commands"
        )
        self.search_icon_action = self.search_field.addAction(
            Icons.find(), QLineEdit.ActionPosition.LeadingPosition
        )

        self.left_show_btn = SideBarShowButton(
            "show_left_bar", ConfigManager.get("show_left_bar")
        )
        self.bottom_show_btn = SideBarShowButton(
            "show_bottom_bar", ConfigManager.get("show_bottom_bar")
        )
        self.right_show_btn = SideBarShowButton(
            "show_right_bar", ConfigManager.get("show_right_bar")
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.settings_button)
        layout.setSpacing(6)
        layout.addWidget(self.menu_bar)
        layout.addStretch(1)
        layout.addWidget(self.search_field, 1)
        layout.addStretch(1)
        layout.addWidget(self.editor_mode_label)
        layout.addWidget(self.left_show_btn)
        layout.addWidget(self.bottom_show_btn)
        layout.addWidget(self.right_show_btn)

        signals.theme_changed.connect(self._refresh_search_icon)

    def _create_menus(self) -> None:
        self.menu_bar.addMenu(Files(self.menu_bar))
        self.menu_bar.addMenu(Edit(self.menu_bar))
        self.menu_bar.addMenu(View(self.menu_bar))
        self.menu_bar.addMenu(Help(self.menu_bar))

    def _refresh_search_icon(self, _theme: str = "") -> None:
        self.search_icon_action.setIcon(Icons.find())

    def set_editor_mode(self, kind: str) -> None:
        labels = {
            "scs": "SCS text editor",
            "gwf": "SCg graph editor",
        }
        self.editor_mode_label.setText(labels.get(kind, "No file open"))
        is_text = kind == "scs"
        self.bottom_show_btn.setEnabled(is_text)
        if is_text:
            self.bottom_show_btn.update_icon()
        else:
            self.bottom_show_btn.setToolTip(
                "Problems are only available for text files"
            )


class SideBarShowButton(IconButton):
    def __init__(self, config_name, state: bool = True):
        super().__init__()
        self.config_name = config_name
        self.state = state
        self.update_icon()
        self.clicked.connect(self.on_clicked)
        signals.theme_changed.connect(self._refresh_icon)
        self._visibility_signal().connect(self.set_state)

    def _visibility_signal(self):
        return {
            "show_left_bar": signals.show_left_bar,
            "show_bottom_bar": signals.show_bottom_bar,
            "show_right_bar": signals.show_right_bar,
        }.get(self.config_name)

    def set_state(self, state: bool) -> None:
        self.state = state
        self.update_icon()

    def _refresh_icon(self, _theme: str = "") -> None:
        self.update_icon()

    def update_icon(self) -> None:
        match self.config_name:
            case "show_left_bar":
                self.setIcon(
                    Icons.panel_left_fill() if self.state else Icons.panel_left()
                )
                panel_name = "project file tree"
            case "show_bottom_bar":
                self.setIcon(
                    Icons.panel_bottom_fill()
                    if self.state
                    else Icons.panel_bottom()
                )
                panel_name = "problems panel"
            case "show_right_bar":
                self.setIcon(
                    Icons.panel_right_fill()
                    if self.state
                    else Icons.panel_right()
                )
                panel_name = "AI chat panel"
            case _:
                panel_name = "panel"

        action = "Hide" if self.state else "Show"
        tooltip = f"{action} the {panel_name}"
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)

    def on_clicked(self) -> None:
        self.state = not self.state
        ConfigManager.set(self.config_name, self.state)
        self.update_icon()
        visibility_signal = self._visibility_signal()
        if visibility_signal is not None:
            visibility_signal.emit(self.state)


class Files(QMenu):
    def __init__(self, parent=None):
        super().__init__("Files", parent)
        self.setObjectName("filesMenu")
        self._create_actions()

    def _create_actions(self) -> None:
        open_project_action = self.addAction("Open Project")
        open_project_action.triggered.connect(signals.select_project_requested.emit)

        self.addSeparator()
        create_file_action = self.addAction("Create File")
        create_file_action.triggered.connect(signals.create_file_act.emit)

        create_dir_action = self.addAction("Create Directory")
        create_dir_action.triggered.connect(signals.create_dir_act.emit)

        self.addSeparator()
        save_file_action = self.addAction("Save")
        save_file_action.triggered.connect(signals.save_file_act.emit)

        auto_save_action = self.addAction("Toggle Auto Save")
        auto_save_action.setCheckable(True)
        auto_save_action.setChecked(ConfigManager.get("auto_save"))
        auto_save_action.triggered.connect(self._toggle_auto_save)
        signals.auto_save_changed.connect(auto_save_action.setChecked)

    @staticmethod
    def _toggle_auto_save(checked: bool) -> None:
        ConfigManager.set("auto_save", checked)
        signals.auto_save_changed.emit(checked)


class Edit(QMenu):
    def __init__(self, parent=None):
        super().__init__("Edit", parent)
        self.setObjectName("editMenu")
        self._create_actions()

    def _create_actions(self) -> None:
        pass


class View(QMenu):
    def __init__(self, parent=None):
        super().__init__("View", parent)
        self.setObjectName("viewMenu")
        self._create_actions()

    def _add_panel_action(self, title: str, config_key: str, signal) -> None:
        action = self.addAction(title)
        action.setCheckable(True)
        action.setChecked(ConfigManager.get(config_key))
        action.triggered.connect(
            lambda checked, key=config_key, target=signal: self._set_panel(
                key, target, checked
            )
        )
        signal.connect(action.setChecked)

    @staticmethod
    def _set_panel(config_key: str, signal, checked: bool) -> None:
        ConfigManager.set(config_key, checked)
        signal.emit(checked)

    def _create_actions(self) -> None:
        self._add_panel_action(
            "Toggle Left Sidebar", "show_left_bar", signals.show_left_bar
        )
        self._add_panel_action(
            "Toggle Right Sidebar", "show_right_bar", signals.show_right_bar
        )
        self._add_panel_action(
            "Toggle Bottom Bar", "show_bottom_bar", signals.show_bottom_bar
        )


class Help(QMenu):
    def __init__(self, parent=None):
        super().__init__("Help", parent)
        self.setObjectName("helpMenu")
        self._create_actions()

    def _create_actions(self) -> None:
        pass
