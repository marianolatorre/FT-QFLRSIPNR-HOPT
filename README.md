
# Freqtrade Strategy Testing & Analysis Suite

A comprehensive framework for algorithmic trading strategy development, testing, and validation with Freqtrade. This repository provides two complementary systems for rigorous strategy analysis:

## 🧪 **Experiment Management System** (`experiments/`)
**Stage-1 strategy validation and parameter optimization**
- **In-Sample/Out-of-Sample Testing**: Controlled methodology for strategy validation
- **Multi-Dimensional Analysis**: Compare strategies across time periods, assets, timeframes, hyperopt spaces, and loss functions
- **Batch Experiment Processing**: Run dozens of experiments unattended with automated CSV tracking
- **Parameter Narrowing**: Quickly identify optimal settings before expensive walk forward testing
- **Configurable Loss Functions**: Test with Sharpe, Sortino, Calmar, and custom optimization objectives

## 🚀 **Walk Forward Testing System** (root)
**Full rolling window validation for production-ready strategies**
- **Automated Time-Series Cross-Validation**: Rolling window walk forward analysis
- **Multi-Asset Support**: Test any trading pair with automatic data download and validation
- **Interactive Charts**: Generate profit charts for both in-sample and out-of-sample periods
- **Comprehensive Reporting**: Detailed HTML reports with performance metrics and chart links

## 📊 **Recommended Workflow**
1. **Stage 1**: Use `experiments/` to rapidly test and compare strategy variations
2. **Stage 2**: Use walk forward testing on promising strategies identified in Stage 1
3. **Stage 3**: Deploy validated strategies to live trading

## Features

- **Hyperopt Integration**: Automatic parameter optimization using Freqtrade's hyperopt
- **Multi-Strategy Support**: Compatible with different hyperopt spaces (buy/sell, roi/stoploss, etc.)
- **Docker Support**: Full containerized environment for consistent testing
- **Numbered Experiment Tracking**: Sequential experiment folders prevent conflicts and enable easy comparison

## Requirements

- Docker Desktop installed
- Python 3.8+
- At least 8GB RAM for large datasets

## Installation

1. **Download docker-compose.yml**
   ```bash
   curl https://raw.githubusercontent.com/freqtrade/freqtrade/stable/docker-compose.yml -o docker-compose.yml
   ```

2. **Pull the freqtrade image**
   ```bash
   docker compose pull
   ```

3. **Create user directory structure**
   ```bash
   docker compose run --rm freqtrade create-userdir --userdir user_data
   ```

4. **Create configuration**
   ```bash
   docker compose run --rm freqtrade new-config --config user_data/config.json
   ```

## Data Setup

### Data Requirements for Walk Forward Testing

Walk forward testing requires sufficient historical data to cover all time periods. Calculate your data needs:
- **Total days needed** = (insample-days + outsample-days) × num-walks + startup buffer
- **Example**: 12 walks with 120-day in-sample + 30-day out-of-sample = ~1800 days minimum

### Futures Trading (Recommended)

**For extensive walk forward testing (1000+ days)**:
```bash
docker-compose run --rm freqtrade download-data --exchange bybit --pairs BTC/USDT:USDT --timeframes 1h --days 1000 --trading-mode futures --erase
```

**For basic testing (1 year)**:
```bash
docker-compose run --rm freqtrade download-data --exchange bybit --pairs BTC/USDT:USDT --timeframes 1h --days 365 --trading-mode futures
```

### Spot Trading
```bash
docker-compose run --rm freqtrade download-data --exchange binance --pairs BTC/USDT --timeframes 1h --days 365 --trading-mode spot
```

### Important: Data Coverage Issues

⚠️ **Always use `--erase` for large data downloads**. Without it, Freqtrade only downloads from the end of existing data to present, which may create gaps:

```bash
# ❌ Wrong - may create data gaps
docker-compose run --rm freqtrade download-data --pairs BTC/USDT:USDT --days 1000

# ✅ Correct - ensures complete historical coverage
docker-compose run --rm freqtrade download-data --pairs BTC/USDT:USDT --days 1000 --erase
```

If your walk forward test fails with "ValueError: min() iterable argument is empty", check that your data covers the required date ranges for all walks.

### Multi-Asset Data Download

Walk forward testing automatically downloads missing data for the specified pair. Ensure the pair is in your config.json whitelist:

```bash
# The system will automatically download data for the specified pair
python3 walk_forward_test.py --pair SOL/USDT:USDT --timeframe 1h --insample-days 30 --outsample-days 15 --num-walks 3
```

**Config Validation**: The system validates that `--pair` exists in your `config.json` pair_whitelist before proceeding and provides helpful error messages with configuration examples if not found.

## Usage

### Walk Forward Testing

The walk forward test automatically performs hyperopt optimization followed by backtesting across time periods.

#### Parameters

