# coding utf-8
import logging
import collections
import threading
import re
import traceback
import datetime

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from meduzach.credentials import BOT_TOKEN

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)

MSG_LIMIT = 2048

SHORT_TITLE_LENGTH = 12
CHATS_CACHE_EXPIRE_TIME = datetime.timedelta(seconds=10)

TOGGLE_SUB_RE = re.compile('^/(\d+)$')


class UserState():
    def __init__(self):
        self.latest = None
        self.unsub_time = collections.defaultdict(int)
        self.chats = []


class context:
    meduzach = None
    chats_to_readers = collections.defaultdict(list)
    readers = collections.defaultdict(lambda: UserState())
    bot = None
    lock = threading.RLock()


def _format_messages(messages):
    """
    Return a list of telegram messages
    representing given list of chat messages.

    Takes care of maximum telegram message length.
    """
    cur_msg = []
    cur_size = 0
    for message in messages:
        formatted = "[{author}] {text}".format(**message)
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


def process_chat_update(chat_id, messages):
    """
    Publish new message to all subscriptors.

    Called from meduzach thread.
    """
    with context.lock:
        short_title = context.meduzach.chats[chat_id]['title']
        if len(short_title) > SHORT_TITLE_LENGTH + 3:
            short_title = short_title[:SHORT_TITLE_LENGTH] + "..."
        header = ("Обновление чата /{} ({}):\n".format(
            chat_id, short_title))
        formatted_messages = list(_format_messages(messages))
        if len(formatted_messages) > 1 or len(
                formatted_messages[0]) + len(header) >= MSG_LIMIT:
            formatted_messages_h = [header] + formatted_messages
        else:
            formatted_messages_h = [header + formatted_messages[0]]
        for reader_chat_id in context.chats_to_readers[chat_id]:
            if context.readers[reader_chat_id].latest == chat_id:
                for msg in formatted_messages:
                    context.bot.sendMessage(reader_chat_id, msg)
            else:
                context.readers[reader_chat_id].latest = chat_id
                for msg in formatted_messages_h:
                    context.bot.sendMessage(reader_chat_id, msg)


def _sub(reader_id, chat_id):
    """
    Add reader subscription to chat
    """
    messages = [
        m for m in context.meduzach.messages[chat_id]
        if m['inserted_at'] > context.readers[reader_id].unsub_time[chat_id]]
    if messages:
        for msg in _format_messages(messages):
            context.bot.sendMessage(
                reader_id,
                text=msg)
    context.chats_to_readers[chat_id].append(
        reader_id)
    context.readers[reader_id].chats.append(
        chat_id)


def _unsub(reader_id, chat_id):
    """
    Remove subscription to chat from reader
    """
    context.chats_to_readers[chat_id].remove(reader_id)
    context.readers[reader_id].chats.remove(chat_id)
    context.readers[reader_id].unsub_time[chat_id] = (
        context.meduzach.messages[chat_id][-1]['inserted_at'])

###
# section Bot methods.
###


def chats(bot, update):
    """
    List available chats.

    /chats command
    """
    with context.lock:
        try:
            reader_id = update.message.chat_id
            sorted_chats = sorted(
                list(context.meduzach.chats.items()),
                key=lambda c: -c[1]['last_message_at'])
            chat_text = "\n".join(
                "/{} [{}] {} ({})".format(
                    k,
                    '+' if k in context.readers[reader_id].chats else '-',
                    v['title'],
                    v['messages_count'])
                for k, v in sorted_chats)
            if not chat_text:
                chat_text = "Список пуст."
            bot.sendMessage(reader_id, text=chat_text)
        except:
            traceback.print_exc()


def show_help(bot, update):
    """
    Show help.

    /help command
    """
    try:
        help_text = ("Список активных чатов: /chats\n"
                     "Чтобы подписаться или отписаться от обновлений чата, "
                     "нажмите на его номер в списке\n")
        bot.sendMessage(
            update.message.chat_id, text=help_text)
    except:
        traceback.print_exc()


def toggle_subscription(bot, update):
    """
    Add or remove subscription to chat.

    /123 command
    """
    with context.lock:
        try:
            reader_id = update.message.chat_id
            match = TOGGLE_SUB_RE.match(update.message.text)
            if match is None:
                print('"{}"'.format(update.message.text))
                return
            chat_id = match.group(1)
            if chat_id in context.chats_to_readers:
                if reader_id in context.chats_to_readers[chat_id]:
                    bot.sendMessage(
                        reader_id,
                        "Вы отписались от /{}".format(chat_id))
                    _unsub(reader_id, chat_id)
                else:
                    bot.sendMessage(
                        reader_id,
                        "Вы подписаны на /{}\nhttps://meduza.io/{}".format(
                            chat_id,
                            context.meduzach.chats[chat_id]['key']))
                    _sub(reader_id, chat_id)
        except:
            traceback.print_exc()


###
# end section Bot methods.
###

def error(bot, update, error):
    logging.warning('Update "%s" caused error "%s"' % (update, error))


def run(meduzach, token):
    """
    Start telegram bot.
    """
    context.meduzach = meduzach
    context.token = token

    updater = Updater(context.token)

    context.bot = updater.bot

    updater.dispatcher.add_handler(CommandHandler('help', show_help), group=0)
    updater.dispatcher.add_handler(CommandHandler('chats', chats), group=0)

    updater.dispatcher.add_handler(
        MessageHandler([Filters.command], toggle_subscription), group=1)

    updater.dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()


def main():
    import meduzach.meduzach as m
    listener = m.Meduzach()
    listener.add_chat_update_action(process_chat_update)

    listener_thread = threading.Thread(
        target=lambda m: m.run(), args=(listener, ))
    listener_thread.start()
    run(listener, BOT_TOKEN)


if __name__ == '__main__':
    main()
