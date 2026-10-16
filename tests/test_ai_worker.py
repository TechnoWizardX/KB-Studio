import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.core.ai_worker import AiWorker, OLLAMA_URL


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

    def test_cancel_request_closes_stream_and_finishes_without_error(self):
        class MockStream:
            def __init__(self):
                self.closed = False

            def __iter__(self):
                yield Mock(
                    choices=[Mock(delta=Mock(content="partial response"))]
                )
                if not self.closed:
                    yield Mock(choices=[Mock(delta=Mock(content="should not appear"))])

            def close(self):
                self.closed = True

        worker = AiWorker(model="test", provider="ollama", base_url=OLLAMA_URL)
        worker._model = "test"
        worker._provider = "ollama"
        worker._base_url = OLLAMA_URL
        stream = MockStream()
        worker.open_ai_client = Mock()
        worker.open_ai_client.chat.completions.create.return_value = stream
        errors = []
        completed = []
        received_chunks = []
        worker.error_occurred.connect(errors.append)
        worker.generation_ended.connect(lambda: completed.append(True))
        worker.text_chunk_received.connect(
            lambda _chunk: (received_chunks.append(_chunk), worker.cancel_request())
        )

        worker.prepare_request()
        worker.send_request(
            provider="ollama",
            base_url=OLLAMA_URL,
            model="test",
            prompt="test",
        )

        self.assertTrue(stream.closed)
        self.assertEqual(received_chunks, ["partial response"])
        self.assertEqual(completed, [True])
        self.assertEqual(errors, [])

if __name__ == "__main__":
    unittest.main()
