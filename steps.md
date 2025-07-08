

# Steps


## Download data
Spot
```
docker-compose run --rm freqtrade download-data --exchange binance --pairs BTC/USDT --timeframes 1h --days 15 --trading-mode spot
```
Futures
```
docker-compose run --rm freqtrade download-data --exchange bybit --pairs BTC/USDT:USDT --timeframes 1h --days 365 --trading-mode futures
```

## Run backtest

 ```
docker-compose run --rm freqtrade backtesting --config user_data/config_spot.json --strategy QFLRSI_Strategy --timeframe 1h --timerange 20250609- --export trades
```

## Server up/down
```
docker-compose up -d freqtrade

docker-compose down  
```

## Clean backtest results
```
rm -rf user_data/backtest_results/*
```

## Hyperopt
Run hyperopt
```
docker-compose run --rm freqtrade hyperopt \
      --config user_data/config_spot.json \
      --strategy QFLRSI_Strategy \
      --hyperopt-loss SharpeHyperOptLoss \
      --spaces buy sell \
      --epochs 200 \
      --timeframe 1h \
      --timerange 20250308-20250608 \
      -j -1
```
Check best results
```
docker-compose run --rm freqtrade hyperopt-show -n -1
```


Run backtest with best hyperopt results
```
docker-compose run --rm freqtrade backtesting --config user_data/config_spot.json --strategy QFLRSI_Strategy --timeframe 1h --timerange 20250609- --export trades --hyperopt-list-best 1
```