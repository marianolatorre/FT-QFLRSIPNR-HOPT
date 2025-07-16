import re
import json
from pathlib import Path
import sys
import csv
import unittest

# Define the headers for the CSV file
CSV_HEADERS = [
    "strategy",
    "pair",
    "timeframe",
    "start_date",
    "IS_days",
    "OOS_days",
    "epochs",
    "Total profit %",
    "Max Drawdown (Acct)",
    "Sortino",
    "Sharpe",
    "Calmar",
    "Profit factor",
    "Trades",
    "Win %",
]

def parse_summary_metrics(report_content):
    metrics = {}
    # Regex to find all rows in the summary metrics table (handles both unicode and ASCII)
    matches = re.findall(r"[│\|] (.*?) [│\|] (.*?) [│\|]", report_content)
    for match in matches:
        key = match[0].strip()
        value = match[1].strip()
        if key and value and key != "Metric":  # Skip header row
            metrics[key] = value
    return metrics

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

def get_csv_row_as_string(experiment_dir, results, primary_strategy_name):
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
    
    start_date = start_date_match.group(1) if start_date_match else "N/A"
    is_days = is_days_match.group(1) if is_days_match else "N/A"
    oos_days = oos_days_match.group(1) if oos_days_match else "N/A"
    epochs = epochs_match.group(1) if epochs_match else "N/A"

    for strategy, result in results.items():
        clean_strategy = strategy.replace("Result for strategy ", "").strip()
        # Only include rows for the primary strategy and its short version
        if clean_strategy == primary_strategy_name or clean_strategy == f'{primary_strategy_name}Short':
            if 'metrics' in result:
                row = {
                    "strategy": clean_strategy,
                    "pair": experiment_dir.parent.parent.name.replace('-', '/'),
                    "timeframe": experiment_dir.parent.name,
                    "start_date": start_date,
                    "IS_days": is_days,
                    "OOS_days": oos_days,
                    "epochs": epochs,
                    "Total profit %": result['metrics'].get("Total profit %"),
                    "Max Drawdown (Acct)": result['metrics'].get("Absolute Drawdown"),
                    "Sortino": result['metrics'].get("Sortino"),
                    "Sharpe": result['metrics'].get("Sharpe"),
                    "Calmar": result['metrics'].get("Calmar"),
                    "Profit factor": result['metrics'].get("Profit factor"),
                    "Trades": result['metrics'].get("Total/Daily Avg", "").split('/')[0].strip(),
                    "Win %": result['metrics'].get("Days win/draw", "").split('/')[0].strip(),
                }
                writer.writerow(row)
    
    lines = output.getvalue().splitlines()
    if len(lines) > 1:
        # Return all data rows (skip header), separated by newlines
        data_rows = lines[1:]
        return '\n'.join(data_rows) + '\n' if data_rows else ""
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

    if len(sys.argv) != 3:
        print("Usage: python3 generate_report.py <experiment_directory> <primary_strategy_name>")
        sys.exit(1)

    experiment_dir = Path(sys.argv[1])
    primary_strategy_name = sys.argv[2]
    log_file = experiment_dir / "run.log"

    if not log_file.exists():
        print(f"Log file not found in {experiment_dir}")
        sys.exit(1)

    with open(log_file, 'r') as f:
        content = f.read()

    results = {}
    backtest_reports = re.findall(r"(Result for strategy .*?)\n(.*?)\n\s+STRATEGY SUMMARY", content, re.DOTALL)

    for report in backtest_reports:
        strategy_name = report[0]
        report_content = report[1]
        metrics = parse_summary_metrics(report_content)
        results[strategy_name] = {"report": report_content, "metrics": metrics}

    generate_html_report(experiment_dir, results)
    print(get_csv_row_as_string(experiment_dir, results, primary_strategy_name), end='')
    sys.stdout.flush()

    

if __name__ == "__main__":
    main()
