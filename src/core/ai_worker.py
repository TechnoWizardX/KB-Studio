from openai import OpenAI
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from src.utils.file_manager import get_context_file_content

DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
DEFAULT_SYSTEM_PROMPT = """
Ты - ИИ чат-бот для помощи с работой с .scs файлами (SC.s-кодом).
.scs файл - язык описания базы знаний для технологии OSTIS. Является частью общей концепции - SC-кода
OSTIS - Open Semantic Technology for Intellegence Systems, предназначена для разработки семантических (символьных) ИИ
SC-код - Semantic Computer Code - предназначен для описания знаний. Есть всего 3 вида:
SC.g - сохраняется в .gwf файлах, редактируется при помощи редактора KBE, представлен визуальным графов
SC.s - сохраняется в .scs файлах, знания описываются текстом при помощи специального синтаксиса
SC.n - представляет знания в виде множеств

"""

OLLAMA_URL = "http://localhost:11434/v1"


class AiWorker(QObject):
    text_chunk_received = Signal(str)
    generation_ended = Signal()
    error_occurred = Signal(str)
    # Signal to trigger request in worker thread
    do_request = Signal(str, str, str, str, str, str, list)

    def __init__(self, model, provider, base_url):
        super().__init__()
        self._model = model
        self._provider = provider
        self._base_url = base_url
        self.open_ai_client = None
        # Connect signal to slot (will run in worker thread)
        self.do_request.connect(self.send_request)
        
    def send_request(self, provider: str = "openai", base_url: str = DEFAULT_URL, 
                     model: str = DEFAULT_MODEL, api: str = "", prompt: str = "", 
                     system_prompt: str = DEFAULT_SYSTEM_PROMPT, files: list | None = None):
        if files:
            prompt = self.add_files_to_prompt(prompt, files)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
            
        is_ollama = provider.lower() == "ollama"
        target_url = OLLAMA_URL if is_ollama else base_url
        target_api = "ollama" if is_ollama else api
        
        # Check if we need to recreate the client
        need_recreate = (
            self.open_ai_client is None or
            self._provider != provider or
            self._model != model or
            self._base_url != target_url
        )
        
        if need_recreate:
            if not is_ollama and not api:
                self.error_occurred.emit("There's no API key for current model")
                return
            self.open_ai_client = OpenAI(api_key=target_api, base_url=target_url)
            self._model = model
            self._provider = provider
            self._base_url = target_url
        
        try:
            stream = self.open_ai_client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    text_chunk = chunk.choices[0].delta.content
                    self.text_chunk_received.emit(text_chunk)
            self.generation_ended.emit()
        except Exception as e:
            self.error_occurred.emit(f"AI request failed: {e}")

    def add_files_to_prompt(self, prompt: str, files: list) -> str:
        """Append the content of the files to the prompt."""
        for file_path in files:
            try:
                file_content = get_context_file_content(file_path)
                prompt += f"\n\nContent of {Path(file_path).name}:\n{file_content}"
            except Exception as e:
                self.error_occurred.emit(f"Failed to read file '{file_path}': {e}")
        return prompt