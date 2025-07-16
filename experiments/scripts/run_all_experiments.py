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
    if len(parts) != 7:
        print(f"Invalid experiment line: {line}")
        return None
    
    return {
        'strategy': parts[0],
        'pair': parts[1], 
        'timeframe': parts[2],
        'start_date': parts[3],
        'is_length': parts[4],
        'oos_length': parts[5],
        'epochs': parts[6]
    }

def run_experiment(experiment):
    """Run a single experiment and return CSV output"""
    strategy = experiment['strategy']
    pair = experiment['pair']
    timeframe = experiment['timeframe']
    start_date = experiment['start_date']
    is_length = experiment['is_length']
    oos_length = experiment['oos_length']
    epochs = experiment['epochs']
    
    print(f"Running experiment: {strategy} {pair} {timeframe} {start_date} {is_length} {oos_length} {epochs}")
    
    try:
        # Run the experiment script
        cmd = [
            sys.executable, "experiments/scripts/run_experiment.py",
            strategy, pair, timeframe, start_date, is_length, oos_length, epochs
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        # Extract CSV lines from output
        csv_lines = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            # Look for lines that start with the current strategy name or its short version
            if line and (line.startswith(f'{strategy},') or line.startswith(f'{strategy}Short,')):
                csv_lines.append(line)
        
        if csv_lines:
            print(f"✅ Completed: {strategy} ({len(csv_lines)} CSV rows)")
            return csv_lines
        else:
            print(f"❌ Failed: {strategy} (no CSV output found)")
            print("STDOUT:", result.stdout[-500:])  # Last 500 chars
            print("STDERR:", result.stderr[-500:])  # Last 500 chars
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
    print("🚀 Starting Python experiment orchestrator...")
    
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
        
        csv_lines = run_experiment(experiment)
        
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