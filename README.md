
# Requirements

Docker desktop installed.

# Installation

Download docker-compose.yml
```
curl https://raw.githubusercontent.com/freqtrade/freqtrade/stable/docker-compose.yml -o docker-compose.yml
```
Pull the freqtrade image
```
docker compose pull
```

Create user directory structure
```
docker compose run --rm freqtrade create-userdir --userdir user_data
```

Create configuration - Requires answering interactive questions
```
docker compose run --rm freqtrade new-config --config user_data/config.json
```


# Steps


## Download data

I recommend trying with Futures, since the rest of the steps are already implemented for futures.

### Spot
```
docker-compose run --rm freqtrade download-data --exchange binance --pairs BTC/USDT --timeframes 1h --days 15 --trading-mode spot
```
### Futures
Let's download a year of data for BTC perps on Bybit:
```
docker-compose run --rm freqtrade download-data --exchange bybit --pairs BTC/USDT:USDT --timeframes 1h --days 365 --trading-mode futures
```

## Run backtest

If you want to backtest a specific period you can use the below or skip it if you only want to test walk forward.
 ```
docker-compose run --rm freqtrade backtesting --config user_data/config_spot.json --strategy QFLRSI_Strategy --timeframe 1h --timerange 20250609- --export trades
```

## Server up/down
This includes the webserver. `docker-compose.yml` and `user_data/config.json` are configured for backtesting and web UI.

```
docker-compose up -d freqtrade
docker-compose down  
```

## Clean backtest results
Healthy to keep it clean before running a WF that will produce many backtest files.
```
rm -rf user_data/backtest_results/*
```

## Hyperopt
Run hyperopt manually:
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
Check the best results right after hyperopt:
```
docker-compose run --rm freqtrade hyperopt-show -n -1
```


## Walk forward

Example of running the WF with 3 out-of-sample walks of 30 days and validating with 15 days in-sample.
```
python3 walk_forward_test.py --insample-days 30 --outsample-days 15 --num-walks 3      
```