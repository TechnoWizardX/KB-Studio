import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from src.core.signals import signals
from src.gui.right_sidebar.chat import ChatBot, Message, MessagesBox
from src.utils.config_manager import ConfigManager


class ChatMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_empty_state_is_hidden_when_a_message_arrives_and_returns_on_clear(self):
        box = MessagesBox()
        self.assertFalse(box._empty_state.isHidden())

        box.add_message("hello", "user")
        self.app.processEvents()

        self.assertTrue(box._empty_state.isHidden())

        box.clear_messages()
        self.app.processEvents()

        self.assertFalse(box._empty_state.isHidden())
        self.assertEqual(box.main_layout.count(), 2)

    def test_messages_are_tagged_by_author_and_show_a_role(self):
        user_message = Message("hello", "user")
        ai_message = Message("hi", "ai")

        self.assertEqual(user_message.objectName(), "messageUser")
        self.assertEqual(ai_message.objectName(), "messageAi")
        self.assertEqual(user_message.role.text(), "You")
        self.assertEqual(ai_message.role.text(), "AI")

    def test_links_open_in_the_default_browser_instead_of_inside_the_label(self):
        message = Message("see [docs](https://example.com)", "ai")

        self.assertFalse(message.label.openExternalLinks())
        with patch(
            "src.gui.right_sidebar.chat.QDesktopServices.openUrl"
        ) as open_url:
            message._open_link("https://example.com")

        open_url.assert_called_once_with(QUrl("https://example.com"))

    def test_streaming_chunks_update_content_and_notify_the_scroll_view(self):
        message = Message("", "ai")
        updates = []
        message.content_changed.connect(lambda: updates.append(message.content))

        message.add_chunk("Hello")
        message.add_chunk(" world")
        message.finish_streaming()

        self.assertEqual(message.content, "Hello world")
        self.assertEqual(updates, ["Hello", "Hello world"])
        self.assertEqual(message.label.text(), "Hello world")


class ChatPromptContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "context.scs"
        self.path.write_text("// context", encoding="utf-8")
        self.resolved = str(self.path.resolve())
        self._set_patcher = patch.object(ConfigManager, "set")
        self._set_patcher.start()

        def fake_ai_setup(bot):
            bot._display_name = ""
            bot._model = ""
            bot._provider = ""
            bot._base_url = ""
            bot.models_list = []

        with patch.object(ChatBot, "init_ai_connect", fake_ai_setup), patch(
            "src.gui.right_sidebar.chat.HistoryManager"
        ):
            self.bot = ChatBot()

    def tearDown(self):
        for signal, slot in (
            (signals.add_file_to_context, self.bot.add_context_file),
            (signals.theme_changed, self.bot._refresh_icons),
            (
                signals.message_context_count_updated,
                self.bot._message_context_count_updated,
            ),
            (
                signals.startup_message_count_updated,
                self.bot._startup_message_count_updated,
            ),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self.bot.deleteLater()
        self.app.processEvents()
        self._set_patcher.stop()
        self.temp_dir.cleanup()

    def _add_via_signal(self):
        signals.add_file_to_context.emit(str(self.path))
        self.app.processEvents()

    def test_signal_attaches_the_file_to_the_prompt_context(self):
        self.assertEqual(self.bot._context_files, [])

        self._add_via_signal()

        self.assertEqual(self.bot._context_files, [self.resolved])
        self.assertEqual(list(self.bot.files_list._files), [self.resolved])
        self.assertFalse(self.bot.files_list.isHidden())

    def test_the_same_file_is_attached_only_once(self):
        self._add_via_signal()
        self._add_via_signal()

        self.assertEqual(self.bot._context_files, [self.resolved])
        self.assertEqual(len(self.bot.files_list._files), 1)

    def test_removing_the_row_drops_the_file_from_the_context(self):
        self._add_via_signal()

        self.bot.files_list._files[self.resolved].remove_requested.emit(
            self.resolved
        )
        self.app.processEvents()

        self.assertEqual(self.bot._context_files, [])
        self.assertTrue(self.bot.files_list.isHidden())

    def test_empty_paths_are_ignored(self):
        signals.add_file_to_context.emit("")
        self.app.processEvents()

        self.assertEqual(self.bot._context_files, [])
        self.assertTrue(self.bot.files_list.isHidden())
