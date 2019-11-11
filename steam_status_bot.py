import telegram
from telegram.ext import Updater, CommandHandler
import logging
import json
import steam

logformat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logformat, level=logging.INFO,
                    filename='./steam_status_bot.log', filemode='w')


class TelegramBot(object):
    '''
    TelegramBot defines basic interactions with the bot.

    args:
        configfile (str): path to the config.json file. Default: ./config.json

    methods:
        read_config(): Reads and loads the configuration from the file.
                       Returns: config (dict) with configuration.
        set_handlers(): Defines the interaction with the bot.
                        To add a command, define a nested function containing
                        functionality for the command, best as a wrapper.
                        Functions must take as input: update, context
                        Returns: handlers (dict) with structure:
                            {'bot_command': function_to_be_called}
        configure_bot(): Add all handlers defined in set_handlers()
                         to the bot. Additional configuration belongs here.
                         Returns nothing.
        start_bot(): Start the bot using configuration as in configfile
                     and set_handlers(). Returns nothing.

    Usage example to start the bot:
        Configure the bot as described in Readme.md and run

        telegram_bot = TelegramBot(configfile='./config.json')
        telegram_bot.start_bot()

        Now, the bot is accessible on telegram with one command /status
    '''

    def __init__(self, configfile='./config.json'):
        self._configfile = configfile
        self.config = self.read_config()
        return

    def read_config(self):
        try:
            with open(self._configfile, 'r') as handle:
                config = json.load(handle)
                logging.info('Config loaded from {}'.format(self._configfile))
        except FileNotFoundError:
            logging.info('File not found: {}'.format(self._configfile))
            raise FileNotFoundError(
                'File not found: {}'.format(self._configfile))
        return config

    def set_handlers(self):
        steamstatusfinder = SteamStatusFinder(configfile=self._configfile)

        def handle_status(update, context):
            msg = steamstatusfinder.get_status_string()
            context.bot.send_message(update.effective_chat.id, text=msg)

        handlers = {'status': handle_status}
        return handlers

    def configure_bot(self):
        bot_commands = self.set_handlers()

        telegram_token = self.config['telegram_bot_token']
        self.updater = Updater(token=telegram_token, use_context=True)
        self.dispatcher = self.updater.dispatcher

        for key in bot_commands:
            self.dispatcher.add_handler(CommandHandler(key, bot_commands[key]))

        return

    def start_bot(self):
        if not hasattr(self, 'updater'):
            self.configure_bot()
        self.updater.start_polling()
        logging.info('Bot running...')
        print('Bot running...')
        return


class SteamStatusFinder(object):
    '''
    SteamStatusFinder connects to the steam API and implements a status finder.

    args:
        configfile (str): path to the config.json file. Default: ./config.json

    methods:
        read_config(): Reads and loads the configuration from the file.
                       Returns: config (dict) with configuration.
        connect(): Connects to the steam API.
                   Returns nothing, but adds an instance of steam.WebAPI
                   as attribute to self.
        get_status_string(): Reads in all the user IDs from the config file.
                             Returns: a formatted string with their status.

    Usage example to start the bot:
        steam_status_finder = SteamStatusFinder(configfile='./config.json')
        print(steam_status_finder.get_status_string())
    '''

    def __init__(self, configfile='./config.json'):
        logging.info('Opening SteamStatusFinder instance')
        self._configfile = configfile
        self.config = self.read_config()
        return

    def read_config(self):
        try:
            with open(self._configfile, 'r') as handle:
                config = json.load(handle)
                logging.info('Config loaded from {}'.format(self._configfile))
        except FileNotFoundError:
            logging.info('File not found: {}'.format(self._configfile))
            raise FileNotFoundError(
                'File not found: {}'.format(self._configfile))
        return config

    def connect(self):
        # TODO: Error handling
        self.steam_api = steam.WebAPI(key=self.config['steam_api_token'])
        logging.info('Connected to Steam API.')
        return

    def get_status_string(self):
        if not hasattr(self, 'steam_api'):
            self.connect()
        states = self.config['personastates']
        status = self._get_user_status()
        out = []
        for key in status.keys():
            if 'gameid' in status[key]:
                out.append('{}:\tStatus \"{}\" and playing \"{}\"'.format(
                    key, states[int(status[key]['personastate'])], status[key]['gameextrainfo']))
            else:
                out.append('{}:\tStatus \"{}\" '.format(
                    key, states[int(status[key]['personastate'])]))
        return '\n'.join(out)

    def _get_user_status(self):
        ids = self.config['player_steam_ids']
        token = self.config['steam_api_token']
        api = self.steam_api
        return {key:
                api.ISteamUser.GetPlayerSummaries(key=token,
                                                  steamids=ids[key])['response']['players'][0]
                for key in ids.keys()}


if __name__ == '__main__':
    configfile = './config.json'
    telegram_bot = TelegramBot(configfile=configfile)
    telegram_bot.start_bot()
