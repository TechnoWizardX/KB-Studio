from dotenv import load_dotenv
from openai import OpenAI
import os
from PySide6.QtCore import QObject
from src.core.signals import signals

DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"
DEFAULT_SYSTEM_PROMPT = """
Ты - ИИ чат-бот для помощи с работой с .scs файлами (SC.s-кодом).
.scs файл - язык описания базы знаний для технологии OSTIS. Является частью общей концепции - SC-кода
OSTIS - Open Semantic Technology for Intellegence Systems, предназначена дял разработки семантических (символьных) ИИ
SC-код - Semantic Computer Code - предназначен для описания знаний. Есть всего 3 вида:
SC.g - сохраняется в .gwf файлах, редактируется при помощи редактора KBE, представлен визуальным графов
SC.s - сохраняется в .scs файлах, знания описываются текстом при помощи специального синтаксиса
SC.n - представляет знания в виде множеств

"""

OLLAMA_URL = "http://localhost:11434/v1"


class AiWorker(QObject):
    def __init__(self, api, model, provider, base_url):
        super().__init__()
        self._model = model
        self.__api = api
        self._provider = provider
        self._base_url = base_url
        self.open_ai_client = None
        
    def send_request(self, provider: str = "openai", base_url: str = DEFAULT_URL, 
                     model: str = DEFAULT_MODEL, api: str = "", prompt: str = "", 
                     system_prompt: str = DEFAULT_SYSTEM_PROMPT, files: list = []):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        is_ollama = provider.lower() == "ollama"
        target_url = OLLAMA_URL if is_ollama else base_url
        target_api = "ollama" if is_ollama else api
        
        need_recreate = (
            self.open_ai_client is None or
            self._provider != provider or
            self._model != model or
            self._base_url != target_url
        )
        
        if need_recreate:
            if not is_ollama and not api:
                signals.error_occured.emit("There's no API key for current model")
                return
            self.open_ai_client = OpenAI(api_key=target_api, base_url=target_url)
            self._model = model
            self._provider = provider
            self._base_url = target_url
            self.__api = api
        
        try:
            stream = self.open_ai_client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    text_chunk = chunk.choices[0].delta.content
                    signals.text_chunk_recieved.emit(text_chunk)
                    print(text_chunk)
                    
            signals.generation_ended.emit()
        except Exception as e:
            signals.error_occured.emit(f"AI request failed: {e}")