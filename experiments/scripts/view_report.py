#!/usr/bin/env python3
"""
Script to view HTML reports using Puppeteer MCP
"""
import sys
import os
from pathlib import Path

def find_latest_report():
    """Find the most recent HTML report"""
    outputs_dir = Path("experiments/outputs")
    reports = list(outputs_dir.glob("**/report.html"))
    if not reports:
        print("No HTML reports found")
        return None
    
    # Sort by modification time, newest first
    reports.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return reports[0]

def main():
    if len(sys.argv) > 1:
        report_path = Path(sys.argv[1])
    else:
        report_path = find_latest_report()
    
    if not report_path or not report_path.exists():
        print(f"Report not found: {report_path}")
        sys.exit(1)
    
    # Convert to absolute path and file URL
    abs_path = report_path.resolve()
    file_url = f"file://{abs_path}"
    
    print(f"Viewing report: {report_path}")
    print(f"URL: {file_url}")
    print()
    print("To view this report in Claude Code, use:")
    print(f"  Navigate to: {file_url}")
    print(f"  Then take a screenshot to view the content")

if __name__ == "__main__":
    main()