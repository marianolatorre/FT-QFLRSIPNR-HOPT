# pragma pylint: disable=missing-docstring, invalid-name, too-few-public-methods
# pragma pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-locals

import pandas as pd
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from freqtrade.optimize.space import SKDecimal


class VWMAStrategyV2(IStrategy):
    """
    VWMA Strategy V2 Implementation - Long Only
    
    Improvements from V1:
    - Tighter stop loss range (1-5% instead of 25%)
    - Volume confirmation with threshold parameter
    - Prepared for future enhancements (ATR, RSI, etc.)
    
    Uses 3 Volume Weighted Moving Averages with different lengths on 15m timeframe:
    - Fast VWMA (10-30 periods)
    - Medium VWMA (80-120 periods)  
    - Slow VWMA (280-320 periods)
    
    Entry conditions:
    - Long: Fast VWMA crosses above Medium VWMA while Slow VWMA has minimum upward slope
    - Volume confirmation: Current volume > volume_threshold * average volume
    
    Exit: Uses stop loss and exit signals
    """
    
    # Strategy interface version
    strategy_version = 2
    
    # Optimal timeframe for the strategy
    timeframe = '15m'
    
    # Can this strategy go short?
    can_short = False
    
    # Static ROI table - disabled (only exit on signal)
    minimal_roi = {
        "0": 10.0  # 100% ROI effectively disables ROI exits
    }
    
    # Stoploss - IMPROVED: Tighter range for better risk management
    stoploss = -0.03  # Default 3% stop loss
    
    # Trailing stoploss - Prepared for Phase 2
    trailing_stop = False
    trailing_stop_positive = None
    trailing_stop_positive_offset = 0.0
    trailing_only_offset_is_reached = False
    
    # Startup candle count
    startup_candle_count: int = 350  # Increased for 300-period slow VWMA
    
    # Hyperopt parameters
    
    # VWMA periods (unchanged from V1)
    vwma_fast = IntParameter(10, 30, default=20, space='buy')
    vwma_medium = IntParameter(80, 120, default=100, space='buy')
    vwma_slow = IntParameter(280, 320, default=300, space='buy')
    
    # Slope parameters (unchanged from V1)
    slope_bars = IntParameter(1, 5, default=3, space='buy')
    min_slope_slow = DecimalParameter(-5.0, 5.0, default=0.0, space='buy', decimals=2)
    
    # NEW: Volume confirmation threshold
    volume_threshold = DecimalParameter(0.8, 2.0, default=1.2, space='buy', decimals=1)
    
    # Volume moving average period for comparison
    volume_ma_period = IntParameter(10, 30, default=20, space='buy')
    
    # Custom stoploss space for 1-5% range (tighter than default -35% to -2%)
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
            'Signals': {
                'buy_signal': {'color': '#00ff00', 'type': 'scatter'},
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
        Populate indicators for VWMA strategy V2
        Calculate 3 VWMAs with different lengths on 15m timeframe
        Add volume moving average for threshold comparison
        """
        # Calculate base VWMAs with default periods (will be optimized in populate_entry_trend)
        dataframe['vwma_fast_base'] = self.vwma(dataframe, 20)
        dataframe['vwma_medium_base'] = self.vwma(dataframe, 100)
        dataframe['vwma_slow_base'] = self.vwma(dataframe, 300)
        
        # Calculate slope angle of slow VWMA using default slope_bars (3)
        dataframe['vwma_slow_slope_base'] = self.calculate_slope_angle(dataframe['vwma_slow_base'], 3)
        
        # NEW: Calculate volume moving average for threshold comparison
        dataframe['volume_ma_base'] = dataframe['volume'].rolling(window=20).mean()
        
        # Prepare columns for future enhancements
        # These will be populated in future phases
        dataframe['atr'] = 0  # Placeholder for ATR
        dataframe['rsi'] = 0  # Placeholder for RSI
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic: Long when Fast VWMA crosses above Medium VWMA while Slow VWMA has upward slope
        V2 Addition: Volume confirmation threshold
        Use hyperopt parameters to modify base calculations
        """
        
        # Stoploss is now handled by Freqtrade's stoploss optimization space
        # No need to manually set it here
        
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
        
        # NEW: Calculate volume moving average with hyperopt parameter
        if self.volume_ma_period.value != 20:
            dataframe['volume_ma'] = dataframe['volume'].rolling(window=self.volume_ma_period.value).mean()
        else:
            dataframe['volume_ma'] = dataframe['volume_ma_base']
        
        # Calculate volume threshold line for plotting
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
        
        # NEW: Volume confirmation
        dataframe['volume_confirmed'] = (
            dataframe['volume'] > (dataframe['volume_ma'] * self.volume_threshold.value)
        )
        
        # Entry conditions with volume confirmation
        long_condition = (
            dataframe['vwma_crossover'] &
            (dataframe['vwma_slow_slope_clean'] > self.min_slope_slow.value) &
            dataframe['volume_confirmed'] &  # NEW: Volume threshold check
            (dataframe['volume'] > 0)
        )
        
        dataframe.loc[long_condition, 'enter_long'] = 1
        
        # Add buy signal for plotting
        dataframe.loc[long_condition, 'buy_signal'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic: Exit on bearish cross (Fast VWMA crosses below Medium VWMA)
        Future: Will add time-based exits and other conditions
        """
        # Exit on bearish crossunder
        if 'vwma_crossunder' in dataframe.columns:
            dataframe.loc[dataframe['vwma_crossunder'], 'exit_long'] = 1
        
        return dataframe