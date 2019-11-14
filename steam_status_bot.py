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
            raise FileNotFoundError('File not found: {}'.format(self._configfile))
        return config

    def set_commands(self):
        if not hasattr(self, 'steamstatusfinder'):
            self.steamstatusfinder = SteamStatusFinder(configfile=self._configfile)

        def handle_status(update, context):
            msg = self.steamstatusfinder.get_status_string()
            context.bot.send_message(update.effective_chat.id, text=msg)
            return

        def handle_spammers(update, context):
            msg = 'Leave me in peace, spammers.'
            context.bot.send_message(update.effective_chat.id, text=msg)
            return

        handlers = {'status': handle_status,
                    'tell_off': handle_spammers}
        return handlers

    def define_job_queue(self):
        if not hasattr(self, 'steamstatusfinder'):
            self.steamstatusfinder = SteamStatusFinder(configfile=self._configfile)

        is_playing_r6s = self.steamstatusfinder.get_is_playing()

        msg = ''
        do_display = False
        for key in is_playing_r6s.keys():
            old_status = self.user_status[key]
            new_status = is_playing_r6s[key]

            if not (new_status == old_status):
                do_display = True
                verb = 'started' if new_status else 'stopped'
                msg += '{} {} playing R6S\n'.format(key, verb)

            self.user_status[key] = new_status

        return do_display, msg

    def configure_bot(self):
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

        def _callback_status(context):
            print('running job queue...')

            do_display, msg = self.define_job_queue()

            if do_display:
                logging.info('    sending message: {}'.format(msg))
                context.bot.send_message(chat_id=int(self.config['chat_id']), text=msg)
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
                out.append('{}:\tStatus \"{}\" and playing \"{}\"'.format(
                    key, states[int(status[key]['personastate'])], status[key]['gameextrainfo']))
            else:
                out.append('{}:\tStatus \"{}\" '.format(
                    key, states[int(status[key]['personastate'])]))
        return '\n'.join(out)

    def get_is_playing(self):
        if not hasattr(self, 'steam_api'):
            self.connect()
        states = self.config['personastates']
        status = self._get_user_status()

        is_pl = {key: 'gameid' in status[key].keys() for key in status.keys()}

        is_pl_r6 = {key: True if is_pl[key] and status[key]['gameid']
                    in self.config['game_steam_id'] else False for key in status.keys()}

        return is_pl_r6

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
