# Freqtrade Experiment Management System

A comprehensive system for running, logging, and analyzing freqtrade experiments with automated reporting and CSV tracking.

## 🎯 **What This System Does**

This experiment framework implements a **controlled in-sample/out-of-sample testing methodology** for algorithmic trading strategies. Each experiment:

1. **Optimizes** strategy parameters using hyperoptimization on a defined in-sample period
2. **Tests** the optimized parameters on a subsequent out-of-sample period  
3. **Measures** true out-of-sample performance to validate strategy robustness
4. **Reports** results in both detailed HTML reports (per experiment) and consolidated CSV format (for comparison across all experiments)

## 🔬 **Key Capabilities**

### **Multi-Dimensional Strategy Analysis**
- **Multiple time periods**: Test same strategy across different market conditions
- **Multiple assets**: Compare performance across different trading pairs
- **Multiple timeframes**: Validate strategies on different chart intervals
- **Multiple optimization spaces**: Compare buy-only vs buy/sell vs ROI-based optimization
- **Multiple loss functions**: Evaluate using Sharpe, Sortino, Calmar, or custom metrics

### **Stage-1 Walk Forward Testing**
This system performs **single-step walk forward analysis** - a crucial preliminary stage before full rolling window walk forwards:
- **Fast iteration**: Quickly test multiple configurations without the time cost of full walk forwards
- **Parameter narrowing**: Identify optimal settings (epochs, spaces, loss functions) for your strategies
- **Comparative analysis**: Systematically compare different approaches on the same time period
- **Risk validation**: Ensure strategies perform well out-of-sample before committing to longer backtests

## ✅ **What You Can Do**
- **Isolate variables**: Test one change at a time (different loss functions, optimization spaces, etc.)
- **Compare strategies**: Run multiple strategies under identical conditions
- **Optimize settings**: Find the best hyperopt configuration before running expensive walk forwards
- **Validate robustness**: Ensure strategies work on unseen data (out-of-sample period)
- **Batch processing**: Run dozens of experiments unattended with automated CSV tracking

## ❌ **What This System Cannot Do**
- **Full walk forward**: This is single-step testing, not rolling window analysis
- **Live trading**: Results are purely backtested, no live execution
- **Real-time optimization**: Parameters are optimized once, not continuously adapted
- **Market regime detection**: No automatic adaptation to changing market conditions

## 🚀 **When to Use This System**
- **Before** running expensive full walk forwards to narrow down optimal settings
- **When** comparing multiple strategies or strategy variations
- **For** validating that your strategy optimizations generalize to unseen data
- **To** systematically test different hyperopt configurations (spaces, loss functions, epochs)

## 📁 Directory Structure

```
experiments/
├── README.md                   # This file
├── experiments.conf            # Configuration file for experiments
├── scripts/                    # All executable scripts
│   ├── cleanup.sh             # Empty outputs folder
│   ├── generate_report.py     # Generate HTML reports and CSV data
│   ├── run_all_experiments.py # Main Python orchestrator script
│   ├── run_all_experiments.sh # Legacy bash orchestrator script
│   ├── run_experiment.py      # Python individual experiment runner
│   ├── run_experiment.sh      # Legacy bash experiment runner
│   └── view_report.py         # Helper for viewing HTML reports
└── outputs/                   # All experiment results
    ├── summary.csv            # Consolidated CSV with all results
    └── {EXP_NUM}.{STRATEGY}/  # Numbered strategy-specific results
        └── {PAIR}/            # Pair-specific results
            └── {TIMEFRAME}/   # Timeframe-specific results
                └── {TIMESTAMP}/   # Individual experiment run
                    ├── run.log        # Full execution log
                    ├── report.html    # HTML report
                    ├── {STRATEGY}.json # Optimization parameters
                    └── *.json         # Backtest result files
```

## 🚀 Quick Start

### 1. Configure Experiments

Edit `experiments.conf` to define your experiments. Each line should contain:
```
STRATEGY PAIR TIMEFRAME START_DATE IS_LENGTH OOS_LENGTH EPOCHS SPACES LOSS_FUNCTION
```

**Example:**
```
VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10 buy,stoploss SharpeHyperOptLoss
VWMAStrategy BTC/USDT:USDT 1h 20250101 60 15 20 buy,roi,stoploss SortinoHyperOptLoss
RPSExitSignal BTC/USDT:USDT 15m 20241101 90 30 100 buy,sell,stoploss SharpeHyperOptLoss
```

### 2. Run Experiments

