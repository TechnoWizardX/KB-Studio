from PySide6.QtWidgets import (QWidget, QDialogButtonBox, QFrame, QFormLayout,
                               QPushButton, QLabel, QTextEdit, QComboBox, QScrollArea,
                               QVBoxLayout, QHBoxLayout, QDialog, QMessageBox, QLineEdit, QFileDialog)
from PySide6.QtCore import QSize, QThread, Qt, QTimer, QEvent, QUrl, Signal
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
        self.showed_messages_limit = ConfigManager.get("showed_messages_limit")
        self._context_files = []
        self._changing_model = False
        self.history_manager = None
        self._active_ai_message = None
        self.init_ai_connect()

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)
        self.messages_box = MessagesBox()
        
        # Send chat box
        self.chat_sender = QFrame()
        self.chat_sender.setObjectName("chatSender")
        self.chat_sender_layout = QVBoxLayout()
        self.chat_sender_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_sender_layout.setSpacing(0)
        self.chat_sender.setLayout(self.chat_sender_layout)

        # Input message
        self.chat_input = QTextEdit()
        self.chat_input.installEventFilter(self)
        self.chat_input.setPlaceholderText("Ask AI...")
        self.setObjectName("chatBotInput")
        self.chat_sender_layout.addWidget(self.chat_input)

        self.sender_bottom_layout = QHBoxLayout()
        self.chat_sender_layout.addLayout(self.sender_bottom_layout)

        self.send_btn = QPushButton()
        self.send_btn.setObjectName("IconButton")
        self.send_btn.setIcon(Icons.send())
        self.send_btn.setIconSize(QSize(30, 30))
        self.send_btn.setFixedSize(QSize(30, 30))
        self.sender_bottom_layout.addWidget(self.send_btn)
        self.send_btn.clicked.connect(self.send_request)

        self.models_combo_box = QComboBox()
        self.sender_bottom_layout.addWidget(self.models_combo_box)
        self.load_models_to_list()

        self.delete_model_btn = QPushButton()
        self.delete_model_btn.setObjectName("IconButton")
        self.delete_model_btn.setIcon(Icons.cross())
        self.delete_model_btn.setIconSize(QSize(30, 30))
        self.delete_model_btn.setFixedSize(QSize(30, 30))
        self.sender_bottom_layout.addWidget(self.delete_model_btn)
        self.delete_model_btn.clicked.connect(self._delete_model)

        self.models_combo_box.activated.connect(self.on_selection_changed)

        self.add_file_to_context_menu = QPushButton()
        self.add_file_to_context_menu.setObjectName("IconButton")
        self.add_file_to_context_menu.setIcon(Icons.file_add())
        self.add_file_to_context_menu.setIconSize(QSize(30, 30))
        self.add_file_to_context_menu.setFixedSize(QSize(30, 30))
        self.add_file_to_context_menu.setToolTip("Add files to context")
        
        self.sender_bottom_layout.insertWidget(0, self.add_file_to_context_menu)
        self.add_file_to_context_menu.clicked.connect(self._add_file_to_prompt)

        self.files_list = FileBox()
        self.files_list.file_removed.connect(self._remove_context_file)
        self.files_list.hide()
        self.chat_sender_layout.insertWidget(1, self.files_list)

        self.main_layout.addWidget(self.messages_box, 2)
        self.main_layout.addWidget(self.chat_sender, 1)

        signals.message_context_count_updated.connect(self._message_context_count_updated)
        signals.showed_messages_limit_updated.connect(self._showed_messages_limit_updated)

        try:
            self.history_manager = HistoryManager()
            for saved_message in self.history_manager.get_messages(limit=self.showed_messages_limit):
                author = "ai" if saved_message["role"] == "assistant" else "user"
                self.messages_box.add_message(
                    saved_message["content"],
                    author,
                    saved_message["created_at"],
                )
        except (OSError, sqlite3.Error) as error:
            self.send_btn.setEnabled(False)
            QMessageBox.critical(
                self,
                "Chat history unavailable",
                f"Could not open the chat history database:\n{error}",
            )

    def _message_context_count_updated(self, new_count: int):
        """Update the message context count and save it to the config."""
        self.message_context_count = new_count

    def _showed_messages_limit_updated(self, new_limit: int):
        """Update the showed messages limit and save it to the config."""
        self.showed_messages_limit = new_limit

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

    def _add_file_to_prompt(self):
        """Open a file dialog to select files and add them to the context for the AI prompt."""
        file_dialog = QFileDialog(self, "Select files to add to prompt")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            existing_paths = {str(Path(path).resolve()) for path in self._context_files}
            added_files = [
                path for path in selected_files
                if str(Path(path).resolve()) not in existing_paths
            ]
            if not added_files:
                return
            self._context_files.extend(added_files)
            for file_path in added_files:
                self.files_list.add_file(file_path)
            self.files_list.show()

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
        print(f"last model: {self._display_name}")
        self._model = last_model.get("model")
        self._provider = last_model.get("provider")
        self._base_url = last_model.get("base_url")
        self.models_list = ConfigManager.get("models")
        
        self.worker = AiWorker(model=self._model, provider=self._provider, base_url=self._base_url)

        self.ai_thread = QThread()
        self.worker.moveToThread(self.ai_thread)
        
        self.ai_thread.start()

    def _delete_model(self):
        """Delete the currently selected model from the list and config."""
        if self.models_combo_box.currentIndex() == self.models_combo_box.findData("add_model"):
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
            self.worker = AiWorker(model="", provider="", base_url="")
            self.worker.moveToThread(self.ai_thread)

        self._changing_model = True
        self.models_combo_box.clear()
        self.load_models_to_list()
        self._changing_model = False

    def load_models_to_list(self):
        """Loads models info from config, deletes "api" key from userData"""
        if self.models_list:
            for model_data in self.models_list: 
                data = model_data.copy()
                data.pop("api", None)
                self.models_combo_box.addItem(model_data.get("display_name"), userData=data)
            last_index = self.models_combo_box.findText(self._display_name)
            self.models_combo_box.setCurrentIndex(last_index)
        self.models_combo_box.addItem("Add new model...", userData="add_model")

    def on_selection_changed(self, index: int):
        """Emits when model in combobox of models changed"""
        if self._changing_model:
            return
            
        if index == self.models_combo_box.findData("add_model"):
            print("Add model function called")
            model_data = AddModelDialog.get_model_data_from_user(self)

            if model_data is None:  
                last_index = self.models_combo_box.findText(self._display_name)
                self._changing_model = True
                self.models_combo_box.setCurrentIndex(last_index)
                self._changing_model = False
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
            return

        data = self.models_combo_box.itemData(index)
        if data is None or data.get("display_name") == self._display_name:
            return
        
        self._display_name = data.get("display_name")
        self._model = data.get("model")
        self._provider = data.get("provider")
        self._base_url = data.get("base_url")
        ConfigManager.set("last_model", data)
        print("model changed")
        self._recreate_worker()

    def _recreate_worker(self):
        """Recreate AI worker with new model configuration"""
        if hasattr(self, 'worker'):
            self.worker.deleteLater()
        self.worker = AiWorker(model=self._model, provider=self._provider, base_url=self._base_url)
        self.worker.moveToThread(self.ai_thread)

    def ready_for_sent(self) -> bool:
        return self._provider and self._base_url and self._model
    
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
            QMessageBox.warning(self, "Request not ready", "Model data incorrect/corrupted")
            return
        if self.history_manager is None:
            QMessageBox.critical(self, "Chat history unavailable", "Chat history is not available.")
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
        self.send_btn.setEnabled(False)

        self.worker.text_chunk_received.connect(self._active_ai_message.add_chunk)
        self.worker.generation_ended.connect(self._on_generation_ended)
        self.worker.error_occurred.connect(self._on_worker_error)

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
        self.send_btn.setEnabled(True)
    
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
    
        

    
class MessagesBox(QScrollArea):
    def __init__(self):
        super().__init__() 
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.addStretch()
        self.setWidget(self.container)
        self.setWidgetResizable(True)

    def add_message(self, text, author, created_at=None) -> "Message | None":
        message = Message(text, author, created_at)
        self.layout.insertWidget(self.layout.count() - 1, message)  # before stretch
        self._scroll_to_bottom()
        if author == "ai":
            return message

    def clear_messages(self) -> None:
        while self.layout.count() > 1:
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _scroll_to_bottom(self):
        """Scroll to bottom after adding message"""
        QTimer.singleShot(0, lambda: QTimer.singleShot(
            0,
            lambda: self.verticalScrollBar().setValue(
                self.verticalScrollBar().maximum()
            ),
        ))

