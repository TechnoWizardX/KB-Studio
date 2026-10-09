from dotenv import load_dotenv
import requests
import os

load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "liquid/lfm-2.5-2.6b:free"

def send_request(provider: str = "openai", url : str = DEFAULT_URL, model : str = DEFAULT_MODEL, prompt : str = "", system_prompt : str = None, files : list = []):
    if provider != "ollama":
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role" : "system", "content": system_prompt})
        messages.append({"role" : "user", "content": prompt})

        payload = {
                "model": "openrouter/free",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 200,
            }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

if __name__ == "__main__":
    print("AI-помощник (напишите 'выход' для завершения)")
    system = "Ты дружелюбный эксперт по программированию на Python. Отвечай кратко и понятно."
    while True:
        user_input = input("\nВы: ")
        if user_input.lower() in ("выход", "exit"):
            break
        answer = send_request(prompt=user_input, system_prompt=system)
        print(f"AI: {answer}")