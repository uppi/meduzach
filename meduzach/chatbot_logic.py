# coding utf-8
import logging
import collections
import threading
import re
import traceback
import datetime
import time

import telegram
from telegram.error import Unauthorized
from meduzach.connections import Connector


MSG_LIMIT = 2048

SHORT_TITLE_LENGTH = 12
CHATS_CACHE_EXPIRE_TIME = datetime.timedelta(seconds=10)

TOGGLE_SUB_RE = re.compile('^/(\d+)$')


class UserState():
    def __init__(self):
        self.latest = None
        self.unsub_time = collections.defaultdict(int)
        self.chats = []


class ChatbotLogic(Connector):
    HELP_TEXT = ("Список активных чатов: /chats\n"
                 "Чтобы подписаться или отписаться "
                 "от обновлений чата, "
                 "нажмите на его номер в списке.\n\n"
                 "Если что, пишите @upppi\n"
                 "https://github.com/uppi/meduzach")

    def __init__(self, listener, bot):
        listener.connect(
            'chat_updated', self._create_process_chat_update())
        self.listener = listener
        self.settings = {"track": True}

        self.meduzach_chats = {}
        self.chats_to_readers = collections.defaultdict(list)
        self.readers = collections.defaultdict(lambda: UserState())
        self.lock = threading.RLock()
        self.track_lock = threading.Lock()

        self.bot = bot

    def _track(self, user, action, payload=None):
        if not self.settings.get("track", False):
            return
        try:
            if BOTAN_TOKEN is not None:
                self.botan.track(user, payload, action)
            with self.track_lock:
                with open("track.txt", "a") as outf:
                    print(
                        datetime.datetime.now().strftime("%d/%m/%y_%H:%M"),
                        user, action, payload, file=outf)
        except:
            traceback.print_exc()

    def _restore_tracked(self):
        earliest = datetime.datetime.now() - datetime.timedelta(days=1)
        try:
            with open("track.txt") as infile:
                for line in infile:
                    try:
                        date, user, action, chat_id = line.split()
                        if chat_id == "None":
                            continue
                        if chat_id not in self.listener.chats:
                            print("chat {} ended".format(chat_id))
                            continue
                        user = int(user)
                        print("so we proceed", action)
                        is_sub = None
                        if action == "sub":
                            is_sub = True
                        elif action == "unsub":
                            is_sub = False
                        if is_sub is None:
                            continue
                        print("so we proceed - 2", action)
                        date = datetime.datetime.strptime(date, "%d/%m/%y_%H:%M")
                        if date > earliest:
                            print("date ok")
                            try:
                                if is_sub:
                                    print("sub!")
                                    self._sub(user, chat_id, False)
                                else:
                                    self._unsub(user, chat_id)
                            except IndexError:
                                print("No messages in chat")
                    except:
                        traceback.print_exc()
        except:
            traceback.print_exc()

    @staticmethod
    def escape_markdown(text):
        return (text.replace("\\", "\\\\")
                    .replace("*", "\\*")
                    .replace("_", "\\_")
                    .replace("[", "\\[")
                    .replace("`", "\\`"))

    @staticmethod
    def format_messages(messages):
        """
        Return a list of telegram messages
        representing given list of chat messages.

        Takes care of maximum telegram message length.
        """
        cur_msg = []
        cur_size = 0
        for message in messages:
            author = message["author"]
            text = message["text"]
            text = ChatbotLogic.escape_markdown(text)
            reply = message["reply_to"] or ""
            if reply:
                reply = self.listener.users.get(reply, "")
            if reply:
                reply = " @_{}_".format(reply["name"])
            formatted = "*{}*{} {}".format(author, reply, text)
            fmt_size = len(formatted)
            if cur_size + fmt_size < MSG_LIMIT:
                cur_msg.append(formatted)
                cur_size += fmt_size
            else:
                yield "\n".join(cur_msg)
                cur_msg = [formatted]
                cur_size = fmt_size
        if cur_msg:
            yield "\n".join(cur_msg)

    def _create_process_chat_update(self):
        def process_chat_update(sender, payload):
            """
            Publish new message to all subscriptors.

            Called from meduzach thread.
            """
            chat_id, messages = payload

            if not self.listener.is_initialized:
                return
            with self.lock:
                short_title = self.listener.chats[chat_id]['title']
                if len(short_title) > SHORT_TITLE_LENGTH + 3:
                    short_title = short_title[:SHORT_TITLE_LENGTH] + "..."
                header = ("Обновление чата /{} ({}):\n".format(
                    chat_id, short_title))
                formatted_messages = list(
                    ChatbotLogic.format_messages(messages))
                if len(formatted_messages) > 1 or len(
                        formatted_messages[0]) + len(header) >= MSG_LIMIT:
                    formatted_messages_h = [header] + formatted_messages
                else:
                    formatted_messages_h = [header + formatted_messages[0]]
                for reader_id in self.chats_to_readers[chat_id]:
                    try:
                        if self.readers[reader_id].latest == chat_id:
                            for msg in formatted_messages:
                                self.bot.sendMessage(
                                    reader_id,
                                    text=msg,
                                    parse_mode=telegram.ParseMode.MARKDOWN)
                        else:
                            self.readers[reader_id].latest = chat_id
                            for msg in formatted_messages_h:
                                self.bot.sendMessage(
                                    reader_id,
                                    text=msg,
                                    parse_mode=telegram.ParseMode.MARKDOWN)
                    except Unauthorized:
                        print("{} has revoked access, unsub him"
                              " from everything".format(reader_id))
                        chats = list(self.readers[reader_id].chats)
                        for sechat_id_to_unsub in chats:
                            self._unsub(reader_id, chat_id_to_unsub)
                    except:
                        print("Trying to send to {}".format(reader_id))
                        traceback.print_exc()
        return process_chat_update

    def _sub(self, reader_id, chat_id, send_messages=True):
        """
        Add reader subscription to chat
        """
        if send_messages:
            messages = [
                m
                for m in self.listener.messages[chat_id]
                if
                m['inserted_at'] >
                self.readers[reader_id].unsub_time[chat_id]]
            if messages:
                for msg in ChatbotLogic.format_messages(messages):
                    self.bot.sendMessage(
                        reader_id,
                        text=msg,
                        parse_mode=telegram.ParseMode.MARKDOWN)
            self.readers[reader_id].latest = chat_id
        self.chats_to_readers[chat_id].append(
            reader_id)
        self.readers[reader_id].chats.append(
            chat_id)

    def _unsub(self, reader_id, chat_id):
        """
        Remove subscription to chat from reader
        """
        self.chats_to_readers[chat_id].remove(reader_id)
        self.readers[reader_id].chats.remove(chat_id)
        self.readers[reader_id].unsub_time[chat_id] = (
            self.listener.messages[chat_id][-1]['inserted_at'])

    def _create_show_chats(self):
        def show_chats(bot, update):
            with self.lock:
                try:
                    reader_id = update.message.chat_id
                    print(self.readers[reader_id])
                    print(self.readers)
                    sorted_chats = sorted(
                        list(self.listener.chats.items()),
                        key=lambda c: -c[1]['last_message_at'])
                    chat_text = "\n".join(
                        "/{} [{}] {} ({})".format(
                            k,
                            '+' if k in self.readers[reader_id].chats
                                else '-',
                            v['title'],
                            v['messages_count'])
                        for k, v in sorted_chats)
                    if not chat_text:
                        chat_text = "Список пуст."
                    bot.sendMessage(reader_id, text=chat_text)
                except:
                    traceback.print_exc()
            self._track(update.message.chat.id, 'chats')
        return show_chats

    def _create_show_help(self):
        def show_help(bot, update):
            try:
                bot.sendMessage(
                    update.message.chat_id, text=ChatbotLogic.HELP_TEXT)
            except:
                traceback.print_exc()

            self._track(update.message.chat.id, 'help')
        return show_help

    def _create_toggle_subscription(self):
        def toggle_subscription(bot, update):
            """
            Add or remove subscription to chat.

            /123 command
            """
            action = "?"
            chat_id = None
            reader_id = update.message.chat_id
            with self.lock:
                try:
                    match = TOGGLE_SUB_RE.match(update.message.text)
                    if match is None:
                        print('message text: "{}"'.format(update.message.text))
                        return
                    chat_id = match.group(1)
                    if chat_id in self.listener.chats:
                        if reader_id in self.chats_to_readers[chat_id]:
                            bot.sendMessage(
                                reader_id,
                                text="Вы отписались от /{}".format(chat_id))
                            self._unsub(reader_id, chat_id)
                            action = "unsub"
                        else:
                            bot.sendMessage(
                                reader_id,
                                text="Вы подписались на /{}\n"
                                "https://meduza.io/{}".format(
                                    chat_id,
                                    self.listener.chats[chat_id]['key']))
                            self._sub(reader_id, chat_id)
                            action = "sub"
                    else:
                        bot.sendMessage(
                            reader_id,
                            text="Чата /{} уже не существует.".format(chat_id))
                except:
                    traceback.print_exc()
            self._track(reader_id, action, chat_id)
        return toggle_subscription