- `--insample-days` - Length of the training period (hyperopt optimization)
- `--outsample-days` - Length of the testing period (out-of-sample validation)
- `--num-walks` - Number of walk forward iterations to perform
- `--timeframe` - **REQUIRED** - Timeframe for analysis (e.g., 1h, 4h, 1d, 15m)
- `--epochs` - Number of hyperopt optimization epochs per walk (default: 200)
- `--strategy` - Strategy name to test (default: QFLRSI_Strategy)
- `--spaces` - Hyperopt spaces to optimize (default: buy sell)
- `--generate-report` - Generate comprehensive HTML report after completion
- `--pair` - Trading pair to test (default: BTC/USDT:USDT)
- `--hyperopt-loss` - Optimization objective function (default: SharpeHyperOptLoss)
- `--config` - Configuration file path (default: user_data/config.json)
- `--end-date` - End date for testing in YYYYMMDD format (default: today)

#### Basic Usage
```bash
python3 walk_forward_test.py --insample-days 30 --outsample-days 15 --num-walks 3 --timeframe 1h --pair BTC/USDT:USDT
```

#### Strategy Examples

**QFLRSI_Strategy (Buy/Sell Spaces)**
```bash
python3 walk_forward_test.py \
    --insample-days 30 \
    --outsample-days 15 \
    --num-walks 3 \
    --timeframe 1h \
    --epochs 400 \
    --strategy QFLRSI_Strategy \
    --spaces buy sell \
    --pair BTC/USDT:USDT \
    --generate-report
```

**QFL_Strategy_SLTP (ROI/Stoploss Optimization)**
```bash
python3 walk_forward_test.py \
    --insample-days 30 \
    --outsample-days 15 \
    --num-walks 3 \
    --timeframe 1h \
    --epochs 400 \
    --strategy QFL_Strategy_SLTP \
    --spaces buy roi stoploss \
    --pair BTC/USDT:USDT \
    --generate-report
```

**Multi-Asset Examples**
```bash
# Test SOL/USDT:USDT perpetuals
python3 walk_forward_test.py \
    --insample-days 30 \
    --outsample-days 15 \
    --num-walks 3 \
    --timeframe 1h \
    --strategy QFLRSI_Strategy \
    --pair SOL/USDT:USDT \
    --generate-report

# Test DOGE/USDT:USDT perpetuals
python3 walk_forward_test.py \
    --insample-days 30 \
    --outsample-days 15 \
    --num-walks 3 \
    --timeframe 1h \
    --strategy QFLRSI_Strategy \
    --pair DOGE/USDT:USDT \
    --generate-report
```

### Manual Operations

#### Individual Backtest
```bash
docker-compose run --rm freqtrade backtesting \
    --config user_data/config.json \
    --strategy QFLRSI_Strategy \
    --pairs BTC/USDT:USDT \
    --timeframe 1h \
    --timerange 20250609- \
    --export trades
```

#### Manual Hyperopt
```bash
docker-compose run --rm freqtrade hyperopt \
    --config user_data/config.json \
    --strategy QFLRSI_Strategy \
    --pairs BTC/USDT:USDT \
    --hyperopt-loss SharpeHyperOptLoss \
    --spaces buy sell \
    --epochs 200 \
    --timeframe 1h \
    --timerange 20250308-20250608 \
    -j -1
```

#### View Hyperopt Results
```bash
docker-compose run --rm freqtrade hyperopt-show -n -1
```

## Strategies

### QFLRSI_Strategy
- **Hyperopt Spaces**: `buy sell`
- **Description**: QFL (Quickfingers Luc) strategy with RSI confirmation
- **Parameters**: RSI periods, QFL levels, buy/sell signal optimization

### QFL_Strategy_SLTP
- **Hyperopt Spaces**: `buy roi stoploss`
- **Description**: QFL strategy with optimized stop-loss and take-profit levels
- **Parameters**: ROI table optimization, dynamic stoploss, entry signal timing

## Output Files

### Walk Forward Results
- `walk_forward_results/[timestamp]/` - Complete walk forward analysis
- `combined_results.json` - Aggregated performance metrics
- `hyperopt_walk_[n].json` - Hyperopt results for each walk
- `backtest_walk_[n].json` - Backtest results for each walk
- `walk_forward_report.html` - Professional HTML report (generated with `--generate-report`)

### Backtest Results
- `user_data/backtest_results/` - Individual backtest files
- Preserved across runs (no automatic cleanup)

## Web Interface

Start the Freqtrade web UI:
```bash
docker-compose up -d freqtrade
```

Access at: http://localhost:8080

Stop the service:
```bash
docker-compose down
```

## Troubleshooting

### Common Issues

1. **Memory Issues**: Reduce epochs or time ranges for large datasets
2. **Docker Permissions**: Ensure Docker has proper permissions
3. **Data Availability**: Verify data exists for specified time ranges

### Cleaning Up

Clean all results directories before starting fresh tests:
```bash
./clean_results.sh
```

This script safely removes all files from:
- `user_data/backtest_results/` - Backtest result files
- `user_data/hyperopt_results/` - Hyperopt optimization files  
- `user_data/plot/` - Generated chart files
- `walk_forward_results/` - Walk forward analysis results

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

This project follows the same license as Freqtrade.

## Support

For issues related to:
- Freqtrade core functionality: [Freqtrade GitHub](https://github.com/freqtrade/freqtrade)
- Walk forward testing: Create an issue in this repository