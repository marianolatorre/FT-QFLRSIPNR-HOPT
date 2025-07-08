#!/usr/bin/env python3
"""
Enhanced Walk Forward Report Generator
Creates professional website-ready HTML reports with comprehensive analysis
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


def extract_metrics_from_raw_output(raw_output: str) -> Dict[str, Any]:
    """Extract comprehensive metrics from the raw hyperopt output"""
    metrics = {}
    
    # Extract key metrics using regex
    patterns = {
        'total_profit_usdt': r'Tot Profit USDT.*?(\d+\.?\d*)',
        'total_profit_pct': r'Total profit %.*?(\d+\.?\d*)',
        'sharpe': r'Sharpe.*?(\d+\.?\d*)',
        'sortino': r'Sortino.*?(-?\d+\.?\d*)',
        'calmar': r'Calmar.*?(-?\d+\.?\d*)',
        'profit_factor': r'Profit factor.*?(\d+\.?\d*)',
        'win_rate': r'Win%.*?(\d+\.?\d*)',
        'total_trades': r'Total/Daily Avg Trades.*?(\d+)',
        'max_drawdown': r'Max % of account underwater.*?(\d+\.?\d*)%',
        'cagr': r'CAGR %.*?(\d+\.?\d*)',
        'sqn': r'SQN.*?(\d+\.?\d*)',
        'expectancy': r'Expectancy \(Ratio\).*?(\d+\.?\d*)',
        'best_trade': r'Best trade.*?(\d+\.?\d*)%',
        'worst_trade': r'Worst trade.*?(\d+\.?\d*)%',
        'market_change': r'Market change.*?(-?\d+\.?\d*)%'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, raw_output)
        if match:
            try:
                metrics[key] = float(match.group(1))
            except ValueError:
                metrics[key] = 0.0
        else:
            metrics[key] = 0.0
    
    return metrics


def detect_strategy_type(metadata: Dict[str, Any]) -> str:
    """Detect the strategy type to determine appropriate parameters to display"""
    strategy_name = metadata.get('strategy', '').lower()
    
    if 'qflrsi' in strategy_name:
        return 'QFLRSI'
    elif 'qfl' in strategy_name and 'sltp' in strategy_name:
        return 'QFL_SLTP'
    else:
        return 'UNKNOWN'


def get_strategy_parameter_config(strategy_type: str) -> Dict[str, Any]:
    """Get parameter configuration for different strategy types"""
    if strategy_type == 'QFLRSI':
        return {
            'headers': ['Walk', 'RSI Entry Percentile', 'RSI Exit Percentile', 'ATR Multiplier', 'ATR Period', 'Volume MA Period'],
            'params': ['rsi_entry_percentile', 'rsi_exit_percentile', 'atr_multiplier', 'atr_period', 'volume_ma_period'],
            'formats': ['{:.0f}', '{:.3f}', '{:.3f}', '{:.1f}', '{:.0f}', '{:.0f}']
        }
    elif strategy_type == 'QFL_SLTP':
        return {
            'headers': ['Walk', 'Volume MA Period', 'Buy Percentage', 'Max Base Age', 'ROI 0', 'ROI Final', 'Stoploss'],
            'params': ['volume_ma_period', 'buy_percentage', 'max_base_age', 'roi_0', 'roi_final', 'stoploss'],
            'formats': ['{:.0f}', '{:.0f}', '{:.3f}', '{:.3f}', '{:.3f}', '{:.3f}']
        }
    else:
        # Fallback for unknown strategies - show all available parameters
        return {
            'headers': ['Walk', 'Volume MA Period', 'Buy Percentage', 'Max Base Age', 'RSI Entry', 'RSI Exit', 'ATR Multiplier', 'ROI 0', 'Stoploss'],
            'params': ['volume_ma_period', 'buy_percentage', 'max_base_age', 'rsi_entry_percentile', 'rsi_exit_percentile', 'atr_multiplier', 'roi_0', 'stoploss'],
            'formats': ['{:.0f}', '{:.0f}', '{:.3f}', '{:.0f}', '{:.3f}', '{:.3f}', '{:.1f}', '{:.3f}', '{:.3f}']
        }


def extract_strategy_parameters(hyperopt_results: Dict[str, Any], strategy_type: str) -> Dict[str, Any]:
    """Extract strategy parameters based on strategy type"""
    if not hyperopt_results:
        return {}
    
    params = hyperopt_results.get('params', {}).get('params', {})
    roi_data = hyperopt_results.get('params', {}).get('minimal_roi', {})
    stoploss_data = hyperopt_results.get('params', {}).get('stoploss', 0)
    
    extracted = {}
    
    # Extract buy space parameters
    extracted['volume_ma_period'] = params.get('volume_ma_period', 0)
    extracted['buy_percentage'] = params.get('buy_percentage', 0)
    extracted['max_base_age'] = params.get('max_base_age', 0)
    extracted['rsi_entry_percentile'] = params.get('rsi_entry_percentile', 0)
    extracted['rsi_exit_percentile'] = params.get('rsi_exit_percentile', 0)
    extracted['atr_multiplier'] = params.get('atr_multiplier', 0)
    extracted['atr_period'] = params.get('atr_period', 0)
    
    # Extract ROI parameters
    if roi_data:
        roi_values = sorted(roi_data.items(), key=lambda x: int(x[0]))
        extracted['roi_0'] = roi_values[0][1] if roi_values else 0  # First ROI value (immediate)
        extracted['roi_final'] = roi_values[-1][1] if roi_values else 0  # Final ROI value (usually 0)
    else:
        extracted['roi_0'] = 0
        extracted['roi_final'] = 0
    
    # Extract stoploss
    extracted['stoploss'] = stoploss_data
    
    return extracted


def calculate_walk_forward_efficiency_ratio(walks: List[Dict]) -> Dict[str, Any]:
    """Calculate comprehensive WFER and related metrics"""
    is_profits = []
    oos_profits = []
    is_sharpes = []
    oos_sharpes = []
    
    for walk in walks:
        # In-sample metrics from hyperopt
        hyperopt_results = walk.get('hyperopt_results')
        if hyperopt_results and hyperopt_results.get('raw_output'):
            is_metrics = extract_metrics_from_raw_output(hyperopt_results['raw_output'])
            is_profits.append(is_metrics.get('total_profit_pct', 0))
            is_sharpes.append(is_metrics.get('sharpe', 0))
        
        # Out-of-sample metrics from backtest
        backtest_results = walk.get('backtest_results')
        if backtest_results:
            metrics = backtest_results.get('comprehensive_metrics', {})
            # Convert absolute profit to percentage (approximate)
            oos_profit_pct = metrics.get('total_profit_pct', 0) if metrics.get('total_profit_pct') else 0
            oos_profits.append(oos_profit_pct)
            oos_sharpes.append(metrics.get('sharpe_approx', 0))
    
    # Calculate WFER
    avg_is_profit = sum(is_profits) / len(is_profits) if is_profits else 0
    avg_oos_profit = sum(oos_profits) / len(oos_profits) if oos_profits else 0
    wfer = avg_oos_profit / avg_is_profit if avg_is_profit != 0 else 0
    
    # Calculate Sharpe degradation
    avg_is_sharpe = sum(is_sharpes) / len(is_sharpes) if is_sharpes else 0
    avg_oos_sharpe = sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else 0
    sharpe_degradation = avg_oos_sharpe / avg_is_sharpe if avg_is_sharpe != 0 else 0
    
    return {
        'wfer': wfer,
        'avg_is_profit': avg_is_profit,
        'avg_oos_profit': avg_oos_profit,
        'sharpe_degradation': sharpe_degradation,
        'avg_is_sharpe': avg_is_sharpe,
        'avg_oos_sharpe': avg_oos_sharpe,
        'total_oos_profit': sum(oos_profits),
        'profit_consistency': len([p for p in oos_profits if p > 0]) / len(oos_profits) if oos_profits else 0
    }


def generate_enhanced_html_report(walk_forward_results: Dict[str, Any], output_file: Path) -> None:
    """Generate a comprehensive, website-ready HTML report"""
    
    # Extract key data
    metadata = walk_forward_results.get('metadata', {})
    walks = walk_forward_results.get('walks', [])
    
    # Calculate comprehensive metrics
    wfer_metrics = calculate_walk_forward_efficiency_ratio(walks)
    wfer = wfer_metrics['wfer']
    
    # Generate overall rating
    if wfer > 0.7 and wfer_metrics['profit_consistency'] > 0.6:
        rating = "GREEN"
        rating_class = "green"
        recommendation = "Deploy with confidence"
        confidence_level = "High"
    elif wfer > 0.5 and wfer_metrics['profit_consistency'] > 0.3:
        rating = "YELLOW"
        rating_class = "yellow"
        recommendation = "Deploy with caution"
        confidence_level = "Medium"
    else:
        rating = "RED"
        rating_class = "red"
        recommendation = "Do not deploy"
        confidence_level = "Low"
    
    # Detect strategy type and get parameter configuration
    strategy_type = detect_strategy_type(metadata)
    param_config = get_strategy_parameter_config(strategy_type)
    
    # Generate walk analysis rows
    walk_analysis_rows = ""
    param_evolution_data = []
    
    for walk in walks:
        walk_num = walk.get('walk_num', 'N/A')
        is_period = f"{walk.get('is_period', {}).get('start', 'N/A')} to {walk.get('is_period', {}).get('end', 'N/A')}"
        oos_period = f"{walk.get('oos_period', {}).get('start', 'N/A')} to {walk.get('oos_period', {}).get('end', 'N/A')}"
        
        # Extract hyperopt metrics
        hyperopt_results = walk.get('hyperopt_results')
        if hyperopt_results and hyperopt_results.get('raw_output'):
            is_metrics = extract_metrics_from_raw_output(hyperopt_results['raw_output'])
            is_profit = f"{is_metrics.get('total_profit_pct', 0):.2f}%"
            is_sharpe = f"{is_metrics.get('sharpe', 0):.2f}"
            is_trades = int(is_metrics.get('total_trades', 0))
            is_drawdown = f"{is_metrics.get('max_drawdown', 0):.2f}%"
        else:
            is_profit = "N/A"
            is_sharpe = "N/A"
            is_trades = "N/A"
            is_drawdown = "N/A"
        
        # Extract backtest metrics
        backtest_results = walk.get('backtest_results')
        if backtest_results:
            metrics = backtest_results.get('comprehensive_metrics', {})
            oos_profit = f"{metrics.get('total_profit_pct', 0):.2f}%" if metrics.get('total_profit_pct') else "0.00%"
            oos_trades = len(backtest_results.get('trades', []))
            oos_win_rate = f"{metrics.get('win_rate', 0):.1f}%"
            oos_profit_factor = f"{metrics.get('profit_factor', 0):.2f}"
            
            # Calculate efficiency for this walk
            is_val = is_metrics.get('total_profit_pct', 0) if 'is_metrics' in locals() else 0
            oos_val = metrics.get('total_profit_pct', 0) if metrics.get('total_profit_pct') else 0
            efficiency = oos_val / is_val if is_val != 0 else 0
            efficiency_str = f"{efficiency:.2f}"
            
            # Status based on efficiency
            if efficiency > 0.7:
                status = "🟢 Excellent"
            elif efficiency > 0.5:
                status = "🟡 Good"
            elif efficiency > 0.3:
                status = "🟠 Caution"
            else:
                status = "🔴 Poor"
        else:
            oos_profit = "N/A"
            oos_trades = "N/A"
            oos_win_rate = "N/A"
            oos_profit_factor = "N/A"
            efficiency_str = "N/A"
            status = "❌ No Data"
        
        # Extract strategy parameters dynamically
        extracted_params = extract_strategy_parameters(hyperopt_results, strategy_type)
        param_data = {'walk': walk_num}
        param_data.update(extracted_params)
        param_evolution_data.append(param_data)
        
        # Generate chart links for this walk
        charts_available = walk.get('chart_generation', {})
        is_chart_available = charts_available.get('is_chart_success', False)
        oos_chart_available = charts_available.get('oos_chart_success', False)
        
        if is_chart_available:
            is_chart_link = f'<a href="charts/walk_{walk_num}_IS_chart.html" target="_blank" style="color: #007bff; text-decoration: none; font-weight: bold;">📈 IS Chart</a>'
        else:
            is_chart_link = '<span style="color: #6c757d; font-style: italic;">No Chart</span>'
            
        if oos_chart_available:
            oos_chart_link = f'<a href="charts/walk_{walk_num}_OOS_chart.html" target="_blank" style="color: #007bff; text-decoration: none; font-weight: bold;">📊 OOS Chart</a>'
        else:
            oos_chart_link = '<span style="color: #6c757d; font-style: italic;">No Chart</span>'
        
        walk_analysis_rows += f"""
        <tr>
            <td style="font-weight: bold; text-align: center;">{walk_num}</td>
            <td style="font-size: 12px;">{is_period}</td>
            <td style="font-size: 12px;">{oos_period}</td>
            <td style="color: {'#28a745' if 'N/A' not in is_profit and float(is_profit.replace('%', '')) > 0 else '#dc3545'}; font-weight: bold;">{is_profit}</td>
            <td>{is_sharpe}</td>
            <td>{is_trades}</td>
            <td>{is_drawdown}</td>
            <td style="color: {'#28a745' if 'N/A' not in oos_profit and float(oos_profit.replace('%', '')) > 0 else '#dc3545'}; font-weight: bold;">{oos_profit}</td>
            <td>{oos_trades}</td>
            <td>{oos_win_rate}</td>
            <td>{oos_profit_factor}</td>
            <td style="font-weight: bold; {'color: #28a745;' if 'N/A' not in efficiency_str and float(efficiency_str) > 0.5 else 'color: #dc3545;'}">{efficiency_str}</td>
            <td style="font-weight: bold;">{status}</td>
            <td style="text-align: center;">{is_chart_link}</td>
            <td style="text-align: center;">{oos_chart_link}</td>
        </tr>
        """
    
    # Generate strategy parameters evolution table dynamically
    param_evolution_rows = ""
    for params in param_evolution_data:
        row = f"""
        <tr>
            <td style="font-weight: bold; text-align: center;">{params['walk']}</td>"""
        
        # Add parameter values based on configuration
        for i, param_name in enumerate(param_config['params']):
            value = params.get(param_name, 0)
            format_str = param_config['formats'][i]
            formatted_value = format_str.format(value)
            row += f"""
            <td>{formatted_value}</td>"""
        
        row += """
        </tr>
        """
        param_evolution_rows += row
    
    # Calculate summary statistics
    total_trades = sum(len(walk.get('backtest_results', {}).get('trades', [])) for walk in walks)
    total_profit = sum(walk.get('backtest_results', {}).get('comprehensive_metrics', {}).get('total_profit_abs', 0) for walk in walks)
    
    # Generate trade details
    trade_details = ""
    for walk in walks:
        trades = walk.get('backtest_results', {}).get('trades', [])
        for i, trade in enumerate(trades):
            profit_abs = trade.get('profit_abs', 0)
            profit_pct = trade.get('profit_ratio', 0) * 100
            duration = trade.get('trade_duration', 0)
            
            # Convert duration from minutes to hours:minutes
            hours = duration // 60
            minutes = duration % 60
            duration_str = f"{hours}h {minutes}m"
            
            profit_color = '#28a745' if profit_abs > 0 else '#dc3545'
            
            trade_details += f"""
            <tr>
                <td>Walk {walk.get('walk_num', 'N/A')}</td>
                <td>{i+1}</td>
                <td>{trade.get('pair', 'N/A')}</td>
                <td>{trade.get('open_date', 'N/A')}</td>
                <td>{trade.get('close_date', 'N/A')}</td>
                <td style="color: {profit_color}; font-weight: bold;">{profit_abs:.2f} USDT</td>
                <td style="color: {profit_color}; font-weight: bold;">{profit_pct:.2f}%</td>
                <td>{duration_str}</td>
                <td>{trade.get('exit_reason', 'N/A')}</td>
            </tr>
            """
    
    # Generate HTML content
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Walk Forward Analysis Report - {metadata.get('strategy', 'Strategy')}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 40px;
            text-align: center;
            position: relative;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="50" cy="50" r="1" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
            opacity: 0.1;
        }}
        
        .header h1 {{
            font-size: 3rem;
            margin-bottom: 10px;
            font-weight: 700;
            position: relative;
            z-index: 1;
        }}
        
        .header .subtitle {{
            font-size: 1.2rem;
            opacity: 0.9;
            margin-bottom: 30px;
            position: relative;
            z-index: 1;
        }}
        
        .rating {{
            display: inline-block;
            font-size: 2rem;
            font-weight: bold;
            padding: 20px 40px;
            border-radius: 50px;
            margin: 20px;
            text-transform: uppercase;
            letter-spacing: 2px;
            position: relative;
            z-index: 1;
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }}
        
        .green {{ 
            background: linear-gradient(135deg, #4CAF50, #45a049);
            color: white;
        }}
        .yellow {{ 
            background: linear-gradient(135deg, #FFC107, #f0b90b);
            color: black;
        }}
        .red {{ 
            background: linear-gradient(135deg, #F44336, #d32f2f);
            color: white;
        }}
        
        .recommendation {{
            font-size: 1.5rem;
            margin-top: 20px;
            position: relative;
            z-index: 1;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .section {{
            margin-bottom: 50px;
        }}
        
        .section h2 {{
            color: #2c3e50;
            font-size: 2rem;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 3px solid #3498db;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        
        .metrics-dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            border-left: 5px solid #3498db;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }}
        
        .metric-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        
        .metric-label {{
            font-size: 0.9rem;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }}
        
        .config-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin: 20px 0;
        }}
        
        .config-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #e9ecef;
        }}
        
        .config-label {{
            font-weight: 600;
            color: #495057;
        }}
        
        .config-value {{
            color: #2c3e50;
            font-weight: 500;
        }}
        
        .analysis-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .analysis-table th {{
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 15px 10px;
            text-align: left;
            font-weight: 600;
            font-size: 0.9rem;
        }}
        
        .analysis-table td {{
            padding: 15px 10px;
            border-bottom: 1px solid #e9ecef;
            vertical-align: middle;
        }}
        
        .analysis-table tbody tr:hover {{
            background-color: #f8f9fa;
        }}
        
        .analysis-table tbody tr:nth-child(even) {{
            background-color: #fafafa;
        }}
        
        .info-panel {{
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border: 1px solid #2196f3;
            padding: 25px;
            border-radius: 15px;
            margin: 30px 0;
        }}
        
        .info-panel h3 {{
            color: #1976d2;
            margin-bottom: 15px;
            font-size: 1.3rem;
        }}
        
        .info-panel ul {{
            list-style: none;
            padding: 0;
        }}
        
        .info-panel li {{
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid rgba(25, 118, 210, 0.2);
        }}
        
        .info-panel li:last-child {{
            border-bottom: none;
        }}
        
        .footer {{
            background: #f8f9fa;
            padding: 30px;
            text-align: center;
            border-top: 1px solid #e9ecef;
            color: #6c757d;
        }}
        
        .highlight {{
            background: linear-gradient(135deg, #fff3cd, #ffeaa7);
            border: 1px solid #ffc107;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }}
        
        .highlight h4 {{
            color: #856404;
            margin-bottom: 10px;
        }}
        
        .copy-button {{
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            margin-top: 10px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 4px rgba(0, 123, 255, 0.2);
            position: relative;
            overflow: hidden;
        }}
        
        .copy-button:hover {{
            background: linear-gradient(135deg, #0056b3, #004085);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0, 123, 255, 0.3);
        }}
        
        .copy-button:active {{
            transform: translateY(0);
            box-shadow: 0 2px 4px rgba(0, 123, 255, 0.2);
        }}
        
        .copy-button:focus {{
            outline: none;
            box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.3);
        }}
        
        .copy-button.copying {{
            background: linear-gradient(135deg, #28a745, #1e7e34);
            transform: scale(0.95);
        }}
        
        .copy-button.copied {{
            background: linear-gradient(135deg, #28a745, #1e7e34);
            animation: successPulse 0.6s ease-out;
        }}
        
        @keyframes successPulse {{
            0% {{
                transform: scale(0.95);
            }}
            50% {{
                transform: scale(1.05);
            }}
            100% {{
                transform: scale(1);
            }}
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 2rem;
            }}
            
            .metrics-dashboard {{
                grid-template-columns: 1fr;
            }}
            
            .config-grid {{
                grid-template-columns: 1fr;
            }}
            
            .analysis-table {{
                font-size: 0.8rem;
            }}
            
            .analysis-table th, .analysis-table td {{
                padding: 8px 5px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Walk Forward Analysis Report</h1>
            <div class="subtitle">Professional Trading Strategy Validation</div>
            <div class="rating {rating_class}">{rating}</div>
            <div class="recommendation">
                <strong>Recommendation:</strong> {recommendation}<br>
                <strong>Confidence Level:</strong> {confidence_level}
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>📊 Key Performance Metrics</h2>
                <div class="metrics-dashboard">
                    <div class="metric-card">
                        <div class="metric-value">{wfer:.3f}</div>
                        <div class="metric-label">Walk Forward Efficiency Ratio</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{wfer_metrics['profit_consistency']:.1%}</div>
                        <div class="metric-label">Profit Consistency</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{total_trades}</div>
                        <div class="metric-label">Total Out-of-Sample Trades</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{total_profit:.2f}</div>
                        <div class="metric-label">Total OOS Profit (USDT)</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{wfer_metrics['avg_is_profit']:.2f}%</div>
                        <div class="metric-label">Avg In-Sample Profit</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{wfer_metrics['avg_oos_profit']:.2f}%</div>
                        <div class="metric-label">Avg Out-of-Sample Profit</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{wfer_metrics['sharpe_degradation']:.2f}</div>
                        <div class="metric-label">Sharpe Ratio Degradation</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{len(walks)}</div>
                        <div class="metric-label">Walk Forward Periods</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>⚙️ Test Configuration</h2>
                <div class="config-grid">
                    <div class="config-item">
                        <span class="config-label">Strategy:</span>
                        <span class="config-value">{metadata.get('strategy', 'N/A')}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Trading Pair:</span>
                        <span class="config-value">{metadata.get('pair', 'N/A')}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Total Walks:</span>
                        <span class="config-value">{metadata.get('num_walks', 'N/A')}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">In-Sample Period:</span>
                        <span class="config-value">{metadata.get('is_window', 'N/A')} days</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Out-of-Sample Period:</span>
                        <span class="config-value">{metadata.get('oos_window', 'N/A')} days</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Epochs per Walk:</span>
                        <span class="config-value">{metadata.get('epochs', 'N/A')}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Test Period:</span>
                        <span class="config-value">{metadata.get('total_period', {}).get('start', 'N/A')} to {metadata.get('total_period', {}).get('end', 'N/A')}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Optimization Function:</span>
                        <span class="config-value">{metadata.get('hyperopt_loss', 'N/A')}</span>
                    </div>
                </div>
                
                <div class="highlight">
                    <h4>🔄 Reproduction Command</h4>
                    <p>Use this command to reproduce the same walk forward test:</p>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #007bff;">
                        <code style="font-family: 'Courier New', monospace; font-size: 0.9em; word-break: break-all; white-space: pre-wrap;">{metadata.get('original_command', 'N/A')}</code>
                    </div>
                    <button id="copyBtn" onclick="copyToClipboard()" class="copy-button">📋 Copy Command</button>
                </div>
            </div>
            
            <div class="section">
                <h2>📈 Walk-by-Walk Analysis</h2>
                <div style="overflow-x: auto;">
                    <table class="analysis-table">
                        <thead>
                            <tr>
                                <th>Walk</th>
                                <th>In-Sample Period</th>
                                <th>Out-of-Sample Period</th>
                                <th>IS Profit</th>
                                <th>IS Sharpe</th>
                                <th>IS Trades</th>
                                <th>IS Drawdown</th>
                                <th>OOS Profit</th>
                                <th>OOS Trades</th>
                                <th>OOS Win Rate</th>
                                <th>OOS Profit Factor</th>
                                <th>Efficiency</th>
                                <th>Status</th>
                                <th>IS Chart</th>
                                <th>OOS Chart</th>
                            </tr>
                        </thead>
                        <tbody>
                            {walk_analysis_rows}
                        </tbody>
                    </table>
                </div>
                <div class="info-panel">
                    <h3>Interactive Charts</h3>
                    <p>Each walk includes interactive profit charts for both in-sample (IS) and out-of-sample (OOS) periods. These charts show:</p>
                    <ul>
                        <li><strong>IS Charts:</strong> Performance during hyperopt optimization period - shows how the strategy performed during parameter tuning</li>
                        <li><strong>OOS Charts:</strong> Performance during validation period - shows real-world performance with optimized parameters</li>
                        <li><strong>Interactive Features:</strong> Hover for trade details, zoom in/out, and detailed profit curves</li>
                    </ul>
                </div>
            </div>
            
            <div class="section">
                <h2>🔧 Strategy Parameter Evolution</h2>
                <div style="overflow-x: auto;">
                    <table class="analysis-table">
                        <thead>
                            <tr>
                                {("".join(f"<th>{header}</th>" for header in param_config['headers']))}
                            </tr>
                        </thead>
                        <tbody>
                            {param_evolution_rows}
                        </tbody>
                    </table>
                </div>
                <div class="info-panel">
                    <h3>Parameter Analysis</h3>
                    <p>The strategy parameters were optimized independently for each walk, showing how the optimal parameters evolved over different market conditions. Consistent parameter ranges across walks indicate robust strategy design.</p>
                </div>
            </div>
            
            <div class="section">
                <h2>📋 Individual Trade Analysis</h2>
                <div style="overflow-x: auto;">
                    <table class="analysis-table">
                        <thead>
                            <tr>
                                <th>Walk</th>
                                <th>Trade #</th>
                                <th>Pair</th>
                                <th>Open Date</th>
                                <th>Close Date</th>
                                <th>Profit (USDT)</th>
                                <th>Profit (%)</th>
                                <th>Duration</th>
                                <th>Exit Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            {trade_details}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div class="section">
                <h2>📚 Understanding Walk Forward Analysis</h2>
                <div class="info-panel">
                    <h3>Walk Forward Efficiency Ratio (WFER)</h3>
                    <p>WFER measures how well your strategy performs in out-of-sample testing compared to in-sample optimization. It's calculated as the ratio of average out-of-sample performance to average in-sample performance.</p>
                    <ul>
                        <li><strong>WFER > 0.7:</strong> Excellent - Strategy performs well out-of-sample with minimal degradation</li>
                        <li><strong>WFER 0.5-0.7:</strong> Good - Acceptable performance degradation, suitable for deployment</li>
                        <li><strong>WFER 0.3-0.5:</strong> Caution - Significant performance drop, review strategy robustness</li>
                        <li><strong>WFER < 0.3:</strong> Poor - Likely overfitting detected, do not deploy</li>
                    </ul>
                </div>
                
                <div class="info-panel">
                    <h3>Profit Consistency</h3>
                    <p>Measures the percentage of walks that generated positive out-of-sample returns. Higher consistency indicates more reliable strategy performance across different market conditions.</p>
                </div>
                
                <div class="info-panel">
                    <h3>Parameter Stability</h3>
                    <p>Analyzes how strategy parameters evolved across different walks. Stable parameters suggest robust strategy design, while highly volatile parameters may indicate overfitting to specific market conditions.</p>
                </div>
            </div>
            
            <div class="highlight">
                <h4>🎯 Key Insights for {metadata.get('strategy', 'Strategy')}</h4>
                <p>This comprehensive walk forward analysis provides institutional-grade validation of your trading strategy. The {rating.lower()} rating is based on multiple factors including efficiency ratio, profit consistency, and parameter stability.</p>
            </div>
        </div>
        
        <div class="footer">
            <p><strong>Report Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p><strong>Session ID:</strong> {metadata.get('session_timestamp', 'N/A')}</p>
            <p><strong>Generated by:</strong> Freqtrade Walk Forward Analysis System v2.0</p>
        </div>
    </div>
    
    <script>
        function copyToClipboard() {{
            const commandText = `{metadata.get('original_command', 'N/A')}`;
            const button = document.getElementById('copyBtn');
            const originalText = button.textContent;
            
            // Show immediate feedback
            button.classList.add('copying');
            button.textContent = '📋 Copying...';
            button.disabled = true;
            
            navigator.clipboard.writeText(commandText).then(function() {{
                // Success feedback
                button.classList.remove('copying');
                button.classList.add('copied');
                button.textContent = '✅ Copied!';
                
                setTimeout(() => {{
                    button.classList.remove('copied');
                    button.textContent = originalText;
                    button.disabled = false;
                }}, 2000);
                
            }}, function(err) {{
                // Error feedback
                button.classList.remove('copying');
                button.textContent = '❌ Copy Failed';
                button.style.background = 'linear-gradient(135deg, #dc3545, #c82333)';
                
                setTimeout(() => {{
                    button.textContent = originalText;
                    button.style.background = '';
                    button.disabled = false;
                }}, 2000);
                
                console.error('Could not copy text: ', err);
                
                // Fallback: show alert with command text
                alert('Failed to copy automatically. Here is the command:\\n\\n' + commandText);
            }});
        }}
    </script>
</body>
</html>
"""
    
    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Enhanced website-ready HTML report generated: {output_file}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python walk_forward_report_enhanced.py <results_file> <output_file>")
        sys.exit(1)
    
    results_file = sys.argv[1]
    output_file = Path(sys.argv[2])
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    generate_enhanced_html_report(results, output_file)