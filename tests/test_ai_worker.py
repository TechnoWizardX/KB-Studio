import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.core.ai_worker import AiWorker, DEFAULT_SYSTEM_PROMPT, OLLAMA_URL
from src.resources.default_prompts import ABOUT_OSTIS


class AiWorkerContextTests(unittest.TestCase):
    def test_add_files_to_prompt_includes_utf8_file_contents(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            selected_file = Path(temporary_directory) / "knowledge.scs"
            selected_file.write_text("\ufeffконтент базы знаний", encoding="utf-8")

            worker = AiWorker(model="test", provider="ollama", base_url=OLLAMA_URL)
            prompt = worker.add_files_to_prompt("Проверь файл", [str(selected_file)])

            self.assertIn('"name": "knowledge.scs"', prompt)
            self.assertIn("контент базы знаний", prompt)
            self.assertNotIn("\ufeff", prompt)
            self.assertIn("untrusted data", prompt)

    def test_does_not_send_request_when_context_file_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            selected_file = Path(temporary_directory) / "binary.scs"
            selected_file.write_bytes(b"\xff\xfe\x00")

            worker = AiWorker(model="test", provider="ollama", base_url=OLLAMA_URL)
            worker.open_ai_client = Mock()
            errors = []
            worker.error_occurred.connect(errors.append)

            worker.send_request(
                provider="ollama",
                base_url=OLLAMA_URL,
                model="test",
                prompt="Проверь файл",
                files=[str(selected_file)],
            )

            worker.open_ai_client.chat.completions.create.assert_not_called()
            self.assertEqual(len(errors), 1)
            self.assertIn(str(selected_file), errors[0])

    def test_sends_conversation_history_to_model(self):
        worker = AiWorker(model="test", provider="ollama", base_url=OLLAMA_URL)
        worker.open_ai_client = Mock()
        worker.open_ai_client.chat.completions.create.return_value = []

        worker.send_request(
            provider="ollama",
            base_url=OLLAMA_URL,
            model="test",
            prompt="Следующий вопрос",
            history=[
                {"role": "user", "content": "Первый вопрос"},
                {"role": "assistant", "content": "Первый ответ"},
            ],
        )

        messages = worker.open_ai_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(
            messages,
            [
                {
                    "role": "system",
                    "content": f"{DEFAULT_SYSTEM_PROMPT}\n\n{ABOUT_OSTIS}",
                },
                {"role": "user", "content": "Первый вопрос"},
                {"role": "assistant", "content": "Первый ответ"},
                {"role": "user", "content": "Следующий вопрос"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
