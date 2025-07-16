# download data
```
docker-compose run --rm freqtrade download-data --exchange bybit --pairs XRP/USDT:USDT --timeframes 15m 1h 4h --days 900 --trading-mode futures
```

# check for repainting
```
freqtrade lookahead-analysis --strategy VWMAStrategy --timerange 20240101-20240201
```

# Strategies 
1. long - VWMAStrategy
2. short - VWMAStrategyShort


# Long backtest
```
docker-compose run --rm freqtrade backtesting \
--config user_data/config.json \
--strategy VWMAStrategy \
--pair BTC/USDT:USDT \
--timeframe 15m \
--timerange 20250601-20250701 \
--export trades
```
# Short backtest
```
docker-compose run --rm freqtrade backtesting \
--config user_data/config.json \
--strategy VWMAStrategyShort \
--pair BTC/USDT:USDT \
--timeframe 15m \
--timerange 20250601-20250701 \
--export trades
```
# hyperopt long
```
docker-compose run --rm freqtrade hyperopt \
--config user_data/config.json \
--strategy VWMAStrategy \
--hyperopt-loss SortinoHyperOptLoss \
--spaces buy stoploss \
--epochs 1000 \
--pair BTC/USDT:USDT \
--timeframe 15m \
--timerange 20250301-20250601 \
-j -1
```
# hyperopt short
```
docker-compose run --rm freqtrade hyperopt \
--config user_data/config.json \
--strategy VWMAStrategyShort \
--hyperopt-loss SortinoHyperOptLoss \
--spaces sell stoploss \
--epochs 1000 \
--pair BTC/USDT:USDT \
--timeframe 15m \
--timerange 20250301-20250601 \
-j -1
```



# Walk forward long
```
./clean_results.sh;
python3 walk_forward_test.py \
--insample-days 120 \
--outsample-days 30 \
--num-walks 6 \
--epochs 1000 \
--strategy VWMAStrategy \
--spaces buy stoploss \
--pair BTC/USDT:USDT \
--generate-report \
--timeframe 15m \
--hyperopt-loss SortinoHyperOptLoss; 
say "completed walk forward"
```

# Walk forward short
```
./clean_results.sh;
python3 walk_forward_test.py \
--insample-days 120 \
--outsample-days 30 \
--num-walks 6 \
--epochs 1000 \
--strategy VWMAStrategyShort \
--spaces sell stoploss \
--pair BTC/USDT:USDT \
--generate-report \
--timeframe 15m \
--hyperopt-loss SortinoHyperOptLoss; 
say "completed walk forward"
```