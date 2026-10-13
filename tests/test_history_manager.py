import tempfile
import unittest
from pathlib import Path

from src.utils.history_manager import HistoryManager


class HistoryManagerTests(unittest.TestCase):
    def test_persists_messages_and_returns_recent_messages_in_order(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manager = HistoryManager(Path(temporary_directory) / "history.sqlite3")
            manager.add_message("user", "Первый вопрос")
            manager.add_message("assistant", "Ответ")
            manager.add_message("user", "Второй вопрос")

            messages = manager.get_messages(limit=2)

            self.assertEqual(
                [(message["role"], message["content"]) for message in messages],
                [("assistant", "Ответ"), ("user", "Второй вопрос")],
            )
            self.assertTrue(messages[0]["created_at"])

    def test_sql_injection_text_is_stored_as_message_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manager = HistoryManager(Path(temporary_directory) / "history.sqlite3")
            malicious_text = "'; DROP TABLE messages; --"

            manager.add_message("user", malicious_text)

            self.assertEqual(manager.get_messages()[0]["content"], malicious_text)
            manager.add_message("assistant", "База данных всё ещё работает")
            self.assertEqual(len(manager.get_messages()), 2)

    def test_rejects_invalid_roles_and_limits(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manager = HistoryManager(Path(temporary_directory) / "history.sqlite3")

            with self.assertRaises(ValueError):
                manager.add_message("system", "Недопустимая роль")
            with self.assertRaises(ValueError):
                manager.get_messages(limit=0)

    def test_clear_removes_all_messages(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manager = HistoryManager(Path(temporary_directory) / "history.sqlite3")
            manager.add_message("user", "Удали меня")
            manager.add_message("assistant", "Ответ")

            manager.clear()

            self.assertEqual(manager.get_messages(), [])
            manager.add_message("user", "База остаётся доступной")
            self.assertEqual(len(manager.get_messages()), 1)


if __name__ == "__main__":
    unittest.main()
