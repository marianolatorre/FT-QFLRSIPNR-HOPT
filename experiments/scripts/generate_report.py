import re
import json
from pathlib import Path
import sys
import csv
import unittest

# Define the headers for the CSV file
CSV_HEADERS = [
    "experiment_num",
    "strategy",
    "pair",
    "timeframe",
    "start_date",
    "IS_days",
    "OOS_days",
    "epochs",
    "loss_function",
    "Status",
    "Total profit %",
    "Max Drawdown (Acct)",
    "Sortino",
    "Sharpe",
    "Calmar",
    "Profit factor",
    "Trades",
    "Win %",
    "stoploss",
    "buy_params",
    "sell_params",
    "roi_params",
]

def parse_summary_metrics(report_content):
    metrics = {}
    # First check if there's actually a SUMMARY METRICS section
    if "SUMMARY METRICS" not in report_content:
        return metrics
    
    # Extract only the SUMMARY METRICS section
    metrics_section_match = re.search(r"SUMMARY METRICS\s*\n(.*?)(?=\n\n|\n\s*\n|$)", report_content, re.DOTALL)
    if not metrics_section_match:
        return metrics
    
    metrics_section = metrics_section_match.group(0)
    
    # Regex to find all rows in the summary metrics table (handles both unicode and ASCII)
    matches = re.findall(r"[│\|] (.*?) [│\|] (.*?) [│\|]", metrics_section)
    for match in matches:
        key = match[0].strip()
        value = match[1].strip()
        if key and value and key != "Metric":  # Skip header row
            metrics[key] = value
    
    # Validate that we got actual metrics, not random table data
    expected_keys = ["Total profit %", "Absolute Drawdown", "Sortino", "Sharpe", "Calmar", "Profit factor"]
    if not any(key in metrics for key in expected_keys):
        return {}  # Return empty if no valid metrics found
    
    return metrics

def parse_strategy_summary_table(content, strategy_name):
    """Parse metrics from STRATEGY SUMMARY table for strategies with 0 or few trades"""
    metrics = {}
    
    # Find lines that contain the strategy name in a table format
    lines = content.split('\n')
    for line in lines:
        if strategy_name in line and '│' in line:
            # Split the line by │ and clean up
            parts = re.split(r'\s*│\s*', line.strip('│ '))
            
            if len(parts) >= 8 and parts[0] == strategy_name:
                trades = parts[1]
                avg_profit = parts[2]
                total_profit_usdt = parts[3]
                total_profit_pct = parts[4]
                # parts[5] is duration
                win_stats = parts[6]  # "0     0     0     0"
                drawdown = parts[7]   # "0 USDT  0.00%"
                
                # Extract win percentage (last number in win_stats)
                win_numbers = win_stats.split()
                win_pct = win_numbers[-1] if win_numbers else "0"
                
                # Extract drawdown values
                drawdown_match = re.search(r'([\d.]+)\s+USDT\s+([\d.]+)%', drawdown)
                if drawdown_match:
                    drawdown_usdt = drawdown_match.group(1)
                    drawdown_pct = drawdown_match.group(2)
                else:
                    drawdown_usdt = "0"
                    drawdown_pct = "0.00"
                
                # Convert to the format expected by CSV generation
                metrics["Total profit %"] = f"{total_profit_pct}%"
                metrics["Absolute Drawdown"] = f"{drawdown_usdt} USDT"
                metrics["Total/Daily Avg"] = f"{trades}"
                metrics["Days win/draw"] = f"{win_pct}"
                
                # For zero trades, set default values for missing metrics
                if trades == "0":
                    metrics["Sortino"] = "0.00"
                    metrics["Sharpe"] = "0.00"  
                    metrics["Calmar"] = "0.00"
                    metrics["Profit factor"] = "0.00"
                
                break
    
    return metrics

