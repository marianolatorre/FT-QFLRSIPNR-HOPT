# pragma pylint: disable=missing-docstring, invalid-name, too-few-public-methods
# pragma pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-locals

import pandas as pd
import numpy as np
from pandas import DataFrame
from datetime import datetime, timedelta
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, BooleanParameter
from freqtrade.optimize.space import SKDecimal
import talib.abstract as ta


class VWMAStrategyV3(IStrategy):
    """
    VWMA Strategy V3 Implementation - Long Only
    
    Phase 2 Risk Management Improvements:
    - ATR-based dynamic stop loss (volatility adaptive)
    - Trailing stop implementation with optimizable parameters
    - Time-based exits to prevent capital lock-up
    
    Inherited from V2:
    - Tighter stop loss range (1-5% instead of 25%)
    - Volume confirmation with threshold parameter
    
    Uses 3 Volume Weighted Moving Averages with different lengths on 15m timeframe:
    - Fast VWMA (10-30 periods)
    - Medium VWMA (80-120 periods)  
    - Slow VWMA (280-320 periods)
    
    Entry conditions:
    - Long: Fast VWMA crosses above Medium VWMA while Slow VWMA has minimum upward slope
    - Volume confirmation: Current volume > volume_threshold * average volume
    
    Exit: ATR-based stop loss, trailing stops, time-based exits, and signal exits
    """
    
    # Strategy interface version
    strategy_version = 3
    
    # Optimal timeframe for the strategy
    timeframe = '15m'
    
    # Can this strategy go short?
    can_short = False
    
    # Static ROI table - disabled (only exit on signal)
    minimal_roi = {
        "0": 10.0  # High ROI effectively disables ROI exits
    }
    
    # Stoploss - Will be overridden by ATR-based dynamic stop loss
    stoploss = -0.03  # Fallback default 3% stop loss
    use_custom_stoploss = True  # Enable custom_stoploss method
    
    # Phase 2: Trailing stop disabled - conflicts with custom_stoploss
    # Using custom_stoploss for ATR-based dynamic stops instead
    trailing_stop = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False
    
    # Startup candle count - increased for ATR calculation
    startup_candle_count: int = 350  # Increased for 300-period slow VWMA + ATR
    
    # Hyperopt parameters
    
    # VWMA periods (inherited from V1/V2)
    vwma_fast = IntParameter(10, 30, default=20, space='buy')
    vwma_medium = IntParameter(80, 120, default=100, space='buy')
    vwma_slow = IntParameter(280, 320, default=300, space='buy')
    
    # Slope parameters (inherited from V1/V2)
    slope_bars = IntParameter(1, 5, default=3, space='buy')
    min_slope_slow = DecimalParameter(-5.0, 5.0, default=0.0, space='buy', decimals=2)
    
    # Volume confirmation threshold (inherited from V2)
    volume_threshold = DecimalParameter(0.8, 2.0, default=1.2, space='buy', decimals=1)
    volume_ma_period = IntParameter(10, 30, default=20, space='buy')
    
    # Phase 2.1: ATR-based dynamic stop loss parameters
    atr_period = IntParameter(10, 20, default=14, space='buy')
    atr_multiplier = DecimalParameter(1.5, 3.0, default=2.0, space='buy', decimals=1)
    use_atr_stoploss = BooleanParameter(default=True, space='buy')
    
    # Phase 2.2: Trailing stop parameters (for potential future optimization)
    # Note: Native trailing stop uses class-level constants above
    # These could be used for custom trailing stop logic if needed
    # trailing_stop_positive_param = DecimalParameter(0.005, 0.03, default=0.01, space='buy', decimals=3)
    # trailing_stop_positive_offset_param = DecimalParameter(0.01, 0.05, default=0.02, space='buy', decimals=3)
    
    # Phase 2.3: Time-based exit parameters
    enable_time_exit = BooleanParameter(default=True, space='buy')
    max_trade_duration_hours = IntParameter(24, 168, default=72, space='buy')  # 1-7 days
    
    # Custom stoploss space for fallback fixed stop losses
    class HyperOpt:
        @staticmethod
        def stoploss_space():
            return [SKDecimal(-0.05, -0.01, decimals=3, name='stoploss')]
    
    # Plot configuration for web UI
    plot_config = {
        'main_plot': {
            'vwma_fast': {'color': '#00ff00', 'type': 'line'},
            'vwma_medium': {'color': '#0000ff', 'type': 'line'},
            'vwma_slow': {'color': '#ff0000', 'type': 'line'},
        },
        'subplots': {
            'VWMA Slow Slope': {
                'vwma_slow_slope': {'color': '#ff00ff', 'type': 'line'},
            },
            'Volume': {
                'volume': {'color': '#848484', 'type': 'bar'},
                'volume_ma': {'color': '#ffa500', 'type': 'line'},
                'volume_threshold_line': {'color': '#00ff00', 'type': 'line'},
            },
            'ATR': {
                'atr': {'color': '#ff9900', 'type': 'line'},
            },
            'Signals': {
                'buy_signal': {'color': '#00ff00', 'type': 'scatter'},
                'time_exit_signal': {'color': '#ffff00', 'type': 'scatter'},
            }
        }
    }
    
    def vwma(self, dataframe: DataFrame, period: int = 21) -> pd.Series:
        """
        Calculate Volume Weighted Moving Average
        VWMA = Sum(Close * Volume) / Sum(Volume) over period
        """
        volume_price = dataframe['close'] * dataframe['volume']
        return volume_price.rolling(window=period).sum() / dataframe['volume'].rolling(window=period).sum()
    
    def calculate_slope_angle(self, ma_series: pd.Series, slope_bars: int) -> pd.Series:
        """
        Calculate slope using: slope = (ma - ma[slopeBars]) / slopeBars
        Convert slope to angle: slopeAngle = arctan(slope) * 180 / pi
        """
        # Calculate slope over slope_bars periods
        slope = (ma_series - ma_series.shift(slope_bars)) / slope_bars
        
        # Convert slope to angle in degrees
        slope_angle = np.arctan(slope) * 180 / np.pi
        
        return slope_angle
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators for VWMA strategy V3
        Calculate 3 VWMAs with different lengths on 15m timeframe
        Add volume moving average for threshold comparison
        Phase 2: Add ATR for dynamic stop loss calculation
        """
        # Calculate base VWMAs with default periods (will be optimized in populate_entry_trend)
        dataframe['vwma_fast_base'] = self.vwma(dataframe, 20)
        dataframe['vwma_medium_base'] = self.vwma(dataframe, 100)
        dataframe['vwma_slow_base'] = self.vwma(dataframe, 300)
        
        # Calculate slope angle of slow VWMA using default slope_bars (3)
        dataframe['vwma_slow_slope_base'] = self.calculate_slope_angle(dataframe['vwma_slow_base'], 3)
        
        # Volume moving average for threshold comparison (from V2)
        dataframe['volume_ma_base'] = dataframe['volume'].rolling(window=20).mean()
        
        # Phase 2.1: Calculate ATR for dynamic stop loss
        dataframe['atr_base'] = ta.ATR(dataframe, timeperiod=14)
        
        # Initialize trade entry timestamps for time-based exits
        dataframe['trade_entry_time'] = pd.NaT
        
        # Prepare columns for future enhancements
        dataframe['rsi'] = 0  # Placeholder for future Phase 3
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade, current_time: datetime, current_rate: float, current_profit: float, after_fill: bool, **kwargs) -> float:
        """
        Phase 2.1: ATR-based dynamic stop loss implementation
        Calculate stop loss based on ATR to adapt to market volatility
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if dataframe is None or len(dataframe) == 0:
            return self.stoploss
        
        # Get the latest ATR value
        if 'atr' in dataframe.columns:
            current_atr = dataframe['atr'].iloc[-1]
        else:
            current_atr = dataframe['atr_base'].iloc[-1]
        
        if pd.isna(current_atr) or current_atr == 0:
            return self.stoploss
        
        # Only use ATR stop loss if enabled
        if not self.use_atr_stoploss.value:
            return self.stoploss
        
        # Calculate ATR-based stop loss
        # For long positions: stop_loss = -1 * (atr_multiplier * atr / entry_price)
        atr_stop_distance = (self.atr_multiplier.value * current_atr) / trade.open_rate
        atr_stoploss = -1 * atr_stop_distance
        
        # Ensure ATR stop loss is within reasonable bounds (1-10%)
        atr_stoploss = max(atr_stoploss, -0.10)  # Max 10% loss
        atr_stoploss = min(atr_stoploss, -0.01)  # Min 1% loss
        
        return atr_stoploss
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic: Long when Fast VWMA crosses above Medium VWMA while Slow VWMA has upward slope
        V2 Addition: Volume confirmation threshold
        V3 Addition: Prepare for ATR-based stop loss and time tracking
        Use hyperopt parameters to modify base calculations
        """
        
        # Native trailing stop is configured at class level
        # No need to modify trailing stop parameters dynamically
        
        # Recalculate VWMAs with hyperopt parameters if they differ from defaults
        if self.vwma_fast.value != 20:
            dataframe['vwma_fast'] = self.vwma(dataframe, self.vwma_fast.value)
        else:
            dataframe['vwma_fast'] = dataframe['vwma_fast_base']
        
        if self.vwma_medium.value != 100:
            dataframe['vwma_medium'] = self.vwma(dataframe, self.vwma_medium.value)
        else:
            dataframe['vwma_medium'] = dataframe['vwma_medium_base']
        
        if self.vwma_slow.value != 300 or self.slope_bars.value != 3:
            dataframe['vwma_slow'] = self.vwma(dataframe, self.vwma_slow.value)
            # Recalculate slope angle with hyperopt parameters
            dataframe['vwma_slow_slope'] = self.calculate_slope_angle(dataframe['vwma_slow'], self.slope_bars.value)
        else:
            dataframe['vwma_slow'] = dataframe['vwma_slow_base']
            dataframe['vwma_slow_slope'] = dataframe['vwma_slow_slope_base']
        
        # Calculate volume moving average with hyperopt parameter (from V2)
        if self.volume_ma_period.value != 20:
            dataframe['volume_ma'] = dataframe['volume'].rolling(window=self.volume_ma_period.value).mean()
        else:
            dataframe['volume_ma'] = dataframe['volume_ma_base']
        
        # Phase 2.1: Calculate ATR with hyperopt parameter
        if self.atr_period.value != 14:
            dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        else:
            dataframe['atr'] = dataframe['atr_base']
        
        # Calculate volume threshold line for plotting (from V2)
        dataframe['volume_threshold_line'] = dataframe['volume_ma'] * self.volume_threshold.value
        
        # Calculate crossover signals
        dataframe['vwma_fast_prev'] = dataframe['vwma_fast'].shift(1)
        dataframe['vwma_medium_prev'] = dataframe['vwma_medium'].shift(1)
        
        # Crossover: Fast VWMA crosses above Medium VWMA (bullish)
        dataframe['vwma_crossover'] = (
            (dataframe['vwma_fast'] > dataframe['vwma_medium']) &
            (dataframe['vwma_fast_prev'] <= dataframe['vwma_medium_prev'])
        )
        
        # Crossunder: Fast VWMA crosses below Medium VWMA (bearish)
        dataframe['vwma_crossunder'] = (
            (dataframe['vwma_fast'] < dataframe['vwma_medium']) &
            (dataframe['vwma_fast_prev'] >= dataframe['vwma_medium_prev'])
        )
        
        # Handle NaN values in slope angle
        dataframe['vwma_slow_slope_clean'] = dataframe['vwma_slow_slope'].fillna(0)
        
        # Volume confirmation (from V2)
        dataframe['volume_confirmed'] = (
            dataframe['volume'] > (dataframe['volume_ma'] * self.volume_threshold.value)
        )
        
        # Entry conditions with volume confirmation
        long_condition = (
            dataframe['vwma_crossover'] &
            (dataframe['vwma_slow_slope_clean'] > self.min_slope_slow.value) &
            dataframe['volume_confirmed'] &  # Volume threshold check
            (dataframe['volume'] > 0)
        )
        
        dataframe.loc[long_condition, 'enter_long'] = 1
        
        # Add buy signal for plotting
        dataframe.loc[long_condition, 'buy_signal'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic: 
        - Exit on bearish cross (Fast VWMA crosses below Medium VWMA)
        - Phase 2.3: Time-based exits to prevent capital lock-up
        """
        
        # Initialize time exit signal column
        dataframe['time_exit_signal'] = 0
        
        # Exit on bearish crossunder (inherited from V2)
        if 'vwma_crossunder' in dataframe.columns:
            dataframe.loc[dataframe['vwma_crossunder'], 'exit_long'] = 1
        
        # Phase 2.3: Time-based exits
        # Note: This is a simplified implementation for signal generation
        # Actual time-based exits are better handled in custom_exit() method
        # which has access to trade information
        
        return dataframe
    
    def custom_exit(self, pair: str, trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs):
        """
        Phase 2.3: Custom exit logic for time-based exits
        Exit trades that have been open longer than max_trade_duration_hours
        """
        
        # Only apply time-based exit if enabled
        if not self.enable_time_exit.value:
            return None
        
        # Calculate trade duration
        trade_duration = current_time - trade.open_date_utc.replace(tzinfo=None)
        max_duration = timedelta(hours=self.max_trade_duration_hours.value)
        
        # Exit if trade duration exceeds maximum
        if trade_duration > max_duration:
            return "time_exit"
        
        return None