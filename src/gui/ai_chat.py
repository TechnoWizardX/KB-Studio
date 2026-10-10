from PySide6.QtWidgets import (QWidget, QDialogButtonBox, QFrame, QFormLayout, 
                               QPushButton, QLabel, QTextEdit, QComboBox, QScrollArea,
                               QVBoxLayout, QHBoxLayout, QDialog, QMessageBox, QLineEdit)
from PySide6.QtCore import QSize, QThread, Qt
from src.utils.config_manager import ConfigManager
from src.resources.icons import Icons
from src.core.ai_worker import AiWorker
from src.core.crypto_manager import decrypt, encrypt
from src.core.signals import signals

from datetime import datetime

class ChatBot(QFrame):
    def __init__(self):
        super().__init__()
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

        self.models_combo_box.activated.connect(self.on_selection_changed)
        self.main_layout.addWidget(self.messages_box)
        self.main_layout.addWidget(self.chat_sender)

        signals.generation_ended.connect(self.unconnect_message)

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
        
        decrypted_key = decrypt(api) if api else ""
        self.worker = AiWorker(api=decrypted_key, model=self._model, provider=self._provider, base_url=self._base_url)

        self.ai_thread = QThread()
        self.worker.moveToThread(self.ai_thread)
        
        self.ai_thread.start()

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

    def on_selection_changed(self):
        """Emits when model in combobox of models changed"""
        if self.models_combo_box.currentIndex() == self.models_combo_box.findData("add_model"):
            print("Add model function called")
            model_data = AddModelDialog.get_model_data_from_user(self)

            if model_data is None:  
                last_index = self.models_combo_box.findText(self._display_name)
                self.models_combo_box.setCurrentIndex(last_index)
                return
        
            if model_data["api"]:
                model_data["api"] = encrypt(model_data["api"])

            self.models_list.append(model_data)
            ConfigManager.set("models", self.models_list)   

            self.models_combo_box.clear()
            self.load_models_to_list()    

            new_index = self.models_combo_box.findText(model_data["display_name"])
            self.models_combo_box.setCurrentIndex(new_index)

        elif (self.models_combo_box.currentIndex() is not None) and (
                self.models_combo_box.currentIndex() != self.models_combo_box.findText(self._display_name)):   
            data = self.models_combo_box.currentData()
            self._display_name = data.get("display_name")
            self._model = data.get("model")
            self._provider = data.get("provider")
            self._base_url = data.get("base_url")
            ConfigManager.set("last_model", data)
            print("model changed")

    def ready_for_sent(self) -> bool:
        return self._provider and self._base_url and self._model
    
    def send_request(self):
        """Sends request to the LLM: localy (Ollama) or cloudly (with API and Provider)"""
        self.last_ai_message = Message("delete this", "system")
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
            self.worker.send_request(
                                    provider=self._provider,
                                    base_url=self._base_url,
                                    model=self._model,
                                    api=decrypted_key,
                                    prompt = prompt
                                    )
            self.messages_box.add_message(prompt, author = "user")
            self.last_ai_message = self.messages_box.add_message(text = "...", author = "ai")
            signals.text_chunk_recieved.connect(self.last_ai_message.add_chunk)
        else:
            QMessageBox.warning(self, "Request not ready", "Model data incorrect/corrupted")
    
    def unconnect_message(self):
        signals.text_chunk_recieved.disconnect(self.last_ai_message.add_chunk)

class MessagesBox(QScrollArea):
    def __init__(self):
        super().__init__() 
        self.main_layout = QVBoxLayout(self)
        self.current_message = None

    def add_message(self, text, author) -> Message | None:
        message = Message(text, author)
        self.main_layout.addWidget(message)
        if author == "ai":
            return message

class Message(QFrame):
    def __init__(self, text, author):
        super().__init__()
        self.text = text    
        self.author = author
        time = datetime.now().strftime("%H:%M")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.text = QTextEdit(text)
        self.text.setReadOnly(True)
        self.text.setTextInteractionFlags(   
        Qt.TextInteractionFlag.TextSelectableByMouse |
        Qt.TextInteractionFlag.TextSelectableByKeyboard |
        Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.main_layout.addWidget(self.text)

        self.date = QLabel(time)
        self.date.setObjectName("messageDate")
        self.main_layout.addWidget(self.date)

    def add_chunk(self, chunk):
        text = self.text.toPlainText()
        self.text.setPlainText(text + chunk)

class AddModelDialog(QDialog):
    def __init__(self, parent : QWidget = None):
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
        if not self.base_url_edit.text().strip():
            errors.append("Base URL is required")
        
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