def load_strategy_parameters(experiment_dir, strategy_name):
    """Load optimization parameters from JSON files"""
    params = {
        "stoploss": "N/A",
        "buy_params": "N/A", 
        "sell_params": "N/A",
        "roi_params": "N/A"
    }
    
    json_file = experiment_dir / f"{strategy_name}.json"
    if json_file.exists():
        try:
            with open(json_file, 'r') as f:
                param_data = json.load(f)
                
            if "params" in param_data:
                p = param_data["params"]
                
                # Extract stoploss
                if "stoploss" in p:
                    params["stoploss"] = str(p["stoploss"].get("stoploss", "N/A"))
                
                # Extract buy parameters (convert to compact string)
                if "buy" in p and p["buy"]:
                    buy_params = {k: v for k, v in p["buy"].items()}
                    params["buy_params"] = json.dumps(buy_params, separators=(',', ':'))
                
                # Extract sell parameters (convert to compact string)  
                if "sell" in p and p["sell"]:
                    sell_params = {k: v for k, v in p["sell"].items()}
                    params["sell_params"] = json.dumps(sell_params, separators=(',', ':'))
                
                # Extract ROI parameters (convert to compact string)
                if "roi" in p and p["roi"]:
                    roi_params = {k: v for k, v in p["roi"].items()}
                    params["roi_params"] = json.dumps(roi_params, separators=(',', ':'))
                    
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            # If we can't load parameters, keep N/A values
            pass
    
    return params

def generate_html_report(experiment_dir, results):
    html_content = f"""\
    <html>
    <head>
        <title>Experiment Report: {experiment_dir.name}</title>
        <style>
            body {{ font-family: sans-serif; }}
            h1, h2 {{ color: #333; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            pre {{ background-color: #eee; padding: 10px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>Experiment Report: {experiment_dir.name}</h1>
    """

    for strategy, result in results.items():
        html_content += f"<h2>{strategy}</h2>"
        if 'metrics' in result:
            html_content += "<h3>Summary Metrics</h3>"
            html_content += "<table>"
            html_content += "<tr><th>Metric</th><th>Value</th></tr>"
            for key, value in result['metrics'].items():
                html_content += f"<tr><td>{key}</td><td>{value}</td></tr>"
            html_content += "</table>"

        if 'report' in result:
            html_content += "<h3>Full Report</h3>"
            html_content += f"<pre>{result['report']}</pre>"

    log_content = (experiment_dir / 'run.log').read_text()
    html_content += "<h2>Full Log</h2>"
    html_content += f"<pre>{log_content}</pre>"

    html_content += """\
    </body>
    </html>
    """
    with open(experiment_dir / "report.html", "w") as f:
        f.write(html_content)

def load_experiment_status(experiment_dir):
    """Load status information from hyperopt_status.txt file"""
    status_file = experiment_dir / "hyperopt_status.txt"
    status_dict = {}
    
    if status_file.exists():
        try:
            with open(status_file, 'r') as f:
                for line in f:
                    if ':' in line:
                        strategy, status = line.strip().split(':', 1)
                        status_dict[strategy] = status
        except Exception:
            pass  # If file reading fails, return empty dict
    
    return status_dict

