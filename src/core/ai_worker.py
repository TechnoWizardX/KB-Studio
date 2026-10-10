from dotenv import load_dotenv
from openai import OpenAI
import os

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

class AiWorker():
    def __init__(self, api, model, provider, base_url):
        self._model = model
        self.__api = api
        self._provider = provider
        self._base_url = base_url

        self.open_ai_client = OpenAI()
        signals.send_request.connect(self.send_request)
        
    def send_request(self, provider: str = "openai", base_url : str = DEFAULT_URL, model : str = DEFAULT_MODEL,
                  api: str = "",  prompt : str = "", system_prompt : str = DEFAULT_SYSTEM_PROMPT, 
                  files : list = []):
        messages = [
            { 
                "role" : "system",
                "content" : system_prompt
            },
            {
                "role" : "user",
                "content" : prompt
            }
        ]
        if provider.lower() != "ollama":
            if self._model != model:
                if self._provider != provider:
                    self.open_ai_client = OpenAI(api_key=api,
                                                base_url=self._base_url
                                                )
                    self._model = model
                    self._provider = provider
                    self._base_url = base_url
                    self.__api = api
            
                if not api:
                    signals.error_occured.emit("There's no API key for current model")
                    return
            stream = self.open_ai_client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True
            )
            for chunk in stream:
                if chunk.choises.delta.content is not None:
                    text_chunk = chunk.choises.delta.content
                    signals.text_chunk_recieved.emit(text_chunk)
        else:
            if self._base_url != "http://localhost:11434/v1":
                self._base_url = "http://localhost:11434/v1"
            if self._model != model:
                self._model = model
                self.open_ai_client = OpenAI(api_key="ollama",
                                             base_url=self._base_url
                                            )
            stream = self.open_ai_client.chat.completions.create(
                            model=self._model,
                            messages=messages,
                            stream=True
                        )
            
            for chunk in stream:
                if chunk.choises.delta.content is not None:
                    text_chunk = chunk.choises.delta.content
                    signals.text_chunk_recieved.emit(text_chunk)