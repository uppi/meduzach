# coding utf-8

import unittest
import unittest.mock as mock
import json
from meduzach.meduzach import Meduzach
from tests.data_example import examples

class FakeWsFinException(Exception):
    pass


fake = [
            {
                'topic': 'topic:lobby',
                'payload': {
                    'chats':
                    {
                        '234': {
                            'messages_count': 10,
                            'title': 'Chat 234',
                            'topic': '/lol/foo'
                        },
                        '345': {
                            'messages_count': 31,
                            'title': 'Chat 345',
                            'topic': '/lol/bar'
                        }
                    },
                    'chats_ids': [
                        '234', '345'
                    ]
                }
            },
            {
                'topic': 'topic:/lol/qua',
                'payload': {
                    'response':
                    {
                        'messages': [
                            {
                                'user_id': 1,
                                'message': 'Test message'
                            },
                            {
                                'user_id': 2,
                                'message': 'Test message 2'
                            },
                        ],
                        'users': [
                            {
                                'id': 1,
                                'name': 'First'
                            },
                            {
                                'id': 2,
                                'name': 'Second'
                            },
                        ]
                    }
                }}]

class FakeWs():
    def __init__(self, fake_results):
        self.fake_results = fake_results

    def recv(self):
        if not self.fake_results:
            raise FakeWsFinException()
        result = self.fake_results[0]
        self.fake_results = self.fake_results[1:]
        return result

    def connect(*args, **kwargs): pass
    def send(*args, **kwargs): pass
    def close(*args, **kwargs): pass
    #def connect(*args, **kwargs): pass



class TestMeduzach(unittest.TestCase):
    def test_init(self):
        m = Meduzach()
        self.assertIsNotNone(m)

    def test_run(self):
        m = Meduzach()
        m.slowmode = False
        with mock.patch('websocket.WebSocket',
                        lambda: FakeWs(examples)) as fake_ws:
            with self.assertRaises(FakeWsFinException):
                m.run(recover=False)
