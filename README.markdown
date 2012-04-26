# A re-stocking bot for the browser game Economeis of Scale

Requires: python 2.7 (probably works 2.6 onwards, but untested) and BeatifulSoup4.

Based on senso's bot, this bot:

Checks the total qty of each product in a store and if total qty < than configured min value will buy the configured amount of said stock from the import market.

Configuration is in json and should be fairly straight forward to understand.

I'm running the script once an hour as a scheduled task on windows 7, you can do something similar with your OS of choice.