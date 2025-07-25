import os
import sys
import subprocess
import datetime
import argparse
from pathlib import Path

def run_experiment(strategy, pair, timeframe, start_date_str, is_length, oos_length, epochs, spaces, loss_function="SharpeHyperOptLoss", exp_index=1, verbose=False):
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
    exp_dir = Path(f"experiments/outputs/{exp_index}.{strategy}/{pair.replace('/', '-')}/{timeframe}/{timestamp}")
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
    log_and_print(f"Spaces: {spaces}")
    log_and_print(f"Loss Function: {loss_function}")
    log_and_print(f"Calculated In Sample Period: {is_period}")
    log_and_print(f"Calculated Out of Sample Period: {oos_period}")

    # Clean previous backtest results to ensure we only copy files from this experiment
    subprocess.run(["rm", "-f", "user_data/backtest_results/*.json"], capture_output=True)
    subprocess.run(["rm", "-f", "user_data/backtest_results/*.zip"], capture_output=True)

    # Clean strategy JSON files
    subprocess.run(["rm", "-f", f"user_data/strategies/{strategy}.json"], capture_output=True)

    # Parse spaces parameter and add stoploss by default
    spaces_list = spaces.split(',') + ['stoploss']
    spaces_args = ['--spaces'] + spaces_list
    
    # Hyperopt for the specified strategy
    hyperopt_cmd = [
        "docker-compose", "run", "--rm", "freqtrade", "hyperopt",
        "--config", "user_data/config.json",
        "--strategy", strategy,
        "--hyperopt-loss", loss_function
    ] + spaces_args + [
        "--epochs", str(epochs),
        "--pair", pair,
        "--timeframe", timeframe,
        "--timerange", is_period,
        "-j", "-1"
    ]
    log_and_print(f"Running command: {' '.join(hyperopt_cmd)}")
    if verbose:
        print(f"[HYPEROPT] {' '.join(hyperopt_cmd)}")
    result = subprocess.run(hyperopt_cmd, capture_output=True, text=True)
    log_and_print(result.stdout)
    log_and_print(result.stderr)
    
    # Check if hyperopt failed
    hyperopt_failed = (
        "No good result found" in result.stdout or 
        result.returncode != 0 or 
        "AttributeError" in result.stderr or
        "Exception" in result.stderr or
        "Error" in result.stderr
    )
    if hyperopt_failed:
        if "No good result found" in result.stdout:
            failure_reason = "Hyperopt produced no good results"
        else:
            failure_reason = "Hyperopt crashed with error"
        log_and_print(f"WARNING: Hyperopt failed for {strategy} - {failure_reason}")
        # Create status file to indicate failure
        with open(exp_dir / "hyperopt_status.txt", 'w') as f:
            f.write(f"{strategy}:{failure_reason}\n")
    else:
        log_and_print(f"SUCCESS: Hyperopt completed for {strategy}")
        # Create status file to indicate success
        with open(exp_dir / "hyperopt_status.txt", 'w') as f:
            f.write(f"{strategy}:Success\n")

    # Only run OOS backtest if hyperopt succeeded
    if not hyperopt_failed:
        # Backtesting for OOS
        backtest_cmd = [
            "docker-compose", "run", "--rm", "freqtrade", "backtesting",
            "--config", "user_data/config.json",
            "--strategy", strategy,
            "--pair", pair,
            "--timeframe", timeframe,
            "--timerange", oos_period,
            "--export", "trades"
        ]
        log_and_print(f"Running command: {' '.join(backtest_cmd)}")
        if verbose:
            print(f"[BACKTEST] {' '.join(backtest_cmd)}")
        result = subprocess.run(backtest_cmd, capture_output=True, text=True)
        log_and_print(result.stdout)
        log_and_print(result.stderr)
    else:
        log_and_print(f"SKIPPING: OOS backtest for {strategy} due to hyperopt failure")

    # Copy backtest results (JSON and ZIP files)
    subprocess.run(["cp", "-f", "user_data/backtest_results/*.json", str(exp_dir)], capture_output=True)
    subprocess.run(["cp", "-f", "user_data/backtest_results/*.zip", str(exp_dir)], capture_output=True)
    
    # Copy optimization parameter files before they get deleted
    strategy_json = f"user_data/strategies/{strategy}.json"
    
    if os.path.exists(strategy_json):
        subprocess.run(["cp", strategy_json, str(exp_dir)], capture_output=True)
        log_and_print(f"Saved optimization parameters: {strategy}.json")
    else:
        log_and_print(f"Warning: {strategy}.json not found for parameter capture")

    # Run the python reporting script and capture its output to the log file, then output CSV data
    generate_report_cmd = [
        sys.executable,  # Use sys.executable to ensure the correct python interpreter
        "experiments/scripts/generate_report.py",
        str(exp_dir),
        strategy,
        str(exp_index)
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a freqtrade experiment")
    parser.add_argument("strategy", help="Strategy name")
    parser.add_argument("pair", help="Trading pair")
    parser.add_argument("timeframe", help="Timeframe")
    parser.add_argument("start_date", help="Start date (YYYYMMDD)")
    parser.add_argument("is_length", help="In-sample length in days")
    parser.add_argument("oos_length", help="Out-of-sample length in days")
    parser.add_argument("epochs", help="Number of epochs")
    parser.add_argument("spaces", help="Hyperopt spaces to optimize (comma-separated)")
    parser.add_argument("loss_function", nargs="?", default="SharpeHyperOptLoss", help="Hyperopt loss function")
    parser.add_argument("exp_index", nargs="?", default="1", help="Experiment index number")
    parser.add_argument("--verbose", action="store_true", help="Print full freqtrade commands")
    
    args = parser.parse_args()
    
    run_experiment(
        args.strategy, args.pair, args.timeframe, args.start_date,
        args.is_length, args.oos_length, args.epochs, args.spaces, args.loss_function, int(args.exp_index), args.verbose
    )