import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from src.gui.right_sidebar.chat import Message, MessagesBox


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
