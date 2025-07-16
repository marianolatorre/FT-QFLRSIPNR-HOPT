# Freqtrade Experiment Management System

A comprehensive system for running, logging, and analyzing freqtrade experiments with automated reporting and CSV tracking.

## 📁 Directory Structure

```
experiments/
├── README.md                   # This file
├── experiments.conf            # Configuration file for experiments
├── scripts/                    # All executable scripts
│   ├── cleanup.sh             # Empty outputs folder
│   ├── generate_report.py     # Generate HTML reports and CSV data
│   ├── run_all_experiments.sh # Main orchestrator script
│   ├── run_experiment.sh      # Run individual experiments
│   └── view_report.py         # Helper for viewing HTML reports
└── outputs/                   # All experiment results
    ├── summary.csv            # Consolidated CSV with all results
    └── {STRATEGY}/            # Strategy-specific results
        └── {PAIR}/            # Pair-specific results
            └── {TIMEFRAME}/   # Timeframe-specific results
                └── {TIMESTAMP}/   # Individual experiment run
                    ├── run.log        # Full execution log
                    ├── report.html    # HTML report
                    └── *.json         # Backtest result files
```

## 🚀 Quick Start

### 1. Configure Experiments

Edit `experiments.conf` to define your experiments. Each line should contain:
```
STRATEGY PAIR TIMEFRAME START_DATE IS_LENGTH OOS_LENGTH EPOCHS
```

**Example:**
```
VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10
VWMAStrategy BTC/USDT:USDT 1h 20250101 60 15 20
```

### 2. Run Experiments

```bash
# Run all experiments from config file (Python orchestrator - recommended)
python3 experiments/scripts/run_all_experiments.py

# Alternative: Bash orchestrator (legacy)
./experiments/scripts/run_all_experiments.sh

# Run a single experiment
```bash
# Run a single experiment
python3 experiments/scripts/run_experiment.py VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10
```
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
- `strategy` - Strategy name
- `pair` - Trading pair
- `timeframe` - Timeframe used
- `start_date` - Start date of the experiment (YYYYMMDD format)
- `IS_days` - In-sample period length in days
- `OOS_days` - Out-of-sample period length in days
- `epochs` - Number of epochs used in hyperoptimization
- `Total profit %` - Total profit percentage
- `Max Drawdown (Acct)` - Maximum drawdown
- `Sortino` - Sortino ratio
- `Sharpe` - Sharpe ratio
- `Calmar` - Calmar ratio
- `Profit factor` - Profit factor
- `Trades` - Number of trades
- `Win %` - Win percentage

### Individual Experiment Results
Each experiment creates a timestamped directory containing:
- **`run.log`** - Complete execution log with all freqtrade output
- **`report.html`** - Formatted HTML report with metrics and full log
- **`*.json`** - Raw backtest result files from freqtrade

## 📋 Available Scripts

### `run_all_experiments.py`
**Main orchestrator script (Python - recommended)**
- Reads `experiments.conf` line by line
- Executes individual experiments sequentially with proper error handling
- Appends results to `summary.csv`
- Creates CSV headers if file doesn't exist
- Better process management and output capturing than bash version
- Continues processing even if individual experiments fail

### `run_all_experiments.sh`
**Legacy bash orchestrator script**
- Same functionality as Python version but with shell scripting limitations
- Kept for backward compatibility

### `run_experiment.sh`
**Individual experiment runner**
- Runs hyperopt + backtesting for both long and short strategies
- Creates timestamped output directory
- Logs all output to `run.log`
- Copies backtest JSON files
- Generates HTML report

### `generate_report.py`
**Report generation utility**
- Parses freqtrade logs for key metrics
- Generates HTML reports with tables and full logs
- Outputs CSV data row for summary file
- Handles multiple strategies per experiment

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
- **Individual runs**: Each run creates a **NEW** timestamped directory
- **Multiple runs**: Will accumulate results over time

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
# Run one experiment manually
./experiments/scripts/run_experiment.sh VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10

# View the generated report
python3 experiments/scripts/view_report.py
```

### Multiple Strategies
Add multiple lines to `experiments.conf`:
```
VWMAStrategy DOGE/USDT:USDT 15m 20250201 90 30 10
VWMAStrategyV2 DOGE/USDT:USDT 15m 20250201 90 30 10
ScalpHybridStrategy BTC/USDT:USDT 5m 20250101 60 15 20
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
Simple space-separated format:
```
STRATEGY PAIR TIMEFRAME START_DATE IS_LENGTH OOS_LENGTH EPOCHS
```

**Parameters:**
- `STRATEGY` - Strategy class name (e.g., `VWMAStrategy`)
- `PAIR` - Trading pair (e.g., `DOGE/USDT:USDT`)
- `TIMEFRAME` - Timeframe (e.g., `15m`, `1h`, `4h`)
- `START_DATE` - Start date for the in-sample period (e.g., `20250201`)
- `IS_LENGTH` - In-sample period length in days (e.g., `90`)
- `OOS_LENGTH` - Out-of-sample period length in days (e.g., `30`)
- `EPOCHS` - Number of epochs for hyperoptimization (e.g., `10`)

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
**Version:** 1.0  
**Last Updated:** July 2025