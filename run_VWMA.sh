#!/bin/bash

# Get symbol from command line argument, default to SOL if not provided
SYMBOL=${1:-SOL}

docker-compose run --rm freqtrade download-data --exchange bybit --pairs ${SYMBOL}/USDT:USDT --timeframes 15m 1h 4h --days 900 --trading-mode futures 

# docker-compose run --rm freqtrade hyperopt \
#     --config user_data/config.json \
#     --strategy VWMAStrategy \
#     --hyperopt-loss SortinoHyperOptLoss \
#     --spaces buy stoploss \
#     --epochs 300 \
#     --pair ${SYMBOL}/USDT:USDT \
#     --timeframe 15m \
#     --timerange 20250101-20250301 \
#     -j -1



# docker-compose run --rm freqtrade hyperopt \
#     --config user_data/config.json \
#     --strategy VWMAStrategyShort \
#     --hyperopt-loss SortinoHyperOptLoss \
#     --spaces sell stoploss \
#     --epochs 300 \
#     --pair ${SYMBOL}/USDT:USDT \
#     --timeframe 15m \
#     --timerange 20250101-20250301 \
#     -j -1





python3 walk_forward_test.py \
--insample-days 120 \
--outsample-days 30 \
--num-walks 12 \
--epochs 1000 \
--strategy VWMAStrategy \
--spaces buy stoploss \
--pair ${SYMBOL}/USDT:USDT \
--generate-report \
--timeframe 15m \
--hyperopt-loss SortinoHyperOptLoss


python3 walk_forward_test.py \
--insample-days 120 \
--outsample-days 30 \
--num-walks 12 \
--epochs 1000 \
--strategy VWMAStrategyShort \
--spaces sell stoploss \
--pair ${SYMBOL}/USDT:USDT \
--generate-report \
--timeframe 15m \
--hyperopt-loss SortinoHyperOptLoss

say "completed walk forward"