def get_csv_row_as_string(experiment_dir, results, primary_strategy_name, experiment_index):
    import io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS)
    writer.writeheader()  # Write headers so we can get the data row

    log_content = (experiment_dir / 'run.log').read_text()
    
    # Extract all needed parameters from the log
    start_date_match = re.search(r"Start Date: (\d{8})", log_content)
    is_days_match = re.search(r"IS Length \(days\): (\d+)", log_content)
    oos_days_match = re.search(r"OOS Length \(days\): (\d+)", log_content)
    epochs_match = re.search(r"Epochs: (\d+)", log_content)
    loss_function_match = re.search(r"Loss Function: (.+)", log_content)
    
    start_date = start_date_match.group(1) if start_date_match else "N/A"
    is_days = is_days_match.group(1) if is_days_match else "N/A"
    oos_days = oos_days_match.group(1) if oos_days_match else "N/A"
    epochs = epochs_match.group(1) if epochs_match else "N/A"
    loss_function = loss_function_match.group(1) if loss_function_match else "N/A"
    
    # Load status information
    status_dict = load_experiment_status(experiment_dir)

    # Process only the exact strategy that was run (literal approach)
    strategy_name = primary_strategy_name
    
    # Get status for this strategy
    strategy_status = status_dict.get(strategy_name, "Unknown")
    
    # Look for backtest results for this strategy
    found_result = None
    for strategy, result in results.items():
        clean_strategy = strategy.replace("Result for strategy ", "").strip()
        if clean_strategy == strategy_name:
            found_result = result
            break
    
    # Load optimization parameters for this strategy
    strategy_params = load_strategy_parameters(experiment_dir, strategy_name)
    
    # Create base row with common information
    row = {
        "experiment_num": experiment_index,
        "strategy": strategy_name,
        "pair": experiment_dir.parent.parent.name.replace('-', '/'),
        "timeframe": experiment_dir.parent.name,
        "start_date": start_date,
        "IS_days": is_days,
        "OOS_days": oos_days,
        "epochs": epochs,
        "loss_function": loss_function,
        "Status": strategy_status,
        "stoploss": strategy_params["stoploss"],
        "buy_params": strategy_params["buy_params"],
        "sell_params": strategy_params["sell_params"],
        "roi_params": strategy_params["roi_params"],
    }
    
    # Add performance metrics if backtest results exist
    if found_result and 'metrics' in found_result:
        row.update({
            "Total profit %": found_result['metrics'].get("Total profit %"),
            "Max Drawdown (Acct)": found_result['metrics'].get("Absolute Drawdown"),
            "Sortino": found_result['metrics'].get("Sortino"),
            "Sharpe": found_result['metrics'].get("Sharpe"),
            "Calmar": found_result['metrics'].get("Calmar"),
            "Profit factor": found_result['metrics'].get("Profit factor"),
            "Trades": found_result['metrics'].get("Total/Daily Avg Trades", "").split('/')[0].strip(),
            "Win %": found_result['metrics'].get("Days win/draw/lose", "").split('/')[0].strip(),
        })
    else:
        # No backtest results - fill with N/A
        row.update({
            "Total profit %": "N/A",
            "Max Drawdown (Acct)": "N/A",
            "Sortino": "N/A",
            "Sharpe": "N/A",
            "Calmar": "N/A",
            "Profit factor": "N/A",
            "Trades": "N/A",
            "Win %": "N/A",
        })
    
    writer.writerow(row)
    
    lines = output.getvalue().splitlines()
    if len(lines) > 1:
        # Return single data row (skip header)
        return lines[1] + '\n'
    else:
        return ""  # No data row to return

class TestReportGenerator(unittest.TestCase):
    def test_regex_compiles(self):
        try:
            re.compile(r"(Result for strategy .*?)\n(.*?)\n\s+STRATEGY SUMMARY")
        except re.error as e:
            self.fail(f"Regex failed to compile: {e}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        suite = unittest.TestLoader().loadTestsFromTestCase(TestReportGenerator)
        runner = unittest.TextTestRunner()
        runner.run(suite)
        sys.exit(0)

    if len(sys.argv) != 4:
        print("Usage: python3 generate_report.py <experiment_directory> <primary_strategy_name> <experiment_index>")
        sys.exit(1)

    experiment_dir = Path(sys.argv[1])
    primary_strategy_name = sys.argv[2]
    experiment_index = int(sys.argv[3])
    log_file = experiment_dir / "run.log"

    if not log_file.exists():
        print(f"Log file not found in {experiment_dir}")
        sys.exit(1)

    with open(log_file, 'r') as f:
        content = f.read()

    results = {}
    # More flexible regex to handle different output formats
    # Look for either the full "Result for strategy" format or just SUMMARY METRICS sections
    backtest_reports = re.findall(r"(Result for strategy .*?)\n(.*?)STRATEGY SUMMARY", content, re.DOTALL)
    
    for report in backtest_reports:
        strategy_name = report[0]
        report_content = report[1]
        metrics = parse_summary_metrics(report_content)
        
        # If no metrics found from SUMMARY METRICS section, try the strategy summary table
        if not metrics:
            strategy_name_raw = strategy_name.replace("Result for strategy ", "")
            metrics = parse_strategy_summary_table(content, strategy_name_raw)
        
        results[strategy_name] = {"report": report_content, "metrics": metrics}

    generate_html_report(experiment_dir, results)
    print(get_csv_row_as_string(experiment_dir, results, primary_strategy_name, experiment_index), end='')
    sys.stdout.flush()

    

if __name__ == "__main__":
    main()
