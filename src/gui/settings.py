from PySide6.QtWidgets import (QApplication, QWidget, QDialog, QFrame, QLabel, QLineEdit, QPushButton, 
                               QVBoxLayout, QHBoxLayout, QScrollArea, QCheckBox, QMessageBox)
from PySide6.QtCore import QSize, Signal
from src.core.signals import signals
from src.resources.icons import Icons
from src.utils.config_manager import ConfigManager
from src.utils.theme_manager import ThemeManager
class Settings(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.call_button = QPushButton()
        self.call_button.setIcon(Icons.settings())
        self.call_button.setToolTip("Settings")
        self.call_button.setIconSize(QSize(30, 30))
        self.call_button.setFixedSize(QSize(30, 30))
        signals.theme_changed.connect(self._refresh_icon)

        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 500)
        self.main_layout = QVBoxLayout(self)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.settings_content = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_content)
        self.scroll_area.setWidget(self.settings_content)
        self.main_layout.addWidget(self.scroll_area)

        self.appearance_label = SettingsSection("Appearance")
        self.settings_layout.addWidget(self.appearance_label)

        self.theme_label = QLabel("Theme")
        self.theme_frame = QFrame()
        self.theme_frame_layout = QHBoxLayout(self.theme_frame)
        self.settings_layout.addWidget(self.theme_label)
        self.settings_layout.addWidget(self.theme_frame)
        
        self.theme_light_button = QPushButton("Light")
        self.theme_light_button.clicked.connect(lambda: self.apply_theme("light"))
        self.theme_dark_button = QPushButton("Dark")
        self.theme_dark_button.clicked.connect(lambda: self.apply_theme("dark"))
        self.theme_frame_layout.addWidget(self.theme_light_button)
        self.theme_frame_layout.addWidget(self.theme_dark_button)

        self.editor_label = SettingsSection("Editor")
        self.editor_frame = QFrame()
        self.editor_frame_layout = QVBoxLayout(self.editor_frame)
        self.settings_layout.addWidget(self.editor_label)
        self.settings_layout.addWidget(self.editor_frame)
        
        self.auto_save_checkbox = QCheckBox("Automatically save files")
        self.auto_save_checkbox.setChecked(bool(ConfigManager.get("auto_save")))
        self.auto_save_checkbox.toggled.connect(self.set_auto_save)
        self.editor_frame_layout.addWidget(self.auto_save_checkbox)

        self.chat_label = SettingsSection("AI-Chat")
        self.chat_frame = QFrame()
        self.chat_frame_layout = QVBoxLayout(self.chat_frame)
        self.settings_layout.addWidget(self.chat_label)
        self.settings_layout.addWidget(self.chat_frame)

        self.startup_message_count = CountChangeSection(
            "Messages loaded on startup",
            "startup_message_count",
            ConfigManager.get("startup_message_count"),
            signals.startup_message_count_updated,
        )
        self.chat_frame_layout.addWidget(self.startup_message_count)

        self.max_context_messages = CountChangeSection("Max context messages", "message_context_count", ConfigManager.get("message_context_count"), signals.message_context_count_updated)
        self.chat_frame_layout.addWidget(self.max_context_messages)

        self.settings_layout.addStretch()

    def apply_theme(self, theme: str) -> None:
        qss = ThemeManager.build_qss(theme)
        app = QApplication.instance()
        app.setStyleSheet(qss)
        ConfigManager.set("theme", theme)
        signals.theme_changed.emit(theme)

    def _refresh_icon(self, _theme: str) -> None:
        self.call_button.setIcon(Icons.settings())

    def set_auto_save(self, enabled: bool) -> None:
        ConfigManager.set("auto_save", enabled)
        signals.auto_save_changed.emit(enabled)

class CountChangeSection(QWidget):
    def __init__(self, text: str, config_name: str, initial_count: int, signal: Signal, parent=None):
        super().__init__(parent)
        self._text = text
        self._config_name = config_name
        self._initial_count = initial_count
        self._signal = signal

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 4, 0, 0)
        self.main_layout.setSpacing(8)

        self._label = QLabel(text)
        self.main_layout.addWidget(self._label, 1)

        self._line_edit = QLineEdit(str(initial_count))
        self._line_edit.setFixedWidth(50)

        self.main_layout.addWidget(self._line_edit, 0)

        self._apply_button = QPushButton("Apply")
        self._apply_button.clicked.connect(self.emit_change)
        self.main_layout.addWidget(self._apply_button, 0)

    def emit_change(self):
        try:
            new_count = int(self._line_edit.text())
            if new_count < 1:
                raise ValueError("Count must be greater than zero")
            self._signal.emit(new_count)
            ConfigManager.set(self._config_name, new_count)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            self._line_edit.setText(str(self._initial_count))
    
class SettingsSection(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(28)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 4, 0, 0)
        self.main_layout.setSpacing(8)

        self._accent = QFrame()
        self._accent.setFixedSize(3, 16)
        self.main_layout.addWidget(self._accent, 0)

        self._label = QLabel(text)
        self.main_layout.addWidget(self._label, 1)

        self._line = QFrame()
        self._line.setFrameShape(QFrame.Shape.HLine)
        self._line.setFixedHeight(1)
        self.main_layout.addWidget(self._line, 6)