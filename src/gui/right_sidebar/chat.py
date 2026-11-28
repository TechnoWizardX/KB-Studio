from PySide6.QtWidgets import (QWidget, QDialogButtonBox, QFrame, QFormLayout, QSizePolicy,
                               QPushButton, QLabel, QTextEdit, QComboBox, QScrollArea,
                               QVBoxLayout, QHBoxLayout, QDialog, QMessageBox, QLineEdit, QFileDialog)
from PySide6.QtCore import QThread, Qt, QTimer, QEvent, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from src.gui.widgets import IconButton
from src.utils.config_manager import ConfigManager
from src.resources.icons import Icons
from src.core.ai_worker import AiWorker, DEFAULT_SYSTEM_PROMPT
from src.core.crypto_manager import decrypt, encrypt
from src.core.signals import signals
from src.utils.history_manager import HistoryManager

from datetime import datetime
from pathlib import Path
import sqlite3


class ChatBot(QFrame):
    def __init__(self):
        super().__init__()
        self.message_context_count = ConfigManager.get("message_context_count")
        self.startup_message_count = ConfigManager.get("startup_message_count")
        self._context_files = []
        self._changing_model = False
        self.history_manager = None
        self._active_ai_message = None
        self.init_ai_connect()

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setLayout(self.main_layout)
        self.setObjectName("chatBot")

        self.header = QFrame()
        self.header.setObjectName("chatHeader")
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(10, 6, 6, 6)
        self.header_layout.setSpacing(6)
        self.header_title = QLabel("AI Assistant")
        self.header_title.setObjectName("chatHeaderTitle")
        self.header_layout.addWidget(self.header_title)
        self.header_layout.addStretch()
        self.clear_history_btn = IconButton(
            Icons.delete(), "Clear chat history", size=28, icon_size=18
        )
        self.clear_history_btn.clicked.connect(self._clear_history)
        self.header_layout.addWidget(self.clear_history_btn)
        self.main_layout.addWidget(self.header)

        self.messages_box = MessagesBox()

        # Send chat box
        self.chat_sender = QFrame()
        self.chat_sender.setObjectName("chatSender")
        self.chat_sender_layout = QVBoxLayout()
        self.chat_sender_layout.setContentsMargins(8, 8, 8, 6)
        self.chat_sender_layout.setSpacing(6)
        self.chat_sender.setLayout(self.chat_sender_layout)

        # Input message
        self.chat_input = QTextEdit()
        self.chat_input.setObjectName("chatBotInput")
        self.chat_input.installEventFilter(self)
        self.chat_input.setPlaceholderText("Ask AI…")
        self.chat_input.setToolTip(
            "Enter sends the message; Shift+Enter inserts a new line"
        )
        self.chat_input.setAcceptRichText(False)
        self.chat_input.setFixedHeight(56)
        self.chat_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.chat_input.textChanged.connect(self._resize_input)
        self.chat_sender_layout.addWidget(self.chat_input)

        self.sender_bottom_layout = QHBoxLayout()
        self.sender_bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.sender_bottom_layout.setSpacing(6)
        self.chat_sender_layout.addLayout(self.sender_bottom_layout)

        self.add_file_to_context_menu = IconButton(
            Icons.file_add(), "Add files to the prompt context"
        )
        self.add_file_to_context_menu.clicked.connect(self._add_file_to_prompt)
        self.sender_bottom_layout.addWidget(self.add_file_to_context_menu)

        self.models_combo_box = QComboBox()
        self.models_combo_box.setPlaceholderText("Select model…")
        self.models_combo_box.setToolTip("Model used for AI requests")
        self.sender_bottom_layout.addWidget(self.models_combo_box, 1)

        self.delete_model_btn = IconButton(
            Icons.cross(), "Delete the selected model"
        )
        self.sender_bottom_layout.addWidget(self.delete_model_btn)
        self.delete_model_btn.clicked.connect(self._delete_model)

        self.send_btn = IconButton(Icons.send())
        self.sender_bottom_layout.addWidget(self.send_btn)
        self.send_btn.clicked.connect(self._send_or_cancel_request)

        self.models_combo_box.activated.connect(self.on_selection_changed)

        self.files_list = FileBox()
        self.files_list.file_removed.connect(self._remove_context_file)
        self.files_list.hide()
        self.chat_sender_layout.insertWidget(1, self.files_list)

        self.shortcut_hint = QLabel("Enter to send · Shift+Enter for a new line")
        self.shortcut_hint.setObjectName("chatShortcutHint")
        self.shortcut_hint.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.chat_sender_layout.addWidget(self.shortcut_hint)

        self.main_layout.addWidget(self.messages_box, 1)
        self.main_layout.addWidget(self.chat_sender, 0)

        self.load_models_to_list()

        signals.theme_changed.connect(self._refresh_icons)
        signals.message_context_count_updated.connect(self._message_context_count_updated)
        signals.startup_message_count_updated.connect(self._startup_message_count_updated)
        signals.add_file_to_context.connect(self.add_context_file)

        try:
            self.history_manager = HistoryManager()
            for saved_message in self.history_manager.get_messages(
                limit=self.startup_message_count
            ):
                author = "ai" if saved_message["role"] == "assistant" else "user"
                self.messages_box.add_message(
                    saved_message["content"],
                    author,
                    saved_message["created_at"],
                )
        except (OSError, sqlite3.Error) as error:
            QMessageBox.critical(
                self,
                "Chat history unavailable",
                f"Could not open the chat history database:\n{error}",
            )
        self._update_send_button()

    def _resize_input(self) -> None:
        """Grow the input with its content, up to the maximum height."""
        document_height = self.chat_input.document().size().height()
        frame = self.chat_input.frameWidth() * 2
        height = int(document_height) + frame + 12
        height = max(56, min(160, height))
        if height != self.chat_input.height():
            self.chat_input.setFixedHeight(height)

    def _refresh_icons(self, _theme: str) -> None:
        self._update_send_button()
        self.delete_model_btn.setIcon(Icons.cross())
        self.clear_history_btn.setIcon(Icons.delete())
        self.add_file_to_context_menu.setIcon(Icons.file_add())

    def _update_send_button(self):
        is_generating = self._active_ai_message is not None
        self.send_btn.setIcon(Icons.cross() if is_generating else Icons.send())
        self._update_action_states()

    def _update_action_states(self) -> None:
        """Enable actions only when they can do something useful."""
        is_generating = self._active_ai_message is not None
        has_history = self.history_manager is not None
        can_send = has_history and (is_generating or self.ready_for_sent())
        self.send_btn.setEnabled(can_send)
        if is_generating:
            self.send_btn.setToolTip("Cancel request")
        elif not has_history:
            self.send_btn.setToolTip("Chat history is unavailable")
        elif self.ready_for_sent():
            self.send_btn.setToolTip("Send request (Enter)")
        else:
            self.send_btn.setToolTip("Select a model before sending")

        current_index = self.models_combo_box.currentIndex()
        has_model = (
            current_index >= 0
            and self.models_combo_box.itemData(current_index) != "add_model"
        )
        self.delete_model_btn.setEnabled(has_model)
        self.clear_history_btn.setEnabled(has_history and not is_generating)

    def _send_or_cancel_request(self):
        if self._active_ai_message is not None:
            self.send_btn.setEnabled(False)
            self.send_btn.setToolTip("Cancelling request…")
            try:
                self.worker.cancel_request()
            except Exception as error:
                self._update_action_states()
                QMessageBox.warning(
                    self,
                    "Cancellation failed",
                    f"Could not cancel the AI request:\n{error}",
                )
            return
        self.send_request()

    def _message_context_count_updated(self, new_count: int):
        """Update the message context count and save it to the config."""
        self.message_context_count = new_count

    def _startup_message_count_updated(self, new_count: int):
        self.startup_message_count = new_count

    def _clear_history(self):
        if self._active_ai_message is not None:
            QMessageBox.information(
                self,
                "Chat is busy",
                "Wait for the current response to finish before clearing history.",
            )
            return
        if self.history_manager is None:
            return

        reply = QMessageBox.question(
            self,
            "Clear chat history",
            "Delete all saved messages? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.history_manager.clear()
        except (OSError, sqlite3.Error) as error:
            QMessageBox.critical(
                self,
                "Chat history error",
                f"Could not clear chat history:\n{error}",
            )
            return
        self.messages_box.clear_messages()
        self._update_action_states()
        signals.status_message.emit("Chat history cleared")

    def add_context_file(self, file_path: str) -> None:
        """Attach *file_path* to the prompt context and show it in the list."""
        if not file_path:
            return
        resolved = str(Path(file_path).resolve())
        if resolved in self._context_files:
            return
        self._context_files.append(resolved)
        self.files_list.add_file(resolved)
        self.files_list.show()

    def _add_file_to_prompt(self):
        """Open a file dialog to select files and add them to the context for the AI prompt."""
        file_dialog = QFileDialog(self, "Select files to add to prompt")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if not file_dialog.exec():
            return
        for file_path in file_dialog.selectedFiles():
            self.add_context_file(file_path)

    def _remove_context_file(self, file_path: str):
        self._context_files = [
            path for path in self._context_files if path != file_path
        ]
        if not self._context_files:
            self.files_list.hide()

    def _load_context_files(self):
        """Rebuild the visual list of files attached to the prompt."""
        self.files_list.clear_files()
        for file_path in self._context_files:
            self.files_list.add_file(file_path)
        self.files_list.setVisible(bool(self._context_files))

    def init_ai_connect(self):
        """Initialize connection with AI and puts it in QThread"""
        last_model = ConfigManager.get("last_model")
        self._display_name = last_model.get("display_name")
        self._model = last_model.get("model")
        self._provider = last_model.get("provider")
        self._base_url = last_model.get("base_url")
        self.models_list = ConfigManager.get("models")
        
        self.ai_thread = QThread(self)
        self.worker = self._create_worker()
        self.ai_thread.start()

    def _create_worker(self) -> AiWorker:
        worker = AiWorker(
            model=self._model,
            provider=self._provider,
            base_url=self._base_url,
        )
        worker.moveToThread(self.ai_thread)
        self.ai_thread.finished.connect(worker.deleteLater)
        return worker

    def shutdown(self) -> bool:
        if self._active_ai_message is not None:
            return False
        if not self.ai_thread.isRunning():
            return True

        self.ai_thread.quit()
        return self.ai_thread.wait(5000)

    def _delete_model(self):
        """Delete the currently selected model from the list and config."""
        current_index = self.models_combo_box.currentIndex()
        if current_index < 0:
            return
        if self.models_combo_box.itemData(current_index) == "add_model":
            return

        reply = QMessageBox.question(
            self,
            "Delete model",
            f"Are you sure you want to delete the model '{self._display_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.models_list = [
            model for model in self.models_list
            if model.get("display_name") != self._display_name
        ]
        ConfigManager.set("models", self.models_list)

        if self.models_list:
            self._changing_model = True
            self.models_combo_box.setCurrentIndex(0)
            self._changing_model = False
            self.on_selection_changed(0)
        else:
            self._display_name = ""
            self._model = ""
            self._provider = ""
            self._base_url = ""
            ConfigManager.set(
                "last_model",
                {"display_name": "", "model": "", "provider": "", "base_url": "", "api": ""},
            )
            if hasattr(self, "worker"):
                self.worker.deleteLater()
            self.worker = self._create_worker()

        self._changing_model = True
        self.models_combo_box.clear()
        self.load_models_to_list()
        self._changing_model = False
        self._update_action_states()

    def load_models_to_list(self):
        """Load configured models and keep an explicit "add" entry.

        Empty placeholder records (the default config ships one) are skipped
        so the selector never shows a blank current model. With no usable
        model the combo shows its placeholder text instead.
        """
        self.models_combo_box.clear()
        valid_models = [
            model
            for model in (self.models_list or [])
            if isinstance(model, dict)
            and str(model.get("display_name", "")).strip()
        ]
        for model_data in valid_models:
            data = model_data.copy()
            data.pop("api", None)
            self.models_combo_box.addItem(
                str(model_data.get("display_name", "")).strip(),
                userData=data,
            )
        self.models_combo_box.addItem("Add a model…", userData="add_model")

        last_index = self.models_combo_box.findText(self._display_name or "")
        if last_index >= 0 and self.models_combo_box.itemData(last_index) != "add_model":
            self.models_combo_box.setCurrentIndex(last_index)
        else:
            self.models_combo_box.setCurrentIndex(-1)
        self._update_action_states()

    def on_selection_changed(self, index: int):
        """Emits when model in combobox of models changed"""
        if self._changing_model:
            return
            
        if index == self.models_combo_box.findData("add_model"):
            model_data = AddModelDialog.get_model_data_from_user(self)

            if model_data is None:  
                last_index = self.models_combo_box.findText(self._display_name)
                self._changing_model = True
                self.models_combo_box.setCurrentIndex(last_index)
                self._changing_model = False
                self._update_action_states()
                return
        
            if model_data["api"]:
                model_data["api"] = encrypt(model_data["api"])

            self.models_list.append(model_data)
            ConfigManager.set("models", self.models_list)   

            self._changing_model = True
            self.models_combo_box.clear()
            self.load_models_to_list()    

            new_index = self.models_combo_box.findText(model_data["display_name"])
            self.models_combo_box.setCurrentIndex(new_index)
            self._changing_model = False
            self.on_selection_changed(new_index)
            return

        data = self.models_combo_box.itemData(index)
        if data is None or data.get("display_name") == self._display_name:
            self._update_action_states()
            return
        
        self._display_name = data.get("display_name")
        self._model = data.get("model")
        self._provider = data.get("provider")
        self._base_url = data.get("base_url")
        ConfigManager.set("last_model", data)
        self._recreate_worker()
        self._update_action_states()

    def _recreate_worker(self):
        """Recreate AI worker with new model configuration"""
        if hasattr(self, 'worker'):
            self.worker.deleteLater()
        self.worker = self._create_worker()

    def ready_for_sent(self) -> bool:
        return bool(self._provider and self._base_url and self._model)
    
    def send_request(self):
        """Sends request to the LLM: locally (Ollama) or cloud (with API and Provider)"""
        if self._active_ai_message is not None:
            return
        prompt = self.chat_input.toPlainText().strip()
        context_files = list(self._context_files)
        if not prompt and not context_files:
            return
        if not prompt:
            prompt = "Please review the attached files."
        if prompt == "/clear-history":
            self._clear_history()
            self.chat_input.clear()
            return

        if not self.ready_for_sent():
            QMessageBox.warning(
                self,
                "Incomplete model",
                "The selected model is missing required details. "
                "Remove it and add it again.",
            )
            return
        if self.history_manager is None:
            QMessageBox.critical(
                self,
                "Chat history unavailable",
                "Chat history is unavailable.",
            )
            return

        try:
            conversation_history = self.history_manager.get_messages(limit=self.message_context_count)
            self.history_manager.add_message("user", prompt)
        except (OSError, sqlite3.Error) as error:
            QMessageBox.critical(
                self,
                "Chat history error",
                f"Could not save the message:\n{error}",
            )
            return

        self.chat_input.clear()

        api = None
        for model in self.models_list:
            if model.get("display_name") == self._display_name:
                api = model.get("api")
        decrypted_key = decrypt(api) if api else ""

        self.messages_box.add_message(prompt, author="user")
        self._active_ai_message = self.messages_box.add_message(text="", author="ai")
        self._update_send_button()

        self.worker.text_chunk_received.connect(self._active_ai_message.add_chunk)
        self.worker.generation_ended.connect(self._on_generation_ended)
        self.worker.error_occurred.connect(self._on_worker_error)

        self.worker.prepare_request()
        self.worker.do_request.emit(
            self._provider,
            self._base_url,
            self._model,
            decrypted_key,
            prompt,
            DEFAULT_SYSTEM_PROMPT,
            context_files,
            [
                {"role": message["role"], "content": message["content"]}
                for message in conversation_history
            ],
        )
    
    def _on_generation_ended(self):
        """Persist the completed answer and clean up its signal connections."""
        message = self._active_ai_message
        self._finish_generation()
        if message is None or self.history_manager is None or not message.content:
            return
        try:
            self.history_manager.add_message("assistant", message.content)
        except (OSError, sqlite3.Error) as error:
            QMessageBox.critical(
                self,
                "Chat history error",
                f"Could not save the AI response:\n{error}",
            )

    def _finish_generation(self):
        message = self._active_ai_message
        if message is None:
            return
        message.finish_streaming()
        try:
            self.worker.text_chunk_received.disconnect(message.add_chunk)
            self.worker.generation_ended.disconnect(self._on_generation_ended)
            self.worker.error_occurred.disconnect(self._on_worker_error)
        except (RuntimeError, TypeError):
            pass
        self._active_ai_message = None
        self._update_send_button()
    
    def _on_worker_error(self, error: str):
        """Handle worker error"""
        message = self._active_ai_message
        self._finish_generation()
        if message:
            message.label.setText(f"{message.content}\n\n[Error: {error}]")

    def eventFilter(self, obj, event):
        if obj is self.chat_input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False  
                else:
                    self.send_request()  
                    return True  
        return super().eventFilter(obj, event)
    
        

    
class EmptyState(QWidget):
    """Placeholder shown while the chat has no messages."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(6)
        layout.addStretch()

        title = QLabel("Start a conversation")
        title.setObjectName("chatEmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)

        text = QLabel("Ask about your code or attach files with the + button.")
        text.setObjectName("chatEmptyText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch()


class MessagesBox(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setObjectName("messagesBox")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.container.setObjectName("messagesContainer")
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)
        self._empty_state = EmptyState()
        self.main_layout.addWidget(self._empty_state, 1)
        self.main_layout.addStretch(3)
        self.setWidget(self.container)
        self.setWidgetResizable(True)

        self._auto_scroll = True
        scroll_bar = self.verticalScrollBar()
        scroll_bar.valueChanged.connect(self._on_scrolled)
        scroll_bar.rangeChanged.connect(self._on_range_changed)

    def add_message(self, text, author, created_at=None) -> "Message | None":
        self._empty_state.hide()
        message = Message(text, author, created_at)
        alignment = Qt.AlignmentFlag.AlignLeft if author == "ai" else Qt.AlignmentFlag.AlignRight
        self.main_layout.insertWidget(self.main_layout.count() - 1, message, alignment)  # before stretch
        message.content_changed.connect(self._on_message_grew)
        self._auto_scroll = True
        self._scroll_to_bottom()
        if author == "ai":
            return message

    def clear_messages(self) -> None:
        for index in reversed(range(self.main_layout.count())):
            item = self.main_layout.itemAt(index)
            widget = item.widget()
            if widget is not None and widget is not self._empty_state:
                self.main_layout.takeAt(index)
                widget.deleteLater()
        self._empty_state.show()
        self._auto_scroll = True
        self.verticalScrollBar().setValue(0)

    def _on_scrolled(self, value: int) -> None:
        """Stop following the stream once the user scrolls up."""
        bar = self.verticalScrollBar()
        self._auto_scroll = value >= bar.maximum() - 24

    def _on_range_changed(self, _minimum: int, maximum: int) -> None:
        if self._auto_scroll:
            self.verticalScrollBar().setValue(maximum)

    def _on_message_grew(self) -> None:
        if self._auto_scroll:
            self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """Scroll to bottom after the layout has been updated."""
        QTimer.singleShot(0, self._scroll_now)

    def _scroll_now(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

class FileBox(QScrollArea):
    file_removed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("contextFilesList")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMaximumHeight(100)
        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)
        self._files: dict[str, ContextFile] = {}
        self.main_layout.addStretch()
        self.setWidget(self.container)
        self.setWidgetResizable(True)

    def add_file(self, path: str) -> None:
        if path in self._files:
            return
        context_file = ContextFile(path)
        context_file.remove_requested.connect(self._remove_file)
        self._files[path] = context_file
        self.main_layout.insertWidget(self.main_layout.count() - 1, context_file)

    def clear_files(self) -> None:
        for path in tuple(self._files):
            self._remove_file(path, notify=False)

    def _remove_file(self, path: str, notify: bool = True) -> None:
        context_file = self._files.pop(path, None)
        if context_file is None:
            return
        self.main_layout.removeWidget(context_file)
        context_file.deleteLater()
        if notify:
            self.file_removed.emit(path)


class ContextFile(QFrame):
    remove_requested = Signal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.setObjectName("contextFileRow")
        self.setMaximumHeight(32)
        self.file_path = file_path
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(8, 2, 4, 2)
        self.label = QLabel(Path(file_path).name)
        self.label.setObjectName("contextFileName")
        self.label.setToolTip(Path(file_path).name)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.remove_btn = QPushButton("×")
        self.remove_btn.setObjectName("contextFileRemove")
        self.remove_btn.setToolTip("Remove file from context")
        self.remove_btn.setFixedSize(24, 24)
        self.remove_btn.clicked.connect(
            lambda: self.remove_requested.emit(self.file_path)
        )
        self.main_layout.addWidget(self.label)
        self.main_layout.addWidget(self.remove_btn)

class Message(QFrame):
    content_changed = Signal()

    def __init__(self, text, author, created_at=None):
        super().__init__()
        
        self.author = author
        self.content = text
        self._streaming = author == "ai" and text == ""
        message_time = datetime.fromisoformat(created_at) if created_at else datetime.now()
        time = message_time.astimezone().strftime("%H:%M")

        self.setObjectName("messageUser" if author == "user" else "messageAi")
        self.setMaximumWidth(380)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 6)
        self.main_layout.setSpacing(2)

        self.label = QLabel(text)
        self.label.setObjectName("messageText")
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.label.setTextFormat(Qt.TextFormat.MarkdownText)
        self.label.setOpenExternalLinks(False)
        self.label.linkActivated.connect(self._open_link)
        self.main_layout.addWidget(self.label)

        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(4)
        self.role = QLabel("You" if author == "user" else "AI")
        self.role.setObjectName("messageRole")
        self.date = QLabel(time)
        self.date.setObjectName("messageDate")
        meta_layout.addWidget(self.role)
        meta_layout.addStretch()
        meta_layout.addWidget(self.date)
        self.main_layout.addLayout(meta_layout)

        # Typing cursor for AI messages
        if self._streaming:
            self._cursor_timer = QTimer(self)
            self._cursor_timer.timeout.connect(self._toggle_cursor)
            self._cursor_visible = True
            self._cursor_timer.start(500)  # Blink every 500ms

    def _open_link(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def _toggle_cursor(self):
        """Toggle typing cursor visibility"""
        if not self._streaming:
            return
        self.label.setText(self.content + ("▌" if self._cursor_visible else ""))
        self._cursor_visible = not self._cursor_visible

    def add_chunk(self, chunk):
        """Append chunk to message text - runs in main thread via Qt queued connection"""
        self.content += chunk
        self.label.setText(self.content + ("▌" if self._streaming and self._cursor_visible else ""))
        self.content_changed.emit()

    def finish_streaming(self):
        """Called when streaming ends - remove cursor"""
        if self._streaming:
            self._streaming = False
            if hasattr(self, '_cursor_timer'):
                self._cursor_timer.stop()
            # Remove cursor if present
            self.label.setText(self.content)


class AddModelDialog(QDialog):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Add new model")
        self.setMinimumWidth(400)
        self.setModal(True)

        self.main_layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        info_label = QLabel("Enter the model connection details.")
        info_label.setWordWrap(True)
        self.main_layout.addWidget(info_label)

        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText(
            "e.g., GPT-6 Astra, Claude Opus 4.6"
        )
        self.display_name_edit.setToolTip(
            "Name shown in the model list. It does not have to match the model ID."
        )
        self.form_layout.addRow("Display name *", self.display_name_edit)
        
        self.provider_edit = QLineEdit()
        self.provider_edit.setPlaceholderText(
            "e.g., anthropic, openai, openrouter; use ollama for a local model"
        )
        self.provider_edit.setToolTip(
            "Provider used for API requests. Use “ollama” for a local model."
        )
        self.form_layout.addRow("API provider *", self.provider_edit)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText(
            "e.g., gpt-4, claude-sonnet-5.5, liquid/lfm-2.5-2.6b:free"
        )
        self.model_edit.setToolTip("Exact model name sent to the provider.")
        self.form_layout.addRow("Model name *", self.model_edit)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText(
            "e.g., https://api.openai.com/v1 or http://localhost:11434/v1 for ollama"
        )
        self.base_url_edit.setToolTip(
            "API endpoint, including the version path. For Ollama, use "
            "http://localhost:11434/v1."
        )
        self.form_layout.addRow("Base URL *", self.base_url_edit)
        
        self.api_edit = QLineEdit()
        self.api_edit.setPlaceholderText("e.g., sk-... Leave empty if you use ollama")
        self.api_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_edit.setToolTip(
            "Stored encrypted on this computer. Leave empty for Ollama."
        )
        self.form_layout.addRow("API key", self.api_edit)

        self.main_layout.addLayout(self.form_layout)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.main_layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)

        self.required_note = QLabel("* Required fields")
        self.required_note.setStyleSheet("color: gray; font-size: 11px;")
        self.main_layout.addWidget(self.required_note)

    def _validate_and_accept(self):
        errors = []
        if not self.display_name_edit.text().strip():
            errors.append("Display Name is required")
        if not self.provider_edit.text().strip():
            errors.append("Provider is required")
        if not self.model_edit.text().strip():
            errors.append("Model ID is required")
        
        # Base URL validation using QUrl
        base_url = self.base_url_edit.text().strip()
        if not base_url:
            errors.append("Base URL is required")
        else:
            qurl = QUrl(base_url)
            if not qurl.isValid():
                errors.append(f"Invalid URL: {qurl.errorString()}")
            elif qurl.scheme().lower() not in ("http", "https"):
                errors.append("Base URL must use http:// or https://")
            elif not qurl.host():
                errors.append("Base URL must have a host")
        
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
        
        self.accept()

    def get_model_data(self) -> dict:
        return {
            "display_name": self.display_name_edit.text().strip(),
            "provider": self.provider_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "base_url": self.base_url_edit.text().strip(),
            "api": self.api_edit.text().strip(),
        }
    
    @staticmethod
    def get_model_data_from_user(parent=None) -> dict | None:
        dialog = AddModelDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_model_data()
        return None