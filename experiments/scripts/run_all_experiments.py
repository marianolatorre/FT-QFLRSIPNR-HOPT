#!/usr/bin/env python3
"""
Python orchestrator for running all freqtrade experiments.
Replaces the bash run_all_experiments.sh for better control and reliability.
"""

import os
import sys
import subprocess
import csv
import re
import argparse
from pathlib import Path

# Configuration
CONFIG_FILE = "experiments/experiments.conf"
SUMMARY_CSV = "experiments/outputs/summary.csv"

def create_summary_csv_if_needed():
    """Create summary.csv with headers if it doesn't exist"""
    if not Path(SUMMARY_CSV).exists():
        # Import CSV headers from generate_report.py
        sys.path.append(str(Path('experiments/scripts').resolve()))
        from generate_report import CSV_HEADERS
        
        os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)
        with open(SUMMARY_CSV, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        print(f"Created {SUMMARY_CSV} with headers")

def parse_experiment_line(line):
    """Parse an experiment configuration line"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    parts = line.split()
    if len(parts) != 9:
        print(f"Invalid experiment line: {line}")
        return None
    
    return {
        'strategy': parts[0],
        'pair': parts[1], 
        'timeframe': parts[2],
        'start_date': parts[3],
        'is_length': parts[4],
        'oos_length': parts[5],
        'epochs': parts[6],
        'spaces': parts[7],
        'loss_function': parts[8]
    }

def run_experiment(experiment, verbose=False):
    """Run a single experiment and return CSV output"""
    strategy = experiment['strategy']
    pair = experiment['pair']
    timeframe = experiment['timeframe']
    start_date = experiment['start_date']
    is_length = experiment['is_length']
    oos_length = experiment['oos_length']
    epochs = experiment['epochs']
    spaces = experiment['spaces']
    loss_function = experiment['loss_function']
    exp_index = experiment['index']
    
    print(f"Running experiment: {strategy} {pair} {timeframe} {start_date} {is_length} {oos_length} {epochs} {spaces} {loss_function}")
    
    try:
        # Run the experiment script
        cmd = [
            sys.executable, "experiments/scripts/run_experiment.py",
            strategy, pair, timeframe, start_date, is_length, oos_length, epochs, spaces, loss_function, str(exp_index)
        ]
        
        # Add verbose flag if enabled
        if verbose:
            cmd.append("--verbose")
        
        if verbose:
            # In verbose mode, don't capture output so commands are visible
            result = subprocess.run(
                cmd,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            # For verbose mode, we need to find the latest experiment directory and get CSV
            exp_index = experiment['index']
            strategy_base = Path(f"experiments/outputs/{exp_index}.{experiment['strategy']}")
            if strategy_base.exists():
                pair_dir = strategy_base / experiment['pair'].replace('/', '-') / experiment['timeframe']
                if pair_dir.exists():
                    latest_dir = max(pair_dir.glob('*'), key=lambda x: x.stat().st_mtime, default=None)
                    if latest_dir:
                        report_cmd = [
                            sys.executable, "experiments/scripts/generate_report.py",
                            str(latest_dir),
                            experiment['strategy'],
                            str(exp_index)
                        ]
                        report_result = subprocess.run(report_cmd, capture_output=True, text=True)
                        csv_output = report_result.stdout
                    else:
                        csv_output = ""
                else:
                    csv_output = ""
            else:
                csv_output = ""
        else:
            # Normal mode - capture output as before
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            csv_output = result.stdout
        
        # Extract CSV lines from output
        csv_lines = []
        for line in csv_output.split('\n'):
            line = line.strip()
            # Look for lines that have the current strategy name in the second column (after experiment_num)
            if line and ',' in line:
                parts = line.split(',')
                if len(parts) >= 2 and (parts[1] == strategy or parts[1] == f'{strategy}Short'):
                    csv_lines.append(line)
        
        if csv_lines:
            print(f"✅ Completed: {strategy} ({len(csv_lines)} CSV rows)")
            return csv_lines
        else:
            print(f"❌ Failed: {strategy} (no CSV output found)")
            if not verbose:
                print("STDOUT:", result.stdout[-500:])  # Last 500 chars
                print("STDERR:", result.stderr[-500:])  # Last 500 chars
            else:
                print("CSV OUTPUT:", csv_output[-500:])  # Last 500 chars of CSV output
            return []
            
    except subprocess.TimeoutExpired:
        print(f"❌ Failed: {strategy} (timeout after 1 hour)")
        return []
    except Exception as e:
        print(f"❌ Failed: {strategy} (error: {e})")
        return []

def append_csv_rows(csv_lines):
    """Append CSV rows to summary file"""
    if not csv_lines:
        return
    
    with open(SUMMARY_CSV, 'a', newline='') as f:
        for line in csv_lines:
            f.write(line + '\n')

def main():
    """Main orchestrator function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run all freqtrade experiments")
    parser.add_argument("--verbose", action="store_true", 
                        help="Print full commands for hyperopt and backtest calls")
    args = parser.parse_args()
    
    print("🚀 Starting Python experiment orchestrator...")
    if args.verbose:
        print("📝 Verbose mode enabled - will show all freqtrade commands")
    
    # Create summary CSV if needed
    create_summary_csv_if_needed()
    
    # Read experiments configuration
    if not Path(CONFIG_FILE).exists():
        print(f"❌ Configuration file not found: {CONFIG_FILE}")
        sys.exit(1)
    
    experiments = []
    with open(CONFIG_FILE, 'r') as f:
        for line_num, line in enumerate(f, 1):
            experiment = parse_experiment_line(line)
            if experiment:
                experiments.append(experiment)
    
    if not experiments:
        print("❌ No valid experiments found in configuration file")
        sys.exit(1)
    
    print(f"Found {len(experiments)} experiments to run")
    
    # Process each experiment
    successful = 0
    failed = 0
    
    for i, experiment in enumerate(experiments, 1):
        print(f"\n--- Processing experiment {i}/{len(experiments)} ---")
        
        # Add experiment index to experiment data
        experiment['index'] = i
        csv_lines = run_experiment(experiment, verbose=args.verbose)
        
        if csv_lines:
            append_csv_rows(csv_lines)
            successful += 1
        else:
            failed += 1
        
        print("---")
    
    # Summary
    print(f"\n🎉 Orchestrator completed!")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Results saved to: {SUMMARY_CSV}")
    
    if failed > 0:
        sys.exit(1)  # Exit with error code if any experiments failed

if __name__ == "__main__":
    main()