# steamstatus_bot
Telegram Bot to check availability of steam users, for squads organised in Telegram group chats.

# Dependencies
Requires packages `steam` and `python-telegram-bot` for functionality, `logging` and `json` for convenience.

# Get started
If you want to use this bot, you need to be able to host it. [Here](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Where-to-host-Telegram-Bots) is a nice overview.

Edit the config.json file to your requirements as follows:
1. Get your [Steam API token](https://steamcommunity.com/dev/apikey) and enter it to `config.json`.
2. Find your friends' [Steam User ID](https://support.ubi.com/en-GB/Faqs/000027522/Finding-your-Steam-ID) and enter it to `config.json` in dictionary format:
In the field `player_steam_ids` replace `UserName` by the name of the user and `UserID` by the Steam ID you have found.
3. [Here is an official how-to](https://core.telegram.org/bots#6-botfather)
Now you need to configure your bot. Open Telegram, connect to @BotFather. Use `/newbot` to get a token. Enter the token to `config.json`.
4. To make sure the bot will be sending automatic updates to the correct group chat, add `chat_id` to the configuration in `config.json`. You can find instructions on how to get your group chat ID [here](https://stackoverflow.com/questions/32423837/telegram-bot-how-to-get-a-group-chat-id).
The configuration entry `time_interval` is the number of seconds after which the job queue (periodically executed tasks) will be executed again.
5. Start the bot with `python steam_status_bot.py` on the server and your bot is online. By default, the bot only know one command: `/status` will show a formatted string of the users you defined and their respective status.

# How to add new commands:
Open the source `steam_status_bot.py`. The bot is configured in the class `TelegramBot`. Its commands are defined in the method `set_commands(self)`.
1. Inside this method, define a function (syntax like the already implemented `handle_status(update, context)`) that defines the message the bot is returning.
2. Then, extend the dictionary `handlers` defined in the method `configure_bot`. Syntax is `handlers = {'SomeCommand': handle_some_command, 'SomeOtherCommand': handle_some_other_command}`.


# How to add new tasks to be executed periodically:
Open the source `steam_status_bot.py`. The bot is configured in the class `TelegramBot`. Its JobQueue is configured in the method `define_job_queue()`. For a project to be used by more than one group chat, the `self.user_status[]` should be adapted to use [context status variables](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Storing-user--and-chat-related-data).
In the current configuration, this method returns a boolean `do_display` that is set to `True` iff a message will be sent to the group chat, and the message itself in `msg`.

Have fun!
