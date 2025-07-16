# Ornstein-Uhlenbeck Mean Reversion Strategy

## Overview

The Ornstein-Uhlenbeck Strategy implements a sophisticated mean reversion trading approach based on the mathematical Ornstein-Uhlenbeck process. This strategy identifies when asset prices deviate significantly from their long-term equilibrium and trades on the expectation of reversion to the mean.

## Mathematical Foundation

The strategy is based on the Ornstein-Uhlenbeck stochastic differential equation:

```
dX(t) = θ(μ - X(t))dt + σdW(t)
```

Where:
- **θ (theta)**: Speed of mean reversion - how quickly prices return to equilibrium
- **μ (mu)**: Long-term mean level - the equilibrium price level
- **σ (sigma)**: Volatility parameter - measure of randomness in the process
- **X(t)**: Log price process at time t
- **W(t)**: Wiener process (random walk component)

## Key Features

### 1. Logarithmic Price Processing
- Uses log prices for improved stationarity
- Ensures better statistical properties for mean reversion analysis
- Normalizes price movements across different price levels

### 2. Dynamic Parameter Estimation
- Rolling window calculation of OU parameters
- Adaptive to changing market conditions
- Real-time estimation of mean reversion speed and equilibrium level

### 3. Z-Score Based Signals
- Standardized deviation measurement from the mean
- Configurable entry and exit thresholds
- Reduces false signals from market noise

### 4. Half-Life Filtering
- Validates mean reversion strength using half-life calculations
- Filters out non-mean-reverting periods
- Ensures trades only in suitable market conditions

## Strategy Parameters

### Core Parameters
- **lookback_period** (50-200, default: 100): Window size for parameter estimation
- **entry_threshold** (1.0-3.0, default: 2.0): Z-score threshold for entry signals
- **exit_threshold** (0.5-1.5, default: 1.0): Z-score threshold for exit signals
- **min_half_life** (5-30, default: 10): Minimum acceptable half-life in periods
- **max_half_life** (50-200, default: 100): Maximum acceptable half-life in periods

### Risk Management
- **Stoploss**: -3% to limit downside risk
- **ROI**: Progressive ROI from 5% to 0.5% over 4 hours
- **Timeframe**: 15-minute candles for optimal signal frequency

## Entry Logic

### Long Entry
Triggered when:
- Z-score < -entry_threshold (price significantly below mean)
- Valid OU parameters exist
- Half-life within acceptable range
- Sufficient volume

### Short Entry
Triggered when:
- Z-score > entry_threshold (price significantly above mean)
- Valid OU parameters exist
- Half-life within acceptable range
- Sufficient volume

## Exit Logic

### Long Exit
- Z-score > -exit_threshold (price reverts toward mean)
- Stop loss or ROI targets hit

### Short Exit
- Z-score < exit_threshold (price reverts toward mean)
- Stop loss or ROI targets hit

## Visualization

The strategy includes comprehensive plotting:

### Main Plot
- Log price series
- OU mean (equilibrium level)
- Upper and lower entry bands

### Subplots
- Z-score with entry thresholds
- OU parameters (theta, half-life)

## Usage Recommendations

### Market Conditions
- Best suited for ranging/sideways markets
- Effective in high-liquidity pairs
- Avoid during strong trending periods

### Parameter Tuning
- Shorter lookback periods for faster adaptation
- Higher entry thresholds for more conservative entries
- Adjust half-life ranges based on asset characteristics

### Risk Considerations
- Monitor half-life stability
- Avoid trades during parameter estimation periods
- Consider market regime changes

## Implementation Notes

### Mathematical Robustness
- Uses scipy.stats for regression calculations
- Handles edge cases and numerical stability
- Validates parameter estimates before trading

### Performance Optimization
- Efficient rolling window calculations
- Vectorized operations where possible
- Minimal computational overhead

### Error Handling
- Graceful handling of insufficient data
- NaN value management
- Parameter validation checks

## Backtesting Guidelines

### Data Requirements
- At least 200 candles for initial parameter estimation
- High-quality price and volume data
- Consistent timeframe (15m recommended)

### Evaluation Metrics
- Focus on Sharpe ratio and maximum drawdown
- Monitor trade frequency and duration
- Analyze performance across different market regimes

### Hyperopt Optimization
- Use sufficient epochs for parameter convergence
- Consider multiple asset classes
- Validate results on out-of-sample data

## Advanced Considerations

### Market Regime Detection
- Monitor theta stability over time
- Detect structural breaks in mean reversion
- Adapt parameters to changing volatility

### Multi-Asset Applications
- Consider correlation effects in portfolio
- Adapt parameters per asset class
- Monitor cross-asset mean reversion

### Enhancement Opportunities
- Kalman filter for parameter estimation
- Regime-switching models
- Machine learning parameter optimization

## Conclusion

The Ornstein-Uhlenbeck Strategy provides a mathematically rigorous approach to mean reversion trading. By leveraging the well-established OU process, it offers a systematic method for identifying and exploiting temporary price dislocations in financial markets.

The strategy's strength lies in its adaptive parameter estimation and robust signal generation, making it suitable for both automated trading and manual analysis. However, careful attention to market conditions and parameter stability is essential for optimal performance.