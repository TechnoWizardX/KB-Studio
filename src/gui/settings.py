from PySide6.QtWidgets import (QApplication, QWidget, QDialog, QFrame, QLabel, QPushButton, 
                               QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QCheckBox,
                               QButtonGroup, QSpinBox)
from PySide6.QtCore import Qt, Signal
from src.gui.widgets import IconButton
from src.core.signals import signals
from src.resources.icons import Icons
from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import ThemeManager


class Settings(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.call_button = IconButton(Icons.settings(), "Settings")
        signals.theme_changed.connect(self._refresh_icon)

        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 500)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.settings_content = QWidget()
        self.settings_content.setObjectName("settingsContent")
        self.settings_layout = QVBoxLayout(self.settings_content)
        self.settings_layout.setContentsMargins(16, 16, 16, 16)
        self.settings_layout.setSpacing(10)
        self.scroll_area.setWidget(self.settings_content)
        self.main_layout.addWidget(self.scroll_area)

        self.appearance_label = SettingsSection("Appearance")
        self.settings_layout.addWidget(self.appearance_label)

        self.theme_label = QLabel("Theme")
        self.theme_label.setObjectName("settingsLabel")
        self.theme_frame = QFrame()
        self.theme_frame_layout = QGridLayout(self.theme_frame)
        self.theme_frame_layout.setContentsMargins(16, 12, 16, 12)
        self.theme_frame_layout.setHorizontalSpacing(10)
        self.theme_frame_layout.setVerticalSpacing(10)
        self.settings_layout.addWidget(self.theme_label)
        self.settings_layout.addWidget(self.theme_frame)

        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        current_theme = ConfigManager.get("theme")
        themes = (
            ("Light", "light"),
            ("Dark", "dark"),
            ("Nord", "nord"),
            ("Solarized Light", "solarized_light"),
            ("Лаванда-графит", "lavender_graphite"),
            ("Moccha", "moccha"),
            ("Мята-эспрессо", "mint_espresso"),
        )
        for index, (label, theme_name) in enumerate(themes):
            button = self._create_theme_button(label, theme_name, current_theme == theme_name)
            setattr(self, f"theme_{theme_name}_button", button)
            row, column = divmod(index, 3)
            self.theme_frame_layout.addWidget(button, row, column)

        self.editor_label = SettingsSection("Editor")
        self.editor_frame = QFrame()
        self.editor_frame_layout = QVBoxLayout(self.editor_frame)
        self.editor_frame_layout.setContentsMargins(16, 12, 16, 12)
        self.editor_frame_layout.setSpacing(8)
        self.settings_layout.addWidget(self.editor_label)
        self.settings_layout.addWidget(self.editor_frame)
        
        self.auto_save_checkbox = QCheckBox("Automatically save files and graphs")
        self.auto_save_checkbox.setChecked(bool(ConfigManager.get("auto_save")))
        self.auto_save_checkbox.toggled.connect(self.set_auto_save)
        self.editor_frame_layout.addWidget(self.auto_save_checkbox)

        self.chat_label = SettingsSection("AI chat")
        self.chat_frame = QFrame()
        self.chat_frame_layout = QVBoxLayout(self.chat_frame)
        self.chat_frame_layout.setContentsMargins(16, 12, 16, 12)
        self.chat_frame_layout.setSpacing(8)
        self.settings_layout.addWidget(self.chat_label)
        self.settings_layout.addWidget(self.chat_frame)

        self.startup_message_count = CountChangeSection(
            "Messages loaded at startup",
            "startup_message_count",
            ConfigManager.get("startup_message_count"),
            signals.startup_message_count_updated,
        )
        self.chat_frame_layout.addWidget(self.startup_message_count)

        self.max_context_messages = CountChangeSection(
            "Messages kept as context",
            "message_context_count",
            ConfigManager.get("message_context_count"),
            signals.message_context_count_updated,
        )
        self.chat_frame_layout.addWidget(self.max_context_messages)

        self.settings_layout.addStretch()

    def _create_theme_button(self, label: str, theme: str, checked: bool) -> QPushButton:
        button = QPushButton()
        button.setObjectName("themeButton")
        button.setCheckable(True)
        button.setChecked(checked)
        button.setToolTip(f"Use the {label.lower()} theme")
        button.clicked.connect(
            lambda _checked=False, theme=theme: self.apply_theme(theme)
        )

        layout = QVBoxLayout(button)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        preview = QFrame()
        preview.setObjectName("themePreview")
        preview_layout = QHBoxLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(3)

        colors = ThemeManager.get_theme_colors(theme)
        swatches = (
            colors.get("bg", "#202020"),
            colors.get("accent", "#007acc"),
            colors.get("selection", "#264f78"),
            colors.get("success", "#4ec9b0"),
        )
        for color in swatches:
            swatch = QFrame()
            swatch.setStyleSheet(f"background-color: {color}; border: none;")
            swatch.setMinimumHeight(38)
            preview_layout.addWidget(swatch)

        title = QLabel(label)
        title.setObjectName("themeCardTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview)
        layout.addWidget(title)

        button.setFixedSize(190, 112)
        self.theme_group.addButton(button)
        return button

    def apply_theme(self, theme: str) -> None:
        qss = ThemeManager.build_qss(theme)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(qss)
        ConfigManager.set("theme", theme)
        button = getattr(self, f"theme_{theme}_button", None)
        if button is not None:
            button.setChecked(True)

    def _refresh_icon(self, _theme: str) -> None:
        self.call_button.setIcon(Icons.settings())

    def set_auto_save(self, enabled: bool) -> None:
        ConfigManager.set("auto_save", enabled)
        signals.auto_save_changed.emit(enabled)


class CountChangeSection(QWidget):
    def __init__(
        self,
        text: str,
        config_name: str,
        initial_count: int,
        signal: Signal,
        minimum: int = 1,
        maximum: int = 100000,
        parent=None,
    ):
        super().__init__(parent)
        self._text = text
        self._config_name = config_name
        self._signal = signal

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        self._label = QLabel(text)
        self.main_layout.addWidget(self._label, 1)

        self._spin_box = QSpinBox()
        self._spin_box.setRange(minimum, maximum)
        self._spin_box.setValue(max(minimum, int(initial_count or minimum)))
        self._spin_box.setFixedWidth(100)
        self._spin_box.setKeyboardTracking(False)
        self._spin_box.setToolTip(f"{text} ({minimum}–{maximum})")
        self._label.setBuddy(self._spin_box)
        self.main_layout.addWidget(self._spin_box, 0)

        self._spin_box.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self, new_count: int) -> None:
        self._signal.emit(new_count)
        ConfigManager.set(self._config_name, new_count)

    def emit_change(self) -> None:
        """Apply the current value (kept for callers of the old API)."""
        self._on_value_changed(self._spin_box.value())


class SettingsSection(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(28)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 4, 0, 0)
        self.main_layout.setSpacing(8)

        self._accent = QFrame()
        self._accent.setObjectName("settingsAccent")
        self._accent.setFixedSize(3, 16)
        self.main_layout.addWidget(self._accent, 0)

        self._label = QLabel(text)
        self._label.setObjectName("settingsSectionLabel")
        self.main_layout.addWidget(self._label, 1)

        self._line = QFrame()
        self._line.setObjectName("settingsLine")
        self._line.setFrameShape(QFrame.Shape.HLine)
        self._line.setFixedHeight(1)
        self.main_layout.addWidget(self._line, 6)
