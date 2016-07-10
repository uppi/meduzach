import datetime
import unittest
import unittest.mock as mock
from telegram import Update, Message, Chat
from meduzach.chatbot_logic import ChatbotLogic


def _construct_update(chat_id, msg_text):
    chat = Chat(chat_id, 'private')
    msg = Message(312, 111, datetime.datetime.now(), chat,
                  text=msg_text)
    upd = Update(123, message=msg)
    return upd


class TestMeduzachTelegramBot(unittest.TestCase):
    def test_help(self):
        mock_sender = mock.MagicMock()
        l = ChatbotLogic(
            mock.MagicMock(),
            mock_sender)
        l.settings['track'] = False

        show_help = l._create_show_help()
        show_help(mock_sender, _construct_update(123, '/help'))
        mock_sender.sendMessage.assert_called_once_with(
            123, text=ChatbotLogic.HELP_TEXT)

    def test_chats(self):
        mock_sender = mock.MagicMock()
        mock_listener = mock.MagicMock()

        l = ChatbotLogic(
            mock_listener,
            mock_sender)
        l.settings['track'] = False

        show_chats = l._create_show_chats()
        show_chats(mock_sender, _construct_update(123, '/chats'))
        mock_sender.sendMessage.assert_called_once_with(
            123, text="Список пуст.")

        mock_listener.chats = {
            '444': {
                'title': 'test chat',
                'messages_count': 100500,
                'last_message_at': 13
            },
            '512': {
                'title': 'my chat',
                'messages_count': 11,
                'last_message_at': 10
            },
        }

        show_chats(mock_sender, _construct_update(312, '/chats'))
        mock_sender.sendMessage.assert_called_with(
            312, text="/444 [-] test chat (100500)\n"
                      "/512 [-] my chat (11)")

    def test_toggle_subscription(self):
        mock_sender = mock.MagicMock()
        mock_listener = mock.MagicMock()

        l = ChatbotLogic(
            mock_listener,
            mock_sender)
        l.settings['track'] = False

        mock_listener.chats = {
            '512': {
                'title': 'my chat',
                'messages_count': 11,
                'last_message_at': 10,
                'key': 'some_key'
            }
        }
        mock_listener.messages = {
            '512': [
                {
                    'author': 'Такой-то чел',
                    'text': 'hello world',
                    'reply_to': '',
                    'inserted_at': 123
                }
            ]
        }

        toggle_subscription = l._create_toggle_subscription()

        self.assertNotIn('512', l.readers[123].chats)

        toggle_subscription(mock_sender, _construct_update(123, '/512'))

        try:
            mock_sender.sendMessage.assert_has_calls(
                [mock.call(123, text="Вы подписались на /512\n"
                                     "https://meduza.io/some_key"),
                 mock.call(123, parse_mode='Markdown',
                           text="*Такой-то чел* hello world")])
        except:
            print(list(mock_sender.sendMessage.call_list()))
            raise

        self.assertIn('512', l.readers[123].chats)

        toggle_subscription(mock_sender, _construct_update(123, '/512'))

        mock_sender.sendMessage.assert_called_with(
            123, text="Вы отписались от /512")

        self.assertNotIn('512', l.readers[123].chats)

        toggle_subscription(mock_sender, _construct_update(123, '/512'))

        self.assertIn('512', l.readers[123].chats)

        mock_sender.sendMessage.assert_called_with(
            123, text="Вы подписались на /512\nhttps://meduza.io/some_key")

    def test_process_chat_update(self):
        mock_sender = mock.MagicMock()
        mock_listener = mock.MagicMock()

        l = ChatbotLogic(
            mock_listener,
            mock_sender)
        l.settings['track'] = False

        mock_listener.chats = {
            '512': {
                'title': 'my chat',
                'messages_count': 11,
                'last_message_at': 10,
                'key': 'some_key'
            },
            '256': {
                'title': 'Лол',
                'messages_count': 0,
                'last_message_at': 100,
                'key': 'other_key'
            }
        }
        mock_listener.messages = {
            '512': [
                {
                    'author': 'Такой-то чел',
                    'text': 'hello world',
                    'reply_to': '',
                    'inserted_at': 123
                }
            ],
            '256': [
                {
                    'author': 'Кто-то',
                    'text': 'Текст',
                    'reply_to': '',
                    'inserted_at': 11
                }
            ]
        }

        toggle_subscription = l._create_toggle_subscription()
        process_chat_update = l._create_process_chat_update()

        toggle_subscription(mock_sender, _construct_update(123, '/512'))
        toggle_subscription(mock_sender, _construct_update(123, '/256'))
        process_chat_update(None, ('512', [
            {
                'author': 'Кто-то',
                'text': 'Новое сообщение!',
                'reply_to': '',
                'inserted_at': 234
            }
        ]))

        mock_sender.sendMessage.assert_called_with(
            123,
            text="Обновление чата /512 (my chat):\n*Кто-то* Новое сообщение!",
            parse_mode='Markdown')

        process_chat_update(None, ('256', [
            {
                'author': 'Экий-то чел',
                'text': 'Еще сообщение!',
                'reply_to': '',
                'inserted_at': 345
            }
        ]))

        mock_sender.sendMessage.assert_called_with(
            123,
            text="Обновление чата /256 (Лол):\n*Экий-то чел* Еще сообщение!",
            parse_mode='Markdown')
