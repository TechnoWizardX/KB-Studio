from PySide6.QtWidgets import QFrame, QPushButton, QTextEdit, QComboBox, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import QSize
from src.utils.config_manager import ConfigManager
from src.resources.icons import Icons
from src.core.ai_worker import send_request
class ChatBot(QFrame):
    def __init__(self):
        super().__init__()
        last_model = ConfigManager.get("last_model")
        self._display_name = last_model.get("display_name")
        print(f"last model: {self._display_name}")
        self._model = last_model.get("model")
        self._provider = last_model.get("provider")
        self._api_name = last_model.get("api_name")
        self._base_url = last_model.get("base_url")
        self.models_list = ConfigManager.get("models")

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

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

        self.models_combo_box = QComboBox()
        self.sender_bottom_layout.addWidget(self.models_combo_box)
        self.load_models_to_list()

        self.models_combo_box.currentIndexChanged.connect(self.on_selection_changed)
        self.main_layout.addStretch(0)
        self.main_layout.addWidget(self.chat_sender)

    def load_models_to_list(self):
        if self.models_list:
            for model_data in self.models_list: 
                display_name = model_data.get("display_name")
                self.models_combo_box.addItem(model_data.get("display_name"), userData=model_data)
            last_index = self.models_combo_box.findText(self._display_name)
            self.models_combo_box.setCurrentIndex(last_index)
        self.models_combo_box.addItem("Add new model...", userData="add_model")

    def on_selection_changed(self):
        if self.models_combo_box.currentIndex() == self.models_combo_box.findData("add_model"):
            print("Add model function called")
        elif self.models_combo_box.currentIndex() is not None:
            data = self.models_combo_box.currentData()
            self._display_name = data.get("display_name")
            self._model = data.get("model")
            self._provider = data.get("provider")
            self._api_name = data.get("api_name")
            self._base_url = data.get("base_url")
            ConfigManager.set("last_model", data)
    def send_request(self):
        pass