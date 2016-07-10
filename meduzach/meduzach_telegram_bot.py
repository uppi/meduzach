# coding utf-8
import logging
import threading
import time

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters


from meduzach.connections import Connector
from meduzach.chatbot_logic import ChatbotLogic
from meduzach.meduzach import Meduzach
from meduzach.credentials import BOT_TOKEN


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)

###
# section Bot methods.
###


class TelegramBot(Connector):
    def __init__(self):
        super().__init__()
        self.bot = None
        self.connect('send_msg', self.create_send_msg())

    def create_send_text(self):
        def _send_text(sender, payload):
            chat_id, message_text = payload
            self.bot.sendMessage(
                chat_id, text=message_text)
        return _send_text


listener = Meduzach()
telegram_bot = TelegramBot()
bot_logic = ChatbotLogic(listener, telegram_bot)

_show_chats = bot_logic._create_show_chats()
_show_help = bot_logic._create_show_help()
_toggle_subscription = bot_logic._create_toggle_subscription()
_process_chat_update = bot_logic._create_process_chat_update()


def chats(bot, update):
    """
    List available chats.

    /chats command
    """
    telegram_bot.emit('chats', update)


def show_help(bot, update):
    """
    Show help.

    /help command
    """
    telegram_bot.emit('help', update)


def toggle_subscription(bot, update):
    """
    Add or remove subscription to chat.

    /123 command
    """
    telegram_bot.emit('toggle_subscription', update)


def error(bot, update, error):
    logging.warning('Update "%s" caused error "%s"' % (update, error))


def run(token):
    """
    Start telegram bot.
    """
    bot_logic.restore_tracked()

    updater = Updater(token)
    telegram_bot.bot = updater.bot

    updater.dispatcher.add_handler(CommandHandler('help', show_help), group=0)
    updater.dispatcher.add_handler(CommandHandler('start', show_help), group=0)
    updater.dispatcher.add_handler(CommandHandler('chats', chats), group=0)
    updater.dispatcher.add_handler(
        MessageHandler([Filters.command], toggle_subscription), group=1)

    updater.dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()


def main():
    listener_thread = threading.Thread(
        target=lambda m: m.run(), args=(listener, ))
    listener_thread.start()
    while not listener.is_initialized:
        time.sleep(3)

    run(BOT_TOKEN)


if __name__ == '__main__':
    main()
