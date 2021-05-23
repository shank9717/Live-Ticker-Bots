import math
from threading import Thread

import cogs.Stats.constants as constants
import cogs.Stats.tv_helper as tv_helper

def main(stock):
    results = {}
    thread = Thread(target=tv_helper.main, args=(stock.replace('&', '_'), results), daemon=True)
    thread.start()

def millify(n):
    n = float(n)
    millidx = max(0, min(len(constants.MILLNAMES) - 1,
                         int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))))
    return '{:.3f}{}'.format(n / 10 ** (3 * millidx), constants.MILLNAMES[millidx])
