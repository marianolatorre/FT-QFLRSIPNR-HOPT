#!/usr/bin/env python3
"""
Walk Forward Testing Script for Freqtrade
Orchestrates hyperopt optimization followed by out-of-sample backtesting
"""

import argparse
import subprocess
import shutil
import os
import json
import glob
import zipfile
import re
from datetime import datetime, timedelta
from pathlib import Path
import sys


class WalkForwardTester:
    def __init__(self, insample_days, outsample_days, num_walks, end_date=None,
                 pair="BTC/USDT:USDT", epochs=200, hyperopt_loss="SharpeHyperOptLoss",
                 strategy="QFLRSI_Strategy", config="user_data/config.json", generate_report=False,
                 spaces=["buy", "sell"], original_command=None):
        self.insample_days = insample_days
        self.outsample_days = outsample_days
        self.num_walks = num_walks
        self.end_date = datetime.strptime(end_date, "%Y%m%d") if end_date else datetime.now()
        self.pair = pair
        self.epochs = epochs
        self.hyperopt_loss = hyperopt_loss
        self.strategy = strategy
        self.config = config
        self.generate_report = generate_report
        self.spaces = spaces
        self.original_command = original_command
        self.backtest_results_dir = Path("user_data/backtest_results")
        
        # Create walk forward results directory
        self.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.wf_results_dir = Path(f"walk_forward_results/{self.session_timestamp}")
        self.wf_results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize results storage
        self.walk_forward_results = {
            'metadata': {
                'strategy': self.strategy,
                'pair': self.pair,
                'total_period': {'start': None, 'end': self.end_date.strftime('%Y-%m-%d')},
                'num_walks': self.num_walks,
                'is_window': self.insample_days,
                'oos_window': self.outsample_days,
                'epochs': self.epochs,
                'hyperopt_loss': self.hyperopt_loss,
                'config': self.config,
                'session_timestamp': self.session_timestamp,
                'original_command': self.original_command
            },
            'walks': [],
            'combined_metrics': {},
            'statistical_tests': {}
        }
        
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
    
    def collect_hyperopt_results(self, walk_num):
        """Collect hyperopt results using hyperopt-show command"""
        print(f"Collecting hyperopt results for walk {walk_num}...")
        
        cmd = [
            "docker-compose", "run", "--rm", "freqtrade", "hyperopt-show",
            "--best", "--print-json", "--no-header"
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Extract JSON from output (it's at the end after the tables)
            output_lines = result.stdout.strip().split('\n')
            json_line = None
            
            # Find the JSON line (starts with '{')
            for line in reversed(output_lines):
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    json_line = line
                    break
            
            if json_line:
                hyperopt_data = json.loads(json_line)
                
                # Add some metadata from the full output
                full_data = {
                    'params': hyperopt_data,
                    'results_metrics': {},  # Will be filled from backtest results
                    'raw_output': result.stdout  # Keep full output for reference
                }
                
                # Save to file
                hyperopt_file = self.wf_results_dir / f"hyperopt_walk_{walk_num}.json"
                with open(hyperopt_file, 'w') as f:
                    json.dump(full_data, f, indent=2)
                
                print(f"Hyperopt results saved to {hyperopt_file}")
                return full_data
            else:
                print(f"No JSON found in hyperopt output for walk {walk_num}")
                return None
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to collect hyperopt results for walk {walk_num}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Failed to parse hyperopt JSON for walk {walk_num}: {e}")
            return None
    
    def generate_charts_for_walk(self, walk_num, hyperopt_start, hyperopt_end, backtest_start, backtest_end):
        """Generate profit charts for both IS and OOS periods"""
        print(f"Generating charts for walk {walk_num}...")
        
        # Generate IS period chart (need to run backtest for IS period first)
        is_timerange = f"{self.format_date(hyperopt_start)}-{self.format_date(hyperopt_end)}"
        is_chart_success = self.generate_is_chart_for_period(walk_num, hyperopt_start, hyperopt_end, "IS")
        
        # Copy IS chart with specific naming
        if is_chart_success:
            self.copy_chart_to_results_dir(walk_num, "IS")
        
        # Generate OOS period chart (use existing backtest results)
        oos_timerange = f"{self.format_date(backtest_start)}-{self.format_date(backtest_end)}"
        oos_chart_success = self.generate_oos_chart_from_existing_backtest(walk_num, oos_timerange, "OOS")
        
        # Copy OOS chart with specific naming
        if oos_chart_success:
            self.copy_chart_to_results_dir(walk_num, "OOS")
        
        return is_chart_success, oos_chart_success
    
    def generate_is_chart_for_period(self, walk_num, hyperopt_start, hyperopt_end, period_type):
        """Generate IS chart by running backtest with optimized parameters for IS period"""
        try:
            # First run a backtest for the IS period using the optimized parameters
            timerange = f"{self.format_date(hyperopt_start)}-{self.format_date(hyperopt_end)}"
            
            backtest_cmd = [
                "docker-compose", "run", "--rm", "freqtrade", "backtesting",
                "--config", self.config,
                "--strategy", self.strategy,
                "--timeframe", "1h",
                "--timerange", timerange,
                "--export", "trades"
            ]
            
            print(f"Running backtest for {period_type} period chart in walk {walk_num}, timerange: {timerange}")
            backtest_result = subprocess.run(backtest_cmd, check=True, capture_output=True, text=True)
            print(f"Backtest for {period_type} period completed successfully")
            
            # Now generate the chart
            chart_cmd = [
                "docker-compose", "run", "--rm", "freqtrade", "plot-profit",
                "--config", self.config,
                "--strategy", self.strategy,
                "--timeframe", "1h",
                "--timerange", timerange
            ]
            
            print(f"Generating {period_type} chart for walk {walk_num}, timerange: {timerange}")
            chart_result = subprocess.run(chart_cmd, check=True, capture_output=True, text=True)
            print(f"{period_type} chart generated successfully for walk {walk_num}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to generate {period_type} chart for walk {walk_num}: {e}")
            # Check if the error is due to no trades available
            if "KeyError: 'pair'" in str(e.stderr) or "No trades found" in str(e.stderr):
                print(f"No trades available for {period_type} period in walk {walk_num} - this is normal for some periods")
            else:
                print(f"Error output: {e.stderr}")
            return False
        except Exception as e:
            print(f"Exception while generating {period_type} chart for walk {walk_num}: {e}")
            return False
    
    def generate_oos_chart_from_existing_backtest(self, walk_num, timerange, period_type):
        """Generate OOS chart from existing backtest results"""
        try:
            # Use the existing backtest result to generate the chart
            chart_cmd = [
                "docker-compose", "run", "--rm", "freqtrade", "plot-profit",
                "--config", self.config,
                "--strategy", self.strategy,
                "--timeframe", "1h"
                # Don't specify timerange - use the most recent backtest result
            ]
            
            print(f"Generating {period_type} chart for walk {walk_num} using existing backtest results")
            chart_result = subprocess.run(chart_cmd, check=True, capture_output=True, text=True)
            print(f"{period_type} chart generated successfully for walk {walk_num}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to generate {period_type} chart for walk {walk_num}: {e}")
            # Check if the error is due to no trades available
            if "KeyError: 'pair'" in str(e.stderr) or "No trades found" in str(e.stderr):
                print(f"No trades available for {period_type} period in walk {walk_num} - this is normal for some periods")
            else:
                print(f"Error output: {e.stderr}")
            return False
        except Exception as e:
            print(f"Exception while generating {period_type} chart for walk {walk_num}: {e}")
            return False
    
    def generate_chart_for_period(self, walk_num, timerange, period_type):
        """Generate a chart for a specific period (IS or OOS)"""
        try:
            cmd = [
                "docker-compose", "run", "--rm", "freqtrade", "plot-profit",
                "--config", self.config,
                "--strategy", self.strategy,
                "--timeframe", "1h",
                "--timerange", timerange
            ]
            
            print(f"Generating {period_type} chart for walk {walk_num}, timerange: {timerange}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"{period_type} chart generated successfully for walk {walk_num}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to generate {period_type} chart for walk {walk_num}: {e}")
            # Check if the error is due to no trades available (common for some periods)
            if "KeyError: 'pair'" in str(e.stderr) or "No trades found" in str(e.stderr):
                print(f"No trades available for {period_type} period in walk {walk_num} - this is normal for some periods")
            else:
                print(f"Error output: {e.stderr}")
            return False
        except Exception as e:
            print(f"Exception while generating {period_type} chart for walk {walk_num}: {e}")
            return False
    
    def copy_chart_to_results_dir(self, walk_num, period_type):
        """Copy generated chart from plot/ to walk_forward_results directory with specific naming"""
        try:
            import shutil
            
            plot_dir = Path("user_data/plot")
            if not plot_dir.exists():
                print(f"Plot directory {plot_dir} does not exist")
                return
            
            # Create charts subdirectory in walk forward results
            charts_dir = self.wf_results_dir / "charts"
            charts_dir.mkdir(exist_ok=True)
            
            # Copy profit plot (the main chart file)
            profit_plot = plot_dir / "freqtrade-profit-plot.html"
            if profit_plot.exists():
                # Copy with walk and period specific naming
                dest_file = charts_dir / f"walk_{walk_num}_{period_type}_chart.html"
                shutil.copy2(profit_plot, dest_file)
                print(f"Copied {period_type} profit chart to {dest_file}")
            else:
                print(f"Profit plot file not found: {profit_plot}")
            
        except Exception as e:
            print(f"Failed to copy {period_type} chart for walk {walk_num}: {e}")

    def collect_backtest_results(self, walk_num):
        """Collect comprehensive backtest results using Freqtrade's analysis tools"""
        print(f"Collecting comprehensive backtest results for walk {walk_num}...")
        
        try:
            # Extract comprehensive data directly from the ZIP files
            backtest_data = self.extract_backtest_from_zip()
            
            if not backtest_data:
                print(f"No comprehensive data found for walk {walk_num}")
                return None
            
            # Save comprehensive results
            backtest_file = self.wf_results_dir / f"backtest_walk_{walk_num}.json"
            with open(backtest_file, 'w') as f:
                json.dump(backtest_data, f, indent=2, default=str)
            
            # Save analysis summary for reference
            analysis_file = self.wf_results_dir / f"analysis_walk_{walk_num}.txt"
            with open(analysis_file, 'w') as f:
                f.write("=== ZIP EXTRACTION SUMMARY ===\n")
                f.write(f"Extracted {len(backtest_data.get('trades', []))} trades\n")
                f.write(f"Comprehensive metrics: {backtest_data.get('comprehensive_metrics', {})}\n")
            
            print(f"Comprehensive backtest results saved to {backtest_file}")
            print(f"Raw analysis saved to {analysis_file}")
            return backtest_data
            
        except subprocess.CalledProcessError as e:
            print(f"Failed to run backtest analysis for walk {walk_num}: {e}")
            print(f"Error output: {e.stderr}")
            return None
        except Exception as e:
            print(f"Failed to collect backtest results for walk {walk_num}: {e}")
            return None
    
    def parse_comprehensive_backtest_data(self, raw_output):
        """Parse comprehensive backtest data from Freqtrade's analysis tools"""
        result = {
            'stats': None,
            'trades': None,
            'analysis': {},
            'raw_output': raw_output
        }
        
        try:
            # Extract stats JSON
            if "=== STATS START ===" in raw_output and "=== STATS END ===" in raw_output:
                stats_start = raw_output.find("=== STATS START ===") + len("=== STATS START ===")
                stats_end = raw_output.find("=== STATS END ===")
                stats_json = raw_output[stats_start:stats_end].strip()
                result['stats'] = json.loads(stats_json)
            
            # Extract trades JSON
            if "=== TRADES START ===" in raw_output and "=== TRADES END ===" in raw_output:
                trades_start = raw_output.find("=== TRADES START ===") + len("=== TRADES START ===")
                trades_end = raw_output.find("=== TRADES END ===")
                trades_json = raw_output[trades_start:trades_end].strip()
                result['trades'] = json.loads(trades_json)
                
        except json.JSONDecodeError as e:
            print(f"Failed to parse extracted JSON data: {e}")
        
        return result
    
    def extract_backtest_from_zip(self):
        """Extract comprehensive backtest data directly from ZIP files"""
        try:
            # Find the most recent ZIP file
            zip_files = glob.glob(str(self.backtest_results_dir / "*.zip"))
            if not zip_files:
                # Check current directory as fallback
                zip_files = glob.glob("*.zip")
                if not zip_files:
                    print("No ZIP files found in backtest results")
                    return None
            
            # Get the most recent ZIP file
            latest_zip = max(zip_files, key=os.path.getctime)
            print(f"Extracting data from: {latest_zip}")
            
            backtest_data = {
                'trades': [],
                'strategy_params': {},
                'stats': {},
                'comprehensive_metrics': {}
            }
            
            with zipfile.ZipFile(latest_zip, 'r') as z:
                # Read main backtest results (contains trades)
                main_file = None
                for name in z.namelist():
                    if name.endswith('.json') and not '_config' in name and not '_QFLRSI' in name:
                        main_file = name
                        break
                
                if main_file:
                    with z.open(main_file) as f:
                        main_data = json.load(f)
                        
                        # Extract strategy data
                        strategy_data = main_data.get('strategy', {}).get(self.strategy, {})
                        
                        if strategy_data:
                            trades = strategy_data.get('trades', [])
                            backtest_data['trades'] = trades
                            
                            # Calculate comprehensive metrics from trades
                            if trades:
                                profits = [t.get('profit_abs', 0) for t in trades]
                                profit_ratios = [t.get('profit_ratio', 0) for t in trades]
                                durations = [t.get('trade_duration', 0) for t in trades]
                                
                                total_profit_abs = sum(profits)
                                total_trades = len(trades)
                                winning_trades = [p for p in profits if p > 0]
                                losing_trades = [p for p in profits if p < 0]
                                
                                backtest_data['comprehensive_metrics'] = {
                                    'total_profit_abs': total_profit_abs,
                                    'total_profit_pct': sum(profit_ratios) * 100,
                                    'total_trades': total_trades,
                                    'winning_trades': len(winning_trades),
                                    'losing_trades': len(losing_trades),
                                    'win_rate': (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0,
                                    'profit_factor': (sum(winning_trades) / abs(sum(losing_trades))) if losing_trades else float('inf'),
                                    'avg_profit_abs': total_profit_abs / total_trades if total_trades > 0 else 0,
                                    'avg_duration_minutes': sum(durations) / total_trades if total_trades > 0 else 0,
                                    'best_trade': max(profits) if profits else 0,
                                    'worst_trade': min(profits) if profits else 0,
                                    'avg_win': sum(winning_trades) / len(winning_trades) if winning_trades else 0,
                                    'avg_loss': sum(losing_trades) / len(losing_trades) if losing_trades else 0
                                }
                                
                                # Calculate Sharpe-like ratio (simplified)
                                if len(profit_ratios) > 1:
                                    import statistics
                                    mean_return = statistics.mean(profit_ratios)
                                    std_return = statistics.stdev(profit_ratios)
                                    backtest_data['comprehensive_metrics']['sharpe_approx'] = mean_return / std_return if std_return > 0 else 0
                                else:
                                    backtest_data['comprehensive_metrics']['sharpe_approx'] = 0
                
                # Read strategy parameters
                strategy_file = None
                for name in z.namelist():
                    if '_QFLRSI_Strategy.json' in name or f'_{self.strategy}.json' in name:
                        strategy_file = name
                        break
                
                if strategy_file:
                    with z.open(strategy_file) as f:
                        strategy_params = json.load(f)
                        backtest_data['strategy_params'] = strategy_params
            
            print(f"Extracted {len(backtest_data['trades'])} trades and comprehensive metrics")
            return backtest_data
            
        except Exception as e:
            print(f"Failed to extract from ZIP: {e}")
            return None
    
    def extract_hyperopt_profit(self, hyperopt_data):
        """Extract profit from hyperopt raw output"""
        if not hyperopt_data or not hyperopt_data.get('raw_output'):
            return None
        
        raw_output = hyperopt_data['raw_output']
        # Look for "Tot Profit USDT" in the hyperopt output
        import re
        match = re.search(r'Tot Profit USDT.*?(\d+\.?\d*)', raw_output)
        if match:
            return float(match.group(1))
        return None
    
    def extract_backtest_profit(self, backtest_data):
        """Extract profit from comprehensive backtest data"""
        if not backtest_data:
            return None
        
        # Try to get profit from comprehensive metrics first
        if backtest_data.get('comprehensive_metrics'):
            return backtest_data['comprehensive_metrics'].get('total_profit_abs', 0)
        
        # Fallback to stats if available
        if backtest_data.get('stats'):
            stats = backtest_data['stats']
            for strategy_name, strategy_data in stats.items():
                if isinstance(strategy_data, dict) and 'profit_total_abs' in strategy_data:
                    return strategy_data['profit_total_abs']
        
        return None
    
    def calculate_walk_metrics(self, hyperopt_data, backtest_data):
        """Calculate comprehensive metrics for a walk using rich data"""
        metrics = {}
        
        # Use comprehensive metrics if available (from ZIP extraction)
        if backtest_data.get('comprehensive_metrics'):
            comp_metrics = backtest_data['comprehensive_metrics']
            metrics.update({
                'profit_total_abs': comp_metrics.get('total_profit_abs', 0),
                'profit_total_pct': comp_metrics.get('total_profit_pct', 0),
                'total_trades': comp_metrics.get('total_trades', 0),
                'winning_trades': comp_metrics.get('winning_trades', 0),
                'losing_trades': comp_metrics.get('losing_trades', 0),
                'win_rate': comp_metrics.get('win_rate', 0),
                'profit_factor': comp_metrics.get('profit_factor', 0),
                'avg_profit_abs': comp_metrics.get('avg_profit_abs', 0),
                'avg_duration_minutes': comp_metrics.get('avg_duration_minutes', 0),
                'best_trade': comp_metrics.get('best_trade', 0),
                'worst_trade': comp_metrics.get('worst_trade', 0),
                'avg_win': comp_metrics.get('avg_win', 0),
                'avg_loss': comp_metrics.get('avg_loss', 0),
                'sharpe_approx': comp_metrics.get('sharpe_approx', 0)
            })
        
        # Extract strategy parameters if available
        if backtest_data.get('strategy_params'):
            strategy_params = backtest_data['strategy_params']
            metrics['strategy_params'] = strategy_params.get('params', {})
        
        # Add trade-level analysis if trades data is available
        if backtest_data.get('trades'):
            trades = backtest_data['trades']
            metrics['trade_count'] = len(trades)
            
            # Add sample trades for analysis
            if trades:
                metrics['sample_trades'] = trades[:5]  # First 5 trades for inspection
                
                # Calculate additional trade metrics
                durations = [t.get('trade_duration', 0) for t in trades]
                profits = [t.get('profit_abs', 0) for t in trades]
                
                metrics.update({
                    'min_duration': min(durations) if durations else 0,
                    'max_duration': max(durations) if durations else 0,
                    'total_duration': sum(durations),
                    'unique_pairs': len(set(t.get('pair', '') for t in trades))
                })
        
        return metrics
    
    def save_combined_results(self):
        """Save combined walk forward results"""
        # Set start date in metadata
        if self.walk_forward_results['walks']:
            first_walk = self.walk_forward_results['walks'][0]
            self.walk_forward_results['metadata']['total_period']['start'] = first_walk['is_period']['start']
        
        # Save combined results
        combined_file = self.wf_results_dir / "combined_results.json"
        with open(combined_file, 'w') as f:
            json.dump(self.walk_forward_results, f, indent=2)
        
        print(f"Combined results saved to {combined_file}")
        
        # Generate report if requested
        if self.generate_report:
            self.generate_walk_forward_report()
    
    def generate_walk_forward_report(self):
        """Generate walk forward analysis report"""
        print("Generating walk forward analysis report...")
        try:
            # Import here to avoid dependency issues if not generating report
            import sys
            import os
            
            # Add current directory to path for imports
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            from walk_forward_report import generate_enhanced_html_report
            
            report_file = self.wf_results_dir / "walk_forward_report.html"
            generate_enhanced_html_report(self.walk_forward_results, report_file)
            print(f"Report generated: {report_file}")
            
        except ImportError as e:
            print(f"Cannot import walk_forward_report module: {e}")
            print("Skipping report generation.")
        except Exception as e:
            print(f"Failed to generate report: {e}")
    
    def clean_backtest_results(self):
        """Clean backtest_results folder"""
        # Skip cleaning to preserve existing backtest results
        print(f"Preserving existing backtest results in {self.backtest_results_dir}")
        self.backtest_results_dir.mkdir(parents=True, exist_ok=True)
    
    def run_hyperopt(self, hyperopt_start, hyperopt_end, walk_num):
        """Run hyperopt optimization"""
        timerange = f"{self.format_date(hyperopt_start)}-{self.format_date(hyperopt_end)}"
        
        cmd = [
            "docker-compose", "run", "--rm", "freqtrade", "hyperopt",
            "--config", self.config,
            "--strategy", self.strategy,
            "--hyperopt-loss", self.hyperopt_loss,
            "--spaces", *self.spaces,
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
            
            # Initialize walk data
            walk_data = {
                'walk_num': window['walk'],
                'is_period': {
                    'start': window['hyperopt_start'].strftime('%Y-%m-%d'),
                    'end': window['hyperopt_end'].strftime('%Y-%m-%d')
                },
                'oos_period': {
                    'start': window['backtest_start'].strftime('%Y-%m-%d'),
                    'end': window['backtest_end'].strftime('%Y-%m-%d')
                },
                'hyperopt_results': None,
                'backtest_results': None,
                'best_params': None,
                'wfer': None,
                'degradation': None
            }
            
            # Run hyperopt
            if not self.run_hyperopt(window['hyperopt_start'], window['hyperopt_end'], window['walk']):
                print(f"Stopping due to hyperopt failure in walk {window['walk']}")
                return False
            
            # Collect hyperopt results
            hyperopt_data = self.collect_hyperopt_results(window['walk'])
            if hyperopt_data:
                walk_data['hyperopt_results'] = hyperopt_data
                walk_data['best_params'] = hyperopt_data.get('params', {})
            
            # Run backtest
            if not self.run_backtest(window['backtest_start'], window['backtest_end'], window['walk']):
                print(f"Stopping due to backtest failure in walk {window['walk']}")
                return False
            
            # Collect backtest results
            backtest_data = self.collect_backtest_results(window['walk'])
            if backtest_data:
                walk_data['backtest_results'] = backtest_data
                
                # Calculate comprehensive metrics using the rich data
                walk_data['metrics'] = self.calculate_walk_metrics(hyperopt_data, backtest_data)
                
                # Calculate WFER using profit_total_abs from comprehensive stats
                is_return = self.extract_hyperopt_profit(hyperopt_data) if hyperopt_data else None
                oos_return = self.extract_backtest_profit(backtest_data)
                
                if is_return and oos_return:
                    walk_data['wfer'] = oos_return / is_return if is_return != 0 else 0
                    walk_data['degradation'] = ((oos_return - is_return) / is_return * 100) if is_return != 0 else 0
                elif oos_return:
                    # If we have OOS data but no IS data, still record what we have
                    walk_data['wfer'] = 0  # Can't calculate without IS data
                    walk_data['degradation'] = 0
                    walk_data['oos_profit'] = oos_return
                else:
                    walk_data['wfer'] = 0
                    walk_data['degradation'] = 0
            
            # Generate charts for this walk
            print(f"Generating charts for walk {window['walk']}...")
            is_chart_success, oos_chart_success = self.generate_charts_for_walk(
                window['walk'], 
                window['hyperopt_start'], 
                window['hyperopt_end'],
                window['backtest_start'], 
                window['backtest_end']
            )
            
            # Store chart generation status
            walk_data['chart_generation'] = {
                'is_chart_success': is_chart_success,
                'oos_chart_success': oos_chart_success
            }
            
            # Add walk data to results
            self.walk_forward_results['walks'].append(walk_data)
        
        print(f"\n{'='*60}")
        print("Walk Forward Test completed successfully!")
        print(f"Backtest results saved in: {self.backtest_results_dir}")
        print(f"Walk Forward results saved in: {self.wf_results_dir}")
        print(f"{'='*60}")
        
        # Save combined results
        self.save_combined_results()
        
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
    parser.add_argument("--generate-report", action="store_true",
                        help="Generate HTML analysis report after completion")
    parser.add_argument("--spaces", type=str, nargs='+', default=["buy", "sell"],
                        help="Hyperopt spaces to optimize (default: buy sell)")
    
    args = parser.parse_args()
    
    # Capture original command line for reproducibility
    original_command = f"python3 {' '.join(sys.argv)}"
    
    tester = WalkForwardTester(
        insample_days=args.insample_days,
        outsample_days=args.outsample_days,
        num_walks=args.num_walks,
        end_date=args.end_date,
        pair=args.pair,
        epochs=args.epochs,
        hyperopt_loss=args.hyperopt_loss,
        strategy=args.strategy,
        config=args.config,
        generate_report=args.generate_report,
        spaces=args.spaces,
        original_command=original_command
    )
    
    success = tester.run_walk_forward_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()