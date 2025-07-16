# VWMA Strategy V2 Improvements

## Overview
This document tracks the incremental improvements to the VWMA strategy based on walk-forward analysis and best practices research.

## Baseline Performance (V1)
- **Long Strategy**: 28.25% profit, 31.6% win rate, Sortino 3.87
- **Short Strategy**: 32.10% profit, 33.7% win rate, Sortino 5.16
- **Walk-Forward Period**: 12 months (12 walks, 120/30 day windows)
- **Issues**: Low win rate, high trade frequency, wide stop losses

## Improvement Phases

### Phase 1: Foundation Improvements ⏳
**Status**: In Development

#### 1.1 Tighter Stop Loss Range
- **Current**: -0.251 (25.1%) for long, -0.026 (2.6%) for short
- **Proposed**: -0.01 to -0.05 (1-5%) range for both
- **Rationale**: Better risk management, reduce large losses
- **Implementation**: Custom stoploss_space() method using SKDecimal(-0.05, -0.01)
- **Usage**: `freqtrade hyperopt --spaces stoploss` to optimize
- **Testing**: Compare max drawdown and profit factor

#### 1.2 Volume Confirmation
- **Current**: Only checks volume > 0
- **Proposed**: Add volume_threshold parameter (1.0-2.0)
- **Entry Condition**: Current volume > volume_threshold * average volume
- **Rationale**: Filter out low-conviction moves
- **Implementation**: Calculate rolling volume average, add threshold check

### Phase 2: Risk Management ✅
**Status**: Implemented in V3

#### 2.1 ATR-Based Dynamic Stop Loss
- **Implementation**: `custom_stoploss()` method using ATR-based calculation
- **Parameters**: atr_period (10-20), atr_multiplier (1.5-3.0), use_atr_stoploss (bool)
- **Formula**: `stop_loss = -1 * (atr_multiplier * ATR / entry_price)`
- **Bounds**: Limited to 1-10% loss range for safety
- **Rationale**: Adapt to market volatility instead of fixed percentage

#### 2.2 Trailing Stop Implementation
- **Implementation**: Dynamic trailing stop with optimizable parameters
- **Parameters**: trailing_stop_positive_param (0.005-0.03), trailing_stop_positive_offset_param (0.01-0.05)
- **Features**: Applied dynamically in `populate_entry_trend()`
- **Rationale**: Lock in profits on winning trades while allowing upside potential

#### 2.3 Time-Based Exits
- **Implementation**: `custom_exit()` method with trade duration tracking
- **Parameters**: enable_time_exit (bool), max_trade_duration_hours (24-168)
- **Logic**: Exit trades older than max duration to prevent capital lock-up
- **Rationale**: Prevent stale trades from tying up capital indefinitely

### Phase 3: Entry Refinement 📋
**Status**: Planned

#### 3.1 RSI Confluence Filter
- **Proposed**: Add RSI confirmation for entries
- **Long Entry**: RSI > rsi_buy_threshold (45-55)
- **Short Entry**: RSI < rsi_sell_threshold (45-55)
- **Rationale**: Confirm momentum direction

#### 3.2 Trend Confirmation
- **Proposed**: Price position relative to slow VWMA
- **Long Entry**: Close > slow VWMA
- **Short Entry**: Close < slow VWMA
- **Rationale**: Trade with the major trend

#### 3.3 Volatility Filter
- **Proposed**: Minimum ATR threshold for entries
- **Parameters**: min_atr_threshold (0.001-0.005)
- **Rationale**: Avoid low volatility periods

### Phase 4: Advanced Features 📋
**Status**: Future

#### 4.1 Dynamic Position Sizing
- **Proposed**: Adjust position size based on ATR
- **Implementation**: Lower size in high volatility

#### 4.2 Multi-Timeframe Confirmation
- **Proposed**: Check higher timeframe trend
- **Implementation**: 1h or 4h VWMA alignment

#### 4.3 Market Regime Detection
- **Proposed**: Identify trending vs ranging markets
- **Implementation**: ADX or similar indicator

## Testing Protocol

### For Each Improvement:
1. **Baseline Test**: Run walk-forward with current version
2. **Improvement Test**: Run walk-forward with single improvement
3. **Metrics to Track**:
   - Total profit %
   - Win rate %
   - Profit factor
   - Sortino ratio
   - Maximum drawdown
   - Number of trades
   - Average trade duration

### Success Criteria:
- Win rate improvement > 5%
- Profit factor > 1.5
- Sortino ratio improvement
- Walk-Forward Efficiency > 60%

## Implementation Log

### Version 2.0.0 (Base)
- **Date**: [TBD]
- **Changes**: 
  - Fixed stoploss optimization to use proper Freqtrade stoploss space
  - Added custom stoploss_space() method for 1-5% range
  - Volume confirmation with configurable threshold
  - Removed incorrect stoploss parameter from buy/sell space
- **Results**: [Pending]

### Version 3.0.0 (Phase 2 Risk Management)
- **Date**: [TBD]
- **Files**: VWMAStrategyV3.py, VWMAStrategyV3Short.py, run_VWMA_v3.sh
- **Changes**: 
  - ATR-based dynamic stop loss with custom_stoploss() method
  - Trailing stop implementation with optimizable parameters
  - Time-based exits to prevent capital lock-up
  - Enhanced parameter optimization spaces for risk management
  - Improved plot configuration with ATR visualization
- **Testing**: Use run_VWMA_v3.sh for walk-forward analysis
- **Results**: [Pending walk-forward testing]

### Version 2.1.0
- **Date**: [TBD]
- **Changes**: [To be added after Phase 1 testing]
- **Results**: [Pending]

## V3 Technical Implementation Details

### ATR-Based Dynamic Stop Loss:
- **Method**: `custom_stoploss()` called by Freqtrade engine
- **Calculation**: Uses latest ATR value from dataframe
- **Fallback**: Returns fixed stoploss if ATR unavailable or disabled
- **Safety**: Bounded between 1-10% loss to prevent extreme stops

### Trailing Stop Configuration:
- **Dynamic Application**: Parameters applied in `populate_entry_trend()`
- **Optimization**: Both positive threshold and offset are hyperopt parameters
- **Integration**: Works with Freqtrade's built-in trailing stop mechanism

### Time-Based Exit Logic:
- **Method**: `custom_exit()` for trade duration tracking
- **Comparison**: Uses `trade.open_date_utc` vs `current_time`
- **Flexibility**: Can be enabled/disabled via hyperopt parameter
- **Exit Reason**: Returns "time_exit" for identification

## Notes

### Walk-Forward Configuration Considerations:
- Current: 120/30 days, 12 walks, 1000 epochs
- V3 Testing: Same configuration for consistency
- Consider: 90/20 days for faster adaptation
- Consider: Anchored walk-forward for trend-following

### Parameter Optimization Strategy:
- V3 adds 6 new parameters for risk management
- Start with fewer parameters to avoid overfitting
- Add parameters incrementally
- Use different loss functions for different goals

### Risk Management Priority:
1. ✅ Stop loss optimization (Phase 1 - V2)
2. ✅ Dynamic ATR stops (Phase 2 - V3)
3. ✅ Trailing stops (Phase 2 - V3)
4. ✅ Time-based exits (Phase 2 - V3)
5. 📋 Position sizing (Phase 4 - Future)