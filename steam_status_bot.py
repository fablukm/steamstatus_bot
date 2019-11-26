import telegram
from telegram.ext import Updater, CommandHandler
import logging
import json
import steam
from ubisoft_server_status import make_rainbow_six_siege_poller

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
        set_commands(): Defines the interaction with the bot.
                        To add a command, define a nested function containing the definition of the command, best as a wrapper.
        define_job_queue(): Defines jobs to be executed periodically.
        configure_bot(): Add all handlers defined in set_handlers()
                         to the bot. Additional configuration belongs here.
                         Returns nothing.
        start_bot(): Start the bot using configuration as in configfile
                     and set_commands(). Returns nothing.

    Usage example to start the bot:
        Configure the bot as described in Readme.md and run

        telegram_bot = TelegramBot(configfile='./config.json')
        telegram_bot.start_bot()

        Now, the bot is accessible on telegram with one command /status
    '''

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

    def set_commands(self):
        if not hasattr(self, 'steamstatusfinder'):
            self.steamstatusfinder = SteamStatusFinder(
                configfile=self._configfile)

        def handle_status(update, context):
            msg = self.steamstatusfinder.get_status_string()
            context.bot.send_message(update.effective_chat.id, text=msg)
            return

        handlers = {'status': handle_status}
        return handlers

    def define_job_queue(self):
        if not hasattr(self, 'steamstatusfinder'):
            self.steamstatusfinder = SteamStatusFinder(
                configfile=self._configfile)

        # get momentaneous user status
        new_status_all = self.steamstatusfinder.get_is_playing()

        msg = ''
        do_display = False
        # for each user, check
        for user in new_status_all.keys():
            old_status = self.user_status[user]
            new_status = new_status_all[user]

            if not (new_status['is_pl'] == old_status['is_pl']):
                do_display = True
                verb = 'started' if new_status else 'stopped'
                game = new_status['game'] if new_status else ''
                msg += '{} {} playing {}\n'.format(user, verb, game)

            self.user_status[user] = new_status

        return do_display, msg

    def configure_bot(self):
        '''
        TelegramBot.configure_bot(): Defines commands and reads job queue.
        '''
        bot_commands = self.set_commands()

        # initialise updater
        telegram_token = self.config['telegram_bot_token']
        self.updater = Updater(token=telegram_token, use_context=True)
        self.dispatcher = self.updater.dispatcher

        # dispatch commands
        for key in bot_commands:
            self.dispatcher.add_handler(CommandHandler(key, bot_commands[key]))

        # define job queue
        if not hasattr(self, 'steamstatusfinder'):
            self.steamstatusfinder = \
                SteamStatusFinder(configfile=self._configfile)
        self.user_status = self.steamstatusfinder.get_is_playing()

        r6s_server_poller = make_rainbow_six_siege_poller(
            print_on_first_run=True)

        # TODO FMU: integrate ubi status check
        self.status_checkers = [
            self.define_job_queue,
            r6s_server_poller
        ]

        def _callback_status(context):
            print('running job queue...')
            for status_checker in self.status_checkers:
                do_display, msg = status_checker()

                if do_display:
                    logging.info('    sending message: {}'.format(msg))
                    context.bot.send_message(chat_id=int(
                        self.config['chat_id']), text=msg)
                else:
                    logging.info('    no changes. not sending message.')
            return

        dt = int(self.config["time_interval"])
        job_queue = self.updater.job_queue
        job_queue.run_repeating(_callback_status, interval=dt)
        return

    def start_bot(self):
        if not hasattr(self, 'updater'):
            self.configure_bot()
        self.updater.start_polling()
        logging.info('Bot running')
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
                out.append('{}:\t{} and playing {}'.format(
                    key, states[int(status[key]['personastate'])], status[key]['gameextrainfo']))
            else:
                out.append('{}:\t{} '.format(
                    key, states[int(status[key]['personastate'])]))
        return '\n'.join(out)

    def get_is_playing(self):
        if not hasattr(self, 'steam_api'):
            self.connect()
        states = self.config['personastates']
        status = self._get_user_status()

        # which games are checked
        game_ids = {game['steam_id']: game
                    for game in self.config['game_ids'].keys()}

        # what are users even playing
        is_pl = {user: 'gameid' in status[user].keys()
                 for user in status.keys()}

        # are users playing a game in the list?
        is_pl_valid = {user: {'is_pl': True, 'game': game_ids[status[user]['gameid']]}
                       if is_pl[user] and status[user]['gameid'] in list(game_ids.keys())
                       else {'is_pl': False, 'game': None} for user in status.keys()}

        return is_pl_valid

    def _get_user_status(self):
        ids = self.config['player_steam_ids']
        token = self.config['steam_api_token']
        api = self.steam_api
        return {key:
                api.ISteamUser.GetPlayerSummaries(key=token,
                                                  steamids=user[key])['response']['players'][0]
                for user in ids.keys()}


class UbiServerStatusFinder(object):
    '''
    UbiServerStatusFinder connects to the steam API and implements a status finder.

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
        logging.info('Opening UbiServerStatusFinder instance')
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
        return

    def get_status_string(self):
        return


if __name__ == '__main__':
    configfile = './config.json'
    telegram_bot = TelegramBot(configfile=configfile)
    telegram_bot.start_bot()
