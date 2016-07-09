# coding utf-8

import unittest
import unittest.mock as mock
import json
from meduzach.meduzach import Meduzach
from tests.data_example import examples


class FakeWsFinException(Exception):
    pass


class FakeWs():
    def __init__(self, fake_results):
        self.fake_results = fake_results

    def recv(self):
        if not self.fake_results:
            raise FakeWsFinException()
        result = self.fake_results[0]
        self.fake_results = self.fake_results[1:]
        return result

    def connect(*args, **kwargs):
        pass

    def send(*args, **kwargs):
        pass

    def close(*args, **kwargs):
        pass


class TestMeduzach(unittest.TestCase):
    def test_init(self):
        m = Meduzach()
        self.assertIsNotNone(m)

    def test_run(self):
        m = Meduzach()
        m.slowmode = False
        with mock.patch('websocket.WebSocket',
                        lambda: FakeWs(examples)):
            with self.assertRaises(FakeWsFinException):
                m.run(recover=False)

    def test_add_action__emit_update(self):
        m = Meduzach()
        calls = []

        m.emit('chat_updated', (1, "1212"))

        self.assertEqual(0, len(calls))

        def _action(sender, payload):
            chat_id, msgs = payload
            calls.append("{}___{}".format(chat_id, msgs))

        m.connect('chat_updated', _action)

        m.emit('chat_updated', (2, "2323"))
        m.emit('chat_updated', (3, "34 34"))

        self.assertEqual(2, len(calls))
        self.assertEqual(calls[0], "2___2323")
        self.assertEqual(calls[1], "3___34 34")

    def test_update_messages(self):
        m = Meduzach()
        calls = []

        def _action(sender, payload):
            chat_id, msgs = payload
            for msg in msgs:
                calls.append("{}___{}".format(chat_id, msg['text']))
        m.connect('chat_updated', _action)

        m.update_messages(json.loads(examples[6]))

        self.assertEqual(3, len(calls), str(calls))
        self.assertEqual(calls, [
            "328___some text",
            "328___и еще сообщение",
            "328___пример сообщения"])

    def test_update_chats(self):
        m = Meduzach()
        m.update_chats(json.loads(examples[1]))
        self.assertEqual(18, len(m.chats))
        self.assertIn('313', m.chats)