class FileBox(QScrollArea):
    file_removed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("contextFilesList")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMaximumHeight(100)
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        self._files: dict[str, ContextFile] = {}
        self.layout.addStretch()
        self.setWidget(self.container)
        self.setWidgetResizable(True)

    def add_file(self, path: str) -> None:
        if path in self._files:
            return
        context_file = ContextFile(path)
        context_file.remove_requested.connect(self._remove_file)
        self._files[path] = context_file
        self.layout.insertWidget(self.layout.count() - 1, context_file)

    def clear_files(self) -> None:
        for path in tuple(self._files):
            self._remove_file(path, notify=False)

    def _remove_file(self, path: str, notify: bool = True) -> None:
        context_file = self._files.pop(path, None)
        if context_file is None:
            return
        self.layout.removeWidget(context_file)
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
    def __init__(self, text, author, created_at=None):
        super().__init__()
        self.author = author
        self.content = text
        self._streaming = author == "ai" and text == ""
        message_time = datetime.fromisoformat(created_at) if created_at else datetime.now()
        time = message_time.astimezone().strftime("%H:%M")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.label = QLabel(text)
        self.label.setObjectName("messageText")
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.label.setTextFormat(Qt.TextFormat.MarkdownText)
        self.main_layout.addWidget(self.label)

        self.date = QLabel(time)
        self.date.setObjectName("messageDate")
        self.main_layout.addWidget(self.date)

        # Typing cursor for AI messages
        if self._streaming:
            self._cursor_timer = QTimer(self)
            self._cursor_timer.timeout.connect(self._toggle_cursor)
            self._cursor_visible = True
            self._cursor_timer.start(500)  # Blink every 500ms

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

        info_label = QLabel("Enter model configuration details")
        info_label.setWordWrap(True)
        self.main_layout.addWidget(info_label)

        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("e.g., GPT-6 Astra, Claude Opus 4.6")
        self.form_layout.addRow("Display name *", self.display_name_edit)
        
        self.provider_edit = QLineEdit()
        self.provider_edit.setPlaceholderText("e.g., anthropic, openai, openrouter; enter ollama if you using local model")
        self.form_layout.addRow("API Provider *", self.provider_edit)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("e.g., gpt-4, claude-sonnet-5.5, liquid/lfm-2.5-2.6b:free")
        self.form_layout.addRow("Model name*", self.model_edit)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("e.g., https://api.openai.com/v1 or http://localhost:11434/v1 for ollama")
        self.form_layout.addRow("Base url*", self.base_url_edit)
        
        self.api_edit = QLineEdit()
        self.api_edit.setPlaceholderText("e.g., sk-... Leave empty if you use ollama")
        self.api_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.form_layout.addRow("API Key", self.api_edit)

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