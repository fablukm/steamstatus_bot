# steamstatus_bot
Telegram Bot to check availability of steam users, for squads organised in Telegram group chats.

# Dependencies
Requires packages `steam` and `python-telegram-bot` for functionality, `logging` and `json` for convenience.

# Get started
If you want to use this bot, you need to be able to host it. [Here](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Where-to-host-Telegram-Bots) is a nice overview.

Edit the config.json file to your requirements. 
1. Get your [Steam API token](https://steamcommunity.com/dev/apikey) and enter it to `config.json`.
2. Find your friends' [Steam User ID](https://support.ubi.com/en-GB/Faqs/000027522/Finding-your-Steam-ID) and enter it to `config.json` in dictionary format: 
In the field `player_steam_ids` replace `UserName` by the name of the user and `UserID` by the Steam ID you have found.
3. Now you need to configure your bot. Open Telegram, connect to @BotFather.
