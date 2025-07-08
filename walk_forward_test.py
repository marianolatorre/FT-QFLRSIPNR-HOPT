#!/usr/bin/env python3
"""
Walk Forward Testing Script for Freqtrade
Orchestrates hyperopt optimization followed by out-of-sample backtesting
"""

import argparse
import subprocess
import shutil
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys


class WalkForwardTester:
    def __init__(self, insample_days, outsample_days, num_walks, end_date=None,
                 pair="BTC/USDT:USDT", epochs=200, hyperopt_loss="SharpeHyperOptLoss",
                 strategy="QFLRSI_Strategy", config="user_data/config.json"):
        self.insample_days = insample_days
        self.outsample_days = outsample_days
        self.num_walks = num_walks
        self.end_date = datetime.strptime(end_date, "%Y%m%d") if end_date else datetime.now()
        self.pair = pair
        self.epochs = epochs
        self.hyperopt_loss = hyperopt_loss
        self.strategy = strategy
        self.config = config
        self.backtest_results_dir = Path("user_data/backtest_results")
        
    def format_date(self, date):
        """Format date for freqtrade timerange"""
        return date.strftime("%Y%m%d")
    
    def calculate_windows(self):
        """Calculate all hyperopt and backtest windows"""
        windows = []
        current_end = self.end_date
        
        for i in range(self.num_walks):
            # Out-of-sample period (backtest)
            backtest_end = current_end
            backtest_start = current_end - timedelta(days=self.outsample_days)
            
            # In-sample period (hyperopt)
            hyperopt_end = backtest_start
            hyperopt_start = hyperopt_end - timedelta(days=self.insample_days)
            
            windows.append({
                'walk': i + 1,
                'hyperopt_start': hyperopt_start,
                'hyperopt_end': hyperopt_end,
                'backtest_start': backtest_start,
                'backtest_end': backtest_end
            })
            
            # Move window back for next iteration
            current_end = backtest_start
            
        return reversed(windows)  # Process chronologically
    
    def validate_data_availability(self):
        """Check if data is available for the required timerange"""
        print(f"Validating data availability for {self.pair}...")
        # This could be enhanced to actually check data files
        return True
    
    def clean_backtest_results(self):
        """Clean backtest_results folder"""
        if self.backtest_results_dir.exists():
            print(f"Cleaning {self.backtest_results_dir}")
            shutil.rmtree(self.backtest_results_dir)
        self.backtest_results_dir.mkdir(parents=True, exist_ok=True)
    
    def run_hyperopt(self, hyperopt_start, hyperopt_end, walk_num):
        """Run hyperopt optimization"""
        timerange = f"{self.format_date(hyperopt_start)}-{self.format_date(hyperopt_end)}"
        
        cmd = [
            "docker-compose", "run", "--rm", "freqtrade", "hyperopt",
            "--config", self.config,
            "--strategy", self.strategy,
            "--hyperopt-loss", self.hyperopt_loss,
            "--spaces", "buy", "sell",
            "--epochs", str(self.epochs),
            "--timeframe", "1h",
            "--timerange", timerange,
            "-j", "-1"
        ]
        
        print(f"Walk {walk_num}: Running hyperopt for {timerange}")
        print(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Hyperopt completed successfully for walk {walk_num}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Hyperopt failed for walk {walk_num}: {e}")
            print(f"Error output: {e.stderr}")
            return False
    
    def run_backtest(self, backtest_start, backtest_end, walk_num):
        """Run backtest with optimized parameters"""
        timerange = f"{self.format_date(backtest_start)}-{self.format_date(backtest_end)}"
        
        cmd = [
            "docker-compose", "run", "--rm", "freqtrade", "backtesting",
            "--config", self.config,
            "--strategy", self.strategy,
            "--timeframe", "1h",
            "--timerange", timerange,
            "--export", "trades"
        ]
        
        print(f"Walk {walk_num}: Running backtest for {timerange}")
        print(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Backtest completed successfully for walk {walk_num}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Backtest failed for walk {walk_num}: {e}")
            print(f"Error output: {e.stderr}")
            return False
    
    def run_walk_forward_test(self):
        """Execute the complete walk forward test"""
        print(f"Starting Walk Forward Test:")
        print(f"- In-sample period: {self.insample_days} days")
        print(f"- Out-of-sample period: {self.outsample_days} days")
        print(f"- Number of walks: {self.num_walks}")
        print(f"- End date: {self.end_date.strftime('%Y-%m-%d')}")
        print(f"- Strategy: {self.strategy}")
        print(f"- Pair: {self.pair}")
        
        if not self.validate_data_availability():
            print("Data validation failed. Exiting.")
            return False
        
        self.clean_backtest_results()
        
        windows = list(self.calculate_windows())
        
        for window in windows:
            print(f"\n{'='*60}")
            print(f"Walk {window['walk']} of {self.num_walks}")
            print(f"Hyperopt period: {window['hyperopt_start'].strftime('%Y-%m-%d')} to {window['hyperopt_end'].strftime('%Y-%m-%d')}")
            print(f"Backtest period: {window['backtest_start'].strftime('%Y-%m-%d')} to {window['backtest_end'].strftime('%Y-%m-%d')}")
            print(f"{'='*60}")
            
            # Run hyperopt
            if not self.run_hyperopt(window['hyperopt_start'], window['hyperopt_end'], window['walk']):
                print(f"Stopping due to hyperopt failure in walk {window['walk']}")
                return False
            
            # Run backtest
            if not self.run_backtest(window['backtest_start'], window['backtest_end'], window['walk']):
                print(f"Stopping due to backtest failure in walk {window['walk']}")
                return False
        
        print(f"\n{'='*60}")
        print("Walk Forward Test completed successfully!")
        print(f"Results saved in: {self.backtest_results_dir}")
        print(f"{'='*60}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Walk Forward Testing for Freqtrade")
    parser.add_argument("--insample-days", type=int, required=True,
                        help="Length in days of in-sample hyperopt period")
    parser.add_argument("--outsample-days", type=int, required=True,
                        help="Length in days of out-of-sample backtest period")
    parser.add_argument("--num-walks", type=int, required=True,
                        help="Number of walk forward iterations")
    parser.add_argument("--end-date", type=str, default=None,
                        help="End date in YYYYMMDD format (default: today)")
    parser.add_argument("--pair", type=str, default="BTC/USDT:USDT",
                        help="Trading pair (default: BTC/USDT:USDT)")
    parser.add_argument("--epochs", type=int, default=200,
                        help="Number of hyperopt epochs (default: 200)")
    parser.add_argument("--hyperopt-loss", type=str, default="SharpeHyperOptLoss",
                        help="Hyperopt loss function (default: SharpeHyperOptLoss)")
    parser.add_argument("--strategy", type=str, default="QFLRSI_Strategy",
                        help="Strategy name (default: QFLRSI_Strategy)")
    parser.add_argument("--config", type=str, default="user_data/config.json",
                        help="Config file path (default: user_data/config.json)")
    
    args = parser.parse_args()
    
    tester = WalkForwardTester(
        insample_days=args.insample_days,
        outsample_days=args.outsample_days,
        num_walks=args.num_walks,
        end_date=args.end_date,
        pair=args.pair,
        epochs=args.epochs,
        hyperopt_loss=args.hyperopt_loss,
        strategy=args.strategy,
        config=args.config
    )
    
    success = tester.run_walk_forward_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()