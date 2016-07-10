# Meduzach

Meduzach is a telegram bot for [Meduza](https://meduza.io) chats. It currently supports subscribing to a number of chats and getting updates in the real time.

It is at an early development stage.

The bot is hosted as [@MeduzachBot](https://telegram.me/meduzachbot)

## Development

The project requires python3.4+.

Call `pip3 install -r requirements.txt` to install required libraries.

Create a file `meduzach/credentials.py` with your own development token.

Call `nosetests` for unit tests.

## TODO

The main goal is to keep the bot interface as simple as possible.

- Use external storage to keep people's preferences when we restart the bot.
- Subscribe to new (reddit-style "hot") chats, subscribe to particular people.
- It is unclear if it is a good idea to implement posting from telegram.

## Acknowledgements

Many thanks to the [meduza-chat](https://github.com/urij/meduza-chat) project for the initial idea.