```bash
# Run all experiments from config file (Python orchestrator - recommended)
python3 experiments/scripts/run_all_experiments.py

# Run with verbose output (shows all freqtrade commands)
python3 experiments/scripts/run_all_experiments.py --verbose

# Alternative: Bash orchestrator (legacy)
./experiments/scripts/run_all_experiments.sh

# Run a single experiment
python3 experiments/scripts/run_experiment.py VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10 buy,stoploss SharpeHyperOptLoss
```

### 3. View Results

```bash
# View consolidated CSV results
cat experiments/outputs/summary.csv

# View latest HTML report
python3 experiments/scripts/view_report.py

# View specific HTML report
python3 experiments/scripts/view_report.py experiments/outputs/VWMAStrategy/DOGE-USDT-USDT/15m/2025-07-16_13-50-26/report.html
```

## 📊 Output Files

### Summary CSV (`outputs/summary.csv`)
Consolidated results from all experiments with columns:
- `experiment_num` - Sequential experiment number (1, 2, 3, etc.)
- `strategy` - Strategy name
- `pair` - Trading pair
- `timeframe` - Timeframe used
- `start_date` - Start date of the experiment (YYYYMMDD format)
- `IS_days` - In-sample period length in days
- `OOS_days` - Out-of-sample period length in days
- `epochs` - Number of epochs used in hyperoptimization
- `Status` - Success/Failed status
- `Total profit %` - Total profit percentage
- `Max Drawdown (Acct)` - Maximum drawdown
- `Sortino` - Sortino ratio
- `Sharpe` - Sharpe ratio
- `Calmar` - Calmar ratio
- `Profit factor` - Profit factor
- `Trades` - Number of trades
- `Win %` - Win percentage
- `stoploss` - Optimized stoploss value
- `buy_params` - Optimized buy parameters (JSON)
- `sell_params` - Optimized sell parameters (JSON)
- `roi_params` - Optimized ROI parameters (JSON)

### Individual Experiment Results
Each experiment creates a timestamped directory containing:
- **`run.log`** - Complete execution log with all freqtrade output
- **`report.html`** - Formatted HTML report with metrics and full log
- **`*.json`** - Raw backtest result files from freqtrade

## 📋 Available Scripts

### `run_all_experiments.py`
**Main orchestrator script (Python - recommended)**
- Reads `experiments.conf` line by line (9 parameters per line)
- Executes individual experiments sequentially with proper error handling
- Creates numbered experiment folders (1.Strategy, 2.Strategy, etc.)
- Appends results to `summary.csv` with experiment numbers
- Creates CSV headers if file doesn't exist
- Supports `--verbose` mode to show all freqtrade commands
- Better process management and output capturing than bash version
- Continues processing even if individual experiments fail
- Passes experiment index and loss function to run_experiment.py

### `run_all_experiments.sh`
**Legacy bash orchestrator script**
- Same functionality as Python version but with shell scripting limitations
- Kept for backward compatibility

### `run_experiment.py`
**Individual experiment runner (Python - recommended)**
- Accepts 9 parameters: strategy, pair, timeframe, start_date, is_length, oos_length, epochs, spaces, loss_function, exp_index
- Creates numbered timestamped output directory: `{exp_index}.{strategy}/{pair}/{timeframe}/{timestamp}/`
- Runs hyperopt with configurable loss function (SharpeHyperOptLoss, SortinoHyperOptLoss, etc.)
- Runs OOS backtesting with optimized parameters
- Logs all output to `run.log`
- Copies backtest JSON files and optimization parameters
- Calls generate_report.py with experiment index
- Supports `--verbose` flag for debugging

### `run_experiment.sh`
**Legacy individual experiment runner (bash)**
- Original bash version with 7 parameters
- Runs hyperopt + backtesting for both long and short strategies
- Creates timestamped output directory
- Logs all output to `run.log`
- Copies backtest JSON files
- Generates HTML report

### `generate_report.py`
**Report generation utility**
- Accepts 3 parameters: experiment_directory, primary_strategy_name, experiment_index
- Parses freqtrade logs for key metrics
- Generates HTML reports with tables and full logs
- Outputs CSV data row for summary file with experiment number as first column
- Handles multiple strategies per experiment
- Includes optimization parameters (buy_params, sell_params, roi_params) in CSV output
- Extracts loss function from logs

### `view_report.py`
**HTML report viewing helper**
- Finds latest HTML report if no path specified
- Provides file URL for easy access
- Useful for Puppeteer MCP integration

### `cleanup.sh`
**Cleanup utility**
- Empties the entire `outputs/` directory
- Prepares for fresh experiment runs
- Keeps directory structure intact

## 🔄 Behavior Notes

### Append vs Replace
- **Summary CSV**: Results are **APPENDED** to existing file
- **Individual runs**: Each run creates a **NEW** numbered and timestamped directory (e.g., `1.Strategy/`, `2.Strategy/`)
- **Multiple runs**: Will accumulate results over time
- **Experiment numbering**: Sequential numbers prevent folder conflicts when running same strategy with different parameters

### Error Handling
- Failed experiments continue gracefully (`|| true`)
- Empty results don't break CSV generation
- Missing data shows as empty cells in CSV

## 🛠️ Prerequisites

### Required Software
- **Docker** - Must be running for freqtrade commands
- **Python 3** - For report generation scripts
- **Bash** - For orchestrator scripts

### Required Files
- `user_data/config.json` - Freqtrade configuration
- Strategy files in `user_data/strategies/`
- Market data in `user_data/data/`

## 📖 Usage Examples

### Basic Usage
```bash
# Clean previous results
./experiments/scripts/cleanup.sh

# Run all configured experiments (Python - recommended)
python3 experiments/scripts/run_all_experiments.py

# Check results
cat experiments/outputs/summary.csv
```

### Single Experiment
```bash
# Run one experiment manually (Python)
python3 experiments/scripts/run_experiment.py VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10 buy,stoploss SharpeHyperOptLoss 1

# Or legacy bash version
./experiments/scripts/run_experiment.sh VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10

# View the generated report
python3 experiments/scripts/view_report.py
```

### Multiple Strategies
Add multiple lines to `experiments.conf`:
```
VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10 buy,stoploss SharpeHyperOptLoss
VWMAStrategyV2 DOGE/USDT:USDT 15m 20250201 90 30 10 buy,sell,stoploss SortinoHyperOptLoss
ScalpHybridStrategy BTC/USDT:USDT 5m 20250101 60 15 20 buy,roi,stoploss CalmarHyperOptLoss
```

### Viewing HTML Reports with Puppeteer MCP
```bash
# Get report URL
python3 experiments/scripts/view_report.py

# In Claude Code with Puppeteer MCP:
# 1. Navigate to the file:// URL
# 2. Take screenshot to view formatted report
```

## 📝 Configuration Format

### experiments.conf
Space-separated format with 9 parameters:
```
STRATEGY PAIR TIMEFRAME START_DATE IS_LENGTH OOS_LENGTH EPOCHS SPACES LOSS_FUNCTION
```

**Parameters:**
- `STRATEGY` - Strategy class name (e.g., `VWMAStrategy`)
- `PAIR` - Trading pair (e.g., `DOGE/USDT:USDT`)
- `TIMEFRAME` - Timeframe (e.g., `15m`, `1h`, `4h`)
- `START_DATE` - Start date for the in-sample period (e.g., `20250201`)
- `IS_LENGTH` - In-sample period length in days (e.g., `90`)
- `OOS_LENGTH` - Out-of-sample period length in days (e.g., `30`)
- `EPOCHS` - Number of epochs for hyperoptimization (e.g., `10`)
- `SPACES` - Comma-separated hyperopt spaces (e.g., `buy,sell,stoploss` or `buy,roi,stoploss`)
- `LOSS_FUNCTION` - Hyperopt loss function (e.g., `SharpeHyperOptLoss`, `SortinoHyperOptLoss`, `CalmarHyperOptLoss`)

**Important:** Each line must end with a newline character for proper parsing.

## 🐛 Troubleshooting

### Common Issues

**No data in summary.csv**
- Check if `experiments.conf` has proper newlines
- Verify Docker is running
- Check individual `run.log` files for errors

**HTML reports not loading**
- Use `python3 experiments/scripts/view_report.py` for correct file URLs
- Check that experiment completed successfully

**Permission errors**
- Ensure scripts are executable: `chmod +x experiments/scripts/*.sh`
- Check Docker permissions

### Debug Mode
Add debugging to orchestrator:
```bash
# Edit run_all_experiments.sh and add at the top:
set -x  # Enable debug output
```

## 🔍 Integration Notes

### For Agents/Automation
- Scripts are designed for programmatic use
- All output is logged and parseable
- CSV format is consistent and machine-readable
- HTML reports can be viewed with Puppeteer MCP

### For Human Users
- HTML reports provide visual summaries
- CSV files can be opened in spreadsheet software
- Log files contain complete execution details
- Cleanup script prepares for fresh runs

---

**Created by:** Claude Code Agent  
**Version:** 2.0  
**Last Updated:** July 2025  
**Major Updates in v2.0:**
- Added Python orchestrator with numbered experiment folders
- Configurable hyperopt loss functions
- Configurable hyperopt spaces
- Enhanced CSV output with experiment numbers and optimization parameters
- Verbose mode support for debugging