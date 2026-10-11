from PySide6.QtWidgets import (QWidget, QDialogButtonBox, QFrame, QFormLayout, 
                               QPushButton, QLabel, QTextEdit, QComboBox, QScrollArea,
                               QVBoxLayout, QHBoxLayout, QDialog, QMessageBox, QLineEdit)
from PySide6.QtCore import QSize, QThread, Qt, QTimer, QEvent, QUrl
from src.utils.config_manager import ConfigManager
from src.resources.icons import Icons
from src.core.ai_worker import AiWorker, DEFAULT_SYSTEM_PROMPT
from src.core.crypto_manager import decrypt, encrypt
from src.core.signals import signals

from datetime import datetime


class ChatBot(QFrame):
    def __init__(self):
        super().__init__()
        self._changing_model = False
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
        self.delete_model_btn.setFixedSize(QSize(30, 30))
        self.sender_bottom_layout.addWidget(self.delete_model_btn)
        self.delete_model_btn.clicked.connect(self._delete_model)

        self.models_combo_box.activated.connect(self.on_selection_changed)
        self.main_layout.addWidget(self.messages_box)
        self.main_layout.addWidget(self.chat_sender)

    def init_ai_connect(self):
        """Initialize connection with AI and puts it in QThread"""
        last_model = ConfigManager.get("last_model")
        self._display_name = last_model.get("display_name")
        print(f"last model: {self._display_name}")
        self._model = last_model.get("model")
        self._provider = last_model.get("provider")
        self._base_url = last_model.get("base_url")
        self.models_list = ConfigManager.get("models")
        api = None
        for model in self.models_list:
            if model.get("display_name") == self._display_name:
                api = model.get("api", None)
        
        self.worker = AiWorker(model=self._model, provider=self._provider, base_url=self._base_url)

        self.ai_thread = QThread()
        self.worker.moveToThread(self.ai_thread)
        
        self.ai_thread.start()

    def _delete_model(self):
        if self.models_combo_box.currentIndex() != self.models_combo_box.findData("add_model"):
            self.models_list = [m for m in self.models_list if m.get("display_name") != self._display_name]
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
                ConfigManager.set("last_model", {"display_name": "", "model": "", "provider": "", "base_url": "", "api": ""})
                if hasattr(self, 'worker'):
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
        self._recreate_worker(data)

    def _recreate_worker(self, model_data):
        """Recreate AI worker with new model configuration"""
        if hasattr(self, 'worker'):
            self.worker.deleteLater()
        self.worker = AiWorker(model=self._model, provider=self._provider, base_url=self._base_url)
        self.worker.moveToThread(self.ai_thread)

    def ready_for_sent(self) -> bool:
        return self._provider and self._base_url and self._model
    
    def send_request(self):
        """Sends request to the LLM: locally (Ollama) or cloud (with API and Provider)"""
        prompt = self.chat_input.toPlainText()
        if not prompt:
            return
        self.chat_input.clear()
        
        api = None
        for model in self.models_list:
            if model.get("display_name") == self._display_name:
                api = model.get("api")
        decrypted_key = decrypt(api) if api else ""
        
        if self.ready_for_sent():
            # Add user message first
            self.messages_box.add_message(prompt, author="user")
            # Add AI message placeholder
            self.last_ai_message = self.messages_box.add_message(text="", author="ai")
            
            # Connect worker signals for this request
            self.worker.text_chunk_received.connect(self.last_ai_message.add_chunk)
            self.worker.generation_ended.connect(self._on_generation_ended)
            self.worker.error_occurred.connect(self._on_worker_error)
            
            # Emit signal to run request in worker thread
            self.worker.do_request.emit(
                self._provider,
                self._base_url,
                self._model,
                decrypted_key,
                prompt,
                DEFAULT_SYSTEM_PROMPT,
                []
            )
        else:
            QMessageBox.warning(self, "Request not ready", "Model data incorrect/corrupted")
    
    def _on_generation_ended(self):
        """Clean up signal connections when generation ends"""
        if self.last_ai_message:
            self.last_ai_message.finish_streaming()
        try:
            self.worker.text_chunk_received.disconnect(self.last_ai_message.add_chunk)
            self.worker.generation_ended.disconnect(self._on_generation_ended)
            self.worker.error_occurred.disconnect(self._on_worker_error)
        except:
            pass
    
    def _on_worker_error(self, error: str):
        """Handle worker error"""
        self._on_generation_ended()
        if self.last_ai_message:
            current = self.last_ai_message.label.text()
            self.last_ai_message.label.setText(current + f"\n\n[Error: {error}]")

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

    def add_message(self, text, author) -> "Message | None":
        message = Message(text, author)
        self.layout.insertWidget(self.layout.count() - 1, message)  # before stretch
        self._scroll_to_bottom()
        if author == "ai":
            return message
    
    def _scroll_to_bottom(self):
        """Scroll to bottom after adding message"""
        QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        ))


class Message(QFrame):
    def __init__(self, text, author):
        super().__init__()
        self.author = author
        self._streaming = author == "ai" and text == ""
        time = datetime.now().strftime("%H:%M")

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
        current = self.label.text()
        # Remove existing cursor if present
        if current.endswith("▌"):
            current = current[:-1]
        # Add cursor if visible
        if self._cursor_visible:
            current += "▌"
        self.label.setText(current)
        self._cursor_visible = not self._cursor_visible

    def add_chunk(self, chunk):
        """Append chunk to message text - runs in main thread via Qt queued connection"""
        current = self.label.text()
        # Remove cursor if present
        if current.endswith("▌"):
            current = current[:-1]
        self.label.setText(current + chunk)

    def finish_streaming(self):
        """Called when streaming ends - remove cursor"""
        if self._streaming:
            self._streaming = False
            if hasattr(self, '_cursor_timer'):
                self._cursor_timer.stop()
            # Remove cursor if present
            current = self.label.text()
            if current.endswith("▌"):
                self.label.setText(current[:-1])


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