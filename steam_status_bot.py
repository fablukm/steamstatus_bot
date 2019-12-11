import telegram
from telegram.ext import Updater, CommandHandler
import logging
import json
import steam
from urllib.request import Request, urlopen
import os, sys
from datetime import datetime

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

    def __init__(self, configfile='./config.json'):
        # read config file
        self._configfile = configfile
        self.config = self.read_config()

        # open instances of external APIs
        self.steamstatusfinder = SteamStatusFinder(configfile=self._configfile)
        self.ubiserverpoller = UbiServerStatusFinder(
            configfile=self._configfile)
        self.tabwirepoller = R6TabPoller()

        # initial call to job queue callbacks
        self.user_status = self.steamstatusfinder.get_is_playing()
        self.server_status = self.ubiserverpoller.run_query()
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

    def set_commands(self):
        def handle_status(update, context):
            msg = self.steamstatusfinder.get_status_string()
            context.bot.send_message(update.effective_chat.id, text=msg)
            logging.info(f'Sent message {msg}')
            return

        def handle_server_status(update, context):
            msg = self.ubiserverpoller.get_message()
            logging.info(f'Sending message {msg}')
            context.bot.send_message(update.effective_chat.id, text=msg)
            return

        def handle_stats(update, context):
            msg = self.tabwirepoller.get_message()
            context.bot.send_message(update.effective_chat.id, text=msg)
            logging.info(f'Sent message {msg}')
            return

        def handle_help(update, context, DEBUG=False):
            helps = [r'I update this group chat whenever someone starts/stops playing, and/or the servers are down or up again.', '',
                     r'You can use the following commands, either here for everyone to see or in a private chat with me, the bot:',
                     r'    /player_status: Show who is playing and who is not.',
                     r'    /server_status: Show whether the servers are online.',
                     r'    /stats: Show basic statistics.',
                     r'    /help: Show this message.']
            msg = '\n'.join(helps)
            if DEBUG:
                print(msg)
            else:
                context.bot.send_message(update.effective_chat.id, text=msg)
            logging.info(f'Sent message {msg}')
            return

        handlers = {'player_status': handle_status,
                    'server_status': handle_server_status,
                    'stats': handle_stats,
                    'help': handle_help}
        return handlers

    def define_job_queue(self):
        msg = ''
        do_display = False

        # get momentaneous user status
        new_user_status_all = self.steamstatusfinder.get_is_playing()
        for user in new_user_status_all.keys():
            old_status = self.user_status[user]
            new_status = new_user_status_all[user]

            if not (new_status['is_pl'] == old_status['is_pl']):
                do_display = True
                verb = 'started' if new_status['is_pl'] else 'stopped'
                game = ' '+new_status['game'] if new_status['is_pl'] else ''
                msg += f'{user} {verb} playing{game}.\n'

        self.user_status = new_user_status_all

        # get momentaneous ubi server status
        new_server_status = self.ubiserverpoller.run_query()
        for game in new_server_status.keys():
            old_status = self.server_status[game]
            new_status = new_server_status[game]

            if not (new_status == old_status):
                msg += f'Servers for {game} are {new_status}.\n'
                do_display = True

        self.server_status = new_server_status

        return do_display, msg

    def configure_bot(self, DEBUG=False):
        '''
        TelegramBot.configure_bot(): Defines commands and reads job queue.
        '''
        # get all bot commands
        bot_commands = self.set_commands()

        # initialise updater
        telegram_token = self.config['telegram_bot_token']
        self.updater = Updater(token=telegram_token, use_context=True)
        self.dispatcher = self.updater.dispatcher

        # dispatch commands
        for key in bot_commands:
            self.dispatcher.add_handler(CommandHandler(key, bot_commands[key]))

        # Configure callback to job queue
        def _callback_status(context):
            logging.info('running job queue...')
            do_display, msg = self.define_job_queue()
            logging.debug(f'    message: {msg}')
            if do_display:
                logging.debug('    sending message.')

                if DEBUG:
                    print(msg)
                else:
                    context.bot.send_message(chat_id=int(self.config['chat_id']), text=msg)
                    logging.info(f'Sending message: {msg}')
            else:
                logging.debug('    no changes. not sending message.')
            return

        dt = int(self.config["time_interval"])
        job_queue = self.updater.job_queue
        job_queue.run_repeating(_callback_status, interval=dt)
        return

    def start_bot(self, mode):
        if not hasattr(self, 'updater'):
            self.configure_bot(DEBUG=False)

        if mode == 'dev':
            self.updater.start_polling()
            logging.info('Bot running in dev mode')
        elif mode == 'prod':
            PORT = int(os.environ.get("PORT", "8443"))
            HEROKU_APP_NAME = os.environ.get("HEROKU_APP_NAME")
            TOKEN = self.config['telegram_bot_token']
            self.updater.start_webhook(listen="0.0.0.0",
                                  port=PORT,
                                  url_path=TOKEN)
            self.updater.bot.set_webhook(f'https://{HEROKU_APP_NAME}.herokuapp.com/{TOKEN}')
            logging.info('Bot running in prod mode')
        else:
            logging.error("No MODE specified!")
            sys.exit(1)
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
        self.connect()
        return

    def read_config(self):
        try:
            with open(self._configfile, 'r') as handle:
                config = json.load(handle)
        except FileNotFoundError:
            logging.info(
                'SSF config File not found: {}'.format(self._configfile))
            raise FileNotFoundError(
                'File not found: {}'.format(self._configfile))
        return config

    def connect(self):
        # TODO: Error handling
        self.steam_api = steam.WebAPI(key=self.config['steam_api_token'])
        logging.info('Connected to Steam API.')
        return

    def get_status_string(self):
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
        states = self.config['personastates']
        status = self._get_user_status()

        # which games are checked
        game_ids = {self.config['game_ids'][game]['steam_id']: game
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
        ids = {user: self.config["player_ids"][user]["steam"]
               for user in self.config['player_ids'].keys()}
        token = self.config['steam_api_token']
        api = self.steam_api
        return {user:
                api.ISteamUser.GetPlayerSummaries(key=token,
                                                  steamids=ids[user])['response']['players'][0]
                for user in ids.keys()}


class UbiServerStatusFinder(object):
    '''
    UbiServerStatusFinder connects to the steam API and implements a status finder.


    args:
        configfile (str): path to the config.json file. Default: ./config.json

    methods:
        read_config(): Reads and loads the configuration from the file.
                       Returns: config (dict) with configuration.
        query(): Connects to the ubi server and finds status
        get_message(): Format results to a human-readable message

    Based on gist by Kjetil Lye, 2019
    '''

    def __init__(self, configfile='./config.json'):
        logging.info('Opening UbiServerStatusFinder instance')
        self._configfile = configfile
        self.config = self.read_config()
        
        self.server_status = {}
        self._last_update = datetime.now()

        self.url_base = 'https://game-status-api.ubisoft.com/v1/instances?appIds={game_id}'
        self.is_first_time = True
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

    def run_query(self, timeout=10):
        game_ids = self.config['game_ids']
        t_since_last = datetime.now() - self._last_update
        interval = float(self.config['ubipoller_interv_min'])
        sec_since_last = t_since_last.total_seconds()
        if (sec_since_last>interval*60) or self.is_first_time:
            logging.info('Getting new Server status for Ubisoft servers...')
            for game in self.config['game_ids'].keys():
                if (not 'ubi_id' in game_ids[game]):
                    continue

                url = self.url_base.format(game_id=game_ids[game]['ubi_id'])
                with urlopen(url, timeout=timeout) as request:
                    json_data = json.load(request)
                    self.server_status[game] = json_data[0]['Status']
            self.is_first_time = False
        else:
            logging.info(f'Only {sec_since_last//60} minutes since updates. Not polling again.')
        return self.server_status 

    def get_message(self):
        self.run_query()
        self.msg = '\n'.join(['{} servers are {}.'.format(game, status)
                         for game, status in self.server_status.items()])
        return self.msg


class R6TabPoller(object):
    def __init__(self, configfile='./config.json'):
        logging.info('Opening R6TabPoller instance')
        self._configfile = configfile
        self.config = self.read_config()
        self.url_base = 'http://r6tab.com/api/player.php?p_id={player_id}'
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

    def get_user_stats(self, timeout=10):
        users = {user: self.config['player_ids'][user]['uplay']
                 for user in self.config['player_ids'].keys()}
        urls = {user: self.url_base.format(player_id=users[user])
                for user in users.keys()}
        user_stats = {}
        for user in users.keys():
            url = urls[user]

            try:
                req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                response = json.load(urlopen(req, timeout=timeout))

                k, d = response['data'][6], response['data'][7]
                w, l = response['data'][8], response['data'][9]
                minplayed = response['data'][5]/60.0
            except URLError:
                logging.info("Connection error in attempt to connect to TabWire")
                k, d, w, l, minplayed = 0., 0., 0., 0., 0.

            user_stats[user] = gen_stats(k, d, w, l, minplayed)
        return user_stats

    def get_message(self):
        user_stats = self.get_user_stats()
        msgs = ['{}: \tW/L: {}, \tK/D: {}, \tWinrate: {}, \tMin/Kill: {}'.format(
            user,
            user_stats[user]['wl'],
            user_stats[user]['kd'],
            user_stats[user]['winrate'],
            user_stats[user]['minperkill']) for user in user_stats.keys()]
        msg = '\n'.join(msgs)
        return msg


def gen_stats(k, d, w, l, minplayed):
    kd = float(k)/float(d) if float(d) > 0. else 0.
    wl = float(w)/float(l) if float(l) > 0. else 0.
    winrate = float(w)/(float(w)+float(l)) if float(w)+float(l) > 0. else 0.

    mpk = float(minplayed)/float(k) if float(k) > 0. else 0.
    return {'kd': round2(kd),
            'wl': round2(wl),
            'winrate': round2(winrate),
            'minperkill': round2(mpk)}


def round2(x):
    return float(str(x)[:4])


if __name__ == '__main__':
    mode = 'dev'
    configfile = './config.json'
    telegram_bot = TelegramBot(configfile=configfile)
    telegram_bot.start_bot(mode)
