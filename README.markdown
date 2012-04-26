# A Re-Stocking Bot for the Browser Game "Economics of Scale"
## http://www.ratjoy.com/eos/

Requires: 
* Python 2.7 (probably works 2.6 onwards, but untested)
* BeatifulSoup4.

Based on Senso's bot (https://github.com/Senso/eos-bot), this bot:

Checks the total qty of each product in a store and if total qty < than configured min value will buy the configured amount of said stock from the import market.

Configuration is in json and should be fairly straight forward to understand.

I'm running the script once an hour as a scheduled task on windows 7 (called from batch file), you can do something similar with your OS of choice.