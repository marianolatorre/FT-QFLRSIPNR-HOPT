./clean_results.sh; docker-compose run --rm freqtrade backtesting \
    --config user_data/config.json \
    --strategy QFL_Strategy_SLTP \
    --timeframe 1h \
    --timerange 20250101- \
    --export trades --pair DOGE/USDT:USDT




    docker-compose run --rm freqtrade hyperopt \
    --config user_data/config.json \
    --strategy QFL_Strategy_SLTP \
    --hyperopt-loss SharpeHyperOptLoss \
    --spaces buy roi stoploss \
    --epochs 400 \
    --pair DOGE/USDT:USDT \
    --timeframe 1h \
    --timerange 20250101- \
    -j -1





docker run --rm -v "$(pwd)/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai download-data  --config /freqtrade/user_data/config_freqai.json --timeframes 5m 15m 4h --timerange 20250101-20250708 --pairs  BTC/USDT --prepend



docker run --rm -v "$(pwd)/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai backtesting --config /freqtrade/user_data/config_freqai.json --strategy FreqAI_Simple_Strategy --timerange 20250101-20250301  --pairs BTC/USDT --freqaimodel LightGBMClassifier

docker-compose down

 docker-compose up -d