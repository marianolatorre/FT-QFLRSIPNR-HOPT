import os
import sys
import subprocess
import datetime
from pathlib import Path

def run_experiment(strategy, pair, timeframe, start_date_str, is_length, oos_length, epochs):
    # Convert lengths to integers
    is_length = int(is_length)
    oos_length = int(oos_length)
    epochs = int(epochs)

    # Calculate IS and OOS periods
    start_date = datetime.datetime.strptime(start_date_str, '%Y%m%d').date()

    is_end_date = start_date + datetime.timedelta(days=is_length - 1)
    is_period = f'{start_date.strftime("%Y%m%d")}-{is_end_date.strftime("%Y%m%d")}'

    oos_start_date = start_date + datetime.timedelta(days=is_length)
    oos_end_date = oos_start_date + datetime.timedelta(days=oos_length - 1)
    oos_period = f'{oos_start_date.strftime("%Y%m%d")}-{oos_end_date.strftime("%Y%m%d")}'

    # Create a unique directory for the experiment
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    exp_dir = Path(f"experiments/outputs/{strategy}/{pair.replace('/', '-')}/{timeframe}/{timestamp}")
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Define the log file
    log_file = exp_dir / "run.log"

    def log_and_print(message):
        with open(log_file, 'a') as f:
            f.write(message + '\n')
        print(message)

    log_and_print(f"Strategy: {strategy}")
    log_and_print(f"Pair: {pair}")
    log_and_print(f"Timeframe: {timeframe}")
    log_and_print(f"Start Date: {start_date_str}")
    log_and_print(f"IS Length (days): {is_length}")
    log_and_print(f"OOS Length (days): {oos_length}")
    log_and_print(f"Epochs: {epochs}")
    log_and_print(f"Calculated In Sample Period: {is_period}")
    log_and_print(f"Calculated Out of Sample Period: {oos_period}")

    # Clean previous backtest results to ensure we only copy files from this experiment
    subprocess.run(["rm", "-f", "user_data/backtest_results/*.json"], capture_output=True)
    subprocess.run(["rm", "-f", "user_data/backtest_results/*.zip"], capture_output=True)

    # Clean strategy JSON files
    subprocess.run(["rm", "-f", f"user_data/strategies/{strategy}.json"], capture_output=True)
    subprocess.run(["rm", "-f", f"user_data/strategies/{strategy}Short.json"], capture_output=True)

    # Hyperopt for long strategy
    hyperopt_cmd_long = [
        "docker-compose", "run", "--rm", "freqtrade", "hyperopt",
        "--config", "user_data/config.json",
        "--strategy", strategy,
        "--hyperopt-loss", "SortinoHyperOptLoss",
        "--spaces", "buy", "stoploss",
        "--epochs", str(epochs),
        "--pair", pair,
        "--timeframe", timeframe,
        "--timerange", is_period,
        "-j", "-1"
    ]
    log_and_print(f"Running command: {' '.join(hyperopt_cmd_long)}")
    result = subprocess.run(hyperopt_cmd_long, capture_output=True, text=True)
    log_and_print(result.stdout)
    log_and_print(result.stderr)

    # Backtesting for long strategy OOS
    backtest_cmd_long = [
        "docker-compose", "run", "--rm", "freqtrade", "backtesting",
        "--config", "user_data/config.json",
        "--strategy", strategy,
        "--pair", pair,
        "--timeframe", timeframe,
        "--timerange", oos_period,
        "--export", "trades"
    ]
    log_and_print(f"Running command: {' '.join(backtest_cmd_long)}")
    result = subprocess.run(backtest_cmd_long, capture_output=True, text=True)
    log_and_print(result.stdout)
    log_and_print(result.stderr)

    # Hyperopt for short strategy
    hyperopt_cmd_short = [
        "docker-compose", "run", "--rm", "freqtrade", "hyperopt",
        "--config", "user_data/config.json",
        "--strategy", f"{strategy}Short",
        "--hyperopt-loss", "SortinoHyperOptLoss",
        "--spaces", "sell", "stoploss",
        "--epochs", str(epochs),
        "--pair", pair,
        "--timeframe", timeframe,
        "--timerange", is_period,
        "-j", "-1"
    ]
    log_and_print(f"Running command: {' '.join(hyperopt_cmd_short)}")
    result = subprocess.run(hyperopt_cmd_short, capture_output=True, text=True)
    log_and_print(result.stdout)
    log_and_print(result.stderr)

    # Backtesting for short strategy OOS
    backtest_cmd_short = [
        "docker-compose", "run", "--rm", "freqtrade", "backtesting",
        "--config", "user_data/config.json",
        "--strategy", f"{strategy}Short",
        "--pair", pair,
        "--timeframe", timeframe,
        "--timerange", oos_period,
        "--export", "trades"
    ]
    log_and_print(f"Running command: {' '.join(backtest_cmd_short)}")
    result = subprocess.run(backtest_cmd_short, capture_output=True, text=True)
    log_and_print(result.stdout)
    log_and_print(result.stderr)

    # Copy backtest results (JSON and ZIP files)
    subprocess.run(["cp", "-f", "user_data/backtest_results/*.json", str(exp_dir)], capture_output=True)
    subprocess.run(["cp", "-f", "user_data/backtest_results/*.zip", str(exp_dir)], capture_output=True)

    # Run the python reporting script and capture its output to the log file, then output CSV data
    generate_report_cmd = [
        sys.executable,  # Use sys.executable to ensure the correct python interpreter
        "experiments/scripts/generate_report.py",
        str(exp_dir),
        strategy
    ]
    log_and_print(f"Running command: {' '.join(generate_report_cmd)}")
    result = subprocess.run(generate_report_cmd, capture_output=True, text=True)
    # Log to file only, don't print stdout to avoid duplicates
    with open(log_file, 'a') as f:
        f.write(result.stdout + '\n')
        f.write(result.stderr + '\n')
    # Print CSV output ONLY to stdout for run_all_experiments.py
    print(result.stdout, end='')

    log_and_print(f"Experiment finished for {strategy} {pair} {timeframe}")

    # Clean strategy JSON files again
    subprocess.run(["rm", "-f", f"user_data/strategies/{strategy}.json"], capture_output=True)
    subprocess.run(["rm", "-f", f"user_data/strategies/{strategy}Short.json"], capture_output=True)

if __name__ == "__main__":
    if len(sys.argv) != 8:
        print("Usage: python3 run_experiment.py <strategy> <pair> <timeframe> <start_date> <is_length> <oos_length> <epochs>")
        sys.exit(1)
    
    run_experiment(*sys.argv[1:])
