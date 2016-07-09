# coding utf-8

import json
import time
import traceback
import datetime
import collections
import queue

import websocket

from meduzach.connections import Connector

HEART_PERIOD = datetime.timedelta(seconds=25)

IGNORED_MESSAGES = [
    "Поскольку тут никто не пишет, чат закроется через 2 часа"
    " (если никто за это время не продолжит разговор)",
    "Здесь 8 часов ничего не писали, поэтому чат закрылся. Всем спасибо!"]
MEDUZA_BOT_NAME = "Meduza Bot"


class Meduzach(Connector):
    def __init__(self):
        super().__init__()
        self.addr = ('wss://meduza.io/pond/socket/websocket?token=no_token'
                     '&vsn=1.0.0')
        self._ws = None
        self._ref = 1
        self._heart_time = None
        self._chats_to_be_updated = collections.defaultdict(int)
        self._chats_to_be_updated_queue = queue.Queue()
        self.chats = {}
        self.messages = collections.defaultdict(list)
        self.slowmode = True
        self.users = {}
        self.is_initialized = False

    def _topic_request(self, topic, event='phx_join', payload=None):
        print('creating request for {}, {}'.format(
            topic, event))
        if payload is None:
            payload = {}
        ref = self._ref
        self._ref += 1
        return {
            "topic": topic,
            "event": event,
            "payload": payload,
            "ref": str(ref)}

    def _heartbeat(self):
        if (self._heart_time is None or
                (datetime.datetime.now() - self._heart_time) >
                HEART_PERIOD):
            self._heart_time = datetime.datetime.now()
            self.send(self._topic_request('phoenix', 'heartbeat'))

    def connect_to_server(self):
        self._ws = websocket.WebSocket()
        self._ws.connect(self.addr)

    def send(self, data):
        if self.slowmode:
            time.sleep(1)
        # with open("log.txt", "a") as f:
        #    print("<<<", datetime.datetime.now(), json.dumps(data), file=f)
        self._ws.send(json.dumps(data))

    def receive(self):
        response = self._ws.recv()
        # with open("log.txt", "a") as f:
        #     print("<<<", datetime.datetime.now(), response, file=f)
        return json.loads(response)

    def update_chats(self, response):
        chats = {
            chat_id: response['payload']['chats'][chat_id]
            for chat_id in response.get('payload', {}).get('chats_ids', [])
            if response['payload']['chats'][chat_id]['messages_count'] > 0
        }

        if not chats:
            return

        for chat_id, chat_info in chats.items():
            previous = self.chats.get(chat_id, {'messages_count': 0})
            msg_update = (chat_info['messages_count'] -
                          previous['messages_count'])
            if msg_update > 0:
                if chat_id not in self._chats_to_be_updated:
                    self._chats_to_be_updated_queue.put(chat_id)
                self._chats_to_be_updated[chat_id] += msg_update

        old_chats = set(self.chats.keys())
        new_chats = set(chats.keys())

        removed_chats = old_chats - new_chats
        added_chats = new_chats - old_chats

        self.chats = chats
        if added_chats or removed_chats:
            self.emit('chatlist_updated', (added_chats, removed_chats))

    def change_topic(self, topic):
        self.send(self._topic_request("topic:" + topic))

    def update_messages(self, response):
        if 'messages_ids' in response.get(
                'payload', {}).get('response', {}):
            chat_info = response['payload']['response']
        elif 'messages_ids' in response.get('payload', {}):
            chat_info = response['payload']
        else:
            return
        if 'messages' not in chat_info:
            return
        messages = chat_info['messages']
        if 'users' in chat_info:
            for user_id, user_info in chat_info['users'].items():
                self.users[user_id] = user_info

        messages = [
            {
                "author": self.users[messages[msg_id]['user_id']]['name'],
                "text": messages[msg_id]['message'],
                "chat_id": messages[msg_id].get('chat_id'),
                "inserted_at": messages[msg_id].get('inserted_at', 1),  # ??
                "reply_to": messages[msg_id].get('reply_to_user_id')
            }
            for msg_id in chat_info['messages_ids']
        ]

        chat_id = chat_info.get('chat_id') or messages[0]['chat_id']
        chat_id = str(chat_id)

        self._store_updated_messages(chat_id, messages)
        if not self._filter_out_chat_messages(messages):
            self.emit('chat_updated', (chat_id, messages))

    def _store_updated_messages(self, chat_id, messages):
        self.messages[chat_id] += messages

    def _filter_out_chat_messages(self, messages):
        return (len(messages) == 1 and
                messages[0]["author"] == MEDUZA_BOT_NAME and
                messages[0]["text"] in IGNORED_MESSAGES)

    def close(self):
        if self._ws is not None:
            self._ws.close()
            self._ws = None

    def route_response(self, response):
        if response['topic'] == 'topic:lobby':
            self.update_chats(response)
            return False
        elif response['topic'] == 'phoenix':
            return False
        else:
            event = response.get('event')
            if (event != 'current_chats' and
                    event != 'new_msg' and event != 'phx_reply'):
                return False
            self.update_messages(response)
            return True

    def run(self, recover=True):
        while True:
            try:
                self.connect_to_server()

                while True:
                    while self._chats_to_be_updated_queue.empty():
                        self._heartbeat()
                        self.send(self._topic_request("topic:lobby"))
                        self.route_response(self.receive())
                        self.route_response(self.receive())
                        if not self._chats_to_be_updated_queue.empty():
                            time.sleep(1)

                    chat_id = self._chats_to_be_updated_queue.get_nowait()
                    self.change_topic(
                        self.chats[chat_id]['key'])
                    chat_updated = False

                    while not chat_updated:
                        self._heartbeat()
                        chat_updated = self.route_response(self.receive())
                    del self._chats_to_be_updated[chat_id]
                    if self._chats_to_be_updated_queue.empty():
                        print("Chat list initialized!")
                        self.is_initialized = True
            except Exception:
                if not recover:
                    raise
                traceback.print_exc()
                self.close()
                time.sleep(5)
                print("Reconnecting...")
            finally:
                self.close()  # It's okay to call it twice


def publish(chat_id, messages):
    print("Update from {}".format(chat_id))
    print("=======")
    for message in messages:
        print("[{author}] {text}".format(**message))
    print("=======")


def main():
    listener = Meduzach()
    listener.connect('chat_updated', lambda sender, payload: publish(*payload))
    listener.run()

if __name__ == '__main__':
    main()
