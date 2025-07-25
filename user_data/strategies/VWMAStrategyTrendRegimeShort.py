# pragma pylint: disable=missing-docstring, invalid-name, too-few-public-methods
# pragma pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-locals

import pandas as pd
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, merge_informative_pair
import talib.abstract as ta


class VWMAStrategyTrendRegimeShort(IStrategy):
    """
    VWMA Short Strategy with Trend Regime Filter (EMA + ADX)
    
    Uses 3 Volume Weighted Moving Averages with different lengths on 15m timeframe:
    - Fast VWMA (20 periods)
    - Medium VWMA (100 periods)  
    - Slow VWMA (300 periods)
    
    Regime Filter:
    - Trend Regime: EMA crossover + ADX strength
    - Uses 4h timeframe for regime detection to avoid noise
    - Only enters when in trending regime (EMA_fast < EMA_slow AND ADX > threshold for shorts)
    
    Entry conditions:
    - Short: Fast VWMA crosses below Medium VWMA while Slow VWMA has minimum downward slope
    - AND we are in downtrending regime
    
    Exit: Exit on bullish cross (Fast VWMA crosses above Medium VWMA)
    """
    
    # Strategy interface version
    strategy_version = 1
    
    # Optimal timeframe for the strategy
    timeframe = '15m'
    
    # Can this strategy go short?
    can_short = True
    
    # Static ROI table - disabled (only exit on signal)
    minimal_roi = {
        "0": 10.0  # High ROI effectively disables ROI exits
    }
    
    # Stoploss
    stoploss = -0.08
    
    # Trailing stoploss
    trailing_stop = False
    
    # Startup candle count
    startup_candle_count: int = 350  # Increased for 300-period slow VWMA
    
    # Hyperopt parameters for short strategy
    vwma_fast = IntParameter(10, 30, default=20, space='sell')
    vwma_medium = IntParameter(80, 120, default=100, space='sell')
    vwma_slow = IntParameter(280, 320, default=300, space='sell')
    slope_bars = IntParameter(1, 5, default=3, space='sell')
    max_slope_slow = DecimalParameter(-5.0, 5.0, default=0.0, space='sell', decimals=2)
    
    # Trend Regime parameters
    regime_timeframe = '4h'  # Higher timeframe for regime detection
    ema_fast_period = IntParameter(30, 50, default=40, space='sell')
    ema_slow_period = IntParameter(60, 100, default=80, space='sell')
    adx_period = IntParameter(10, 20, default=14, space='sell')
    adx_threshold = IntParameter(20, 30, default=25, space='sell')
    
    # Informative pairs - define higher timeframe for the same pair
    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        informative_pairs = [(pair, self.regime_timeframe) for pair in pairs]
        return informative_pairs
    
    # Plot configuration for web UI (red theme for shorts)
    plot_config = {
        'main_plot': {
            'vwma_fast': {'color': '#ff6666', 'type': 'line'},  # Light red
            'vwma_medium': {'color': '#cc0000', 'type': 'line'},   # Dark red
            'vwma_slow': {'color': '#990000', 'type': 'line'},   # Very dark red
        },
        'subplots': {
            'VWMA Slow Slope': {
                'vwma_slow_slope': {'color': '#ff3366', 'type': 'line'},
            },
            'Short Signals': {
                'vwma_crossover_plot': {'color': '#00ff00', 'type': 'scatter'},   # Short exit
                'vwma_crossunder_plot': {'color': '#ff0000', 'type': 'scatter'},  # Short entry
            },
            'Trend Regime': {
                f'adx_{regime_timeframe}': {'color': '#00ffff', 'type': 'line'},
                f'trend_regime_short_{regime_timeframe}': {'color': '#ff00ff', 'type': 'scatter'},
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
        Populate indicators for VWMA short strategy with Trend regime filter
        Calculate 3 VWMAs with different lengths on 15m timeframe
        Calculate EMA crossover and ADX on 4h timeframe for trend regime
        """
        # Calculate base VWMAs with default periods (will be optimized in populate_entry_trend)
        dataframe['vwma_fast_base'] = self.vwma(dataframe, 20)
        dataframe['vwma_medium_base'] = self.vwma(dataframe, 100)
        dataframe['vwma_slow_base'] = self.vwma(dataframe, 300)
        
        # Calculate slope angle of slow VWMA using default slope_bars (3)
        dataframe['vwma_slow_slope_base'] = self.calculate_slope_angle(dataframe['vwma_slow_base'], 3)
        
        # Add regime filter from higher timeframe
        if self.dp:
            # Get the higher timeframe data for regime detection
            informative = self.dp.get_pair_dataframe(
                pair=metadata['pair'],
                timeframe=self.regime_timeframe
            )
            
            # Calculate EMAs on higher timeframe
            informative['ema_fast'] = ta.EMA(informative, timeperiod=self.ema_fast_period.value)
            informative['ema_slow'] = ta.EMA(informative, timeperiod=self.ema_slow_period.value)
            
            # Calculate ADX on higher timeframe
            informative['adx'] = ta.ADX(informative, timeperiod=self.adx_period.value)
            
            # Calculate trend regime for shorts
            # For short strategy: trending down when EMA_fast < EMA_slow AND ADX > threshold
            informative['trend_regime_short'] = (
                (informative['ema_fast'] < informative['ema_slow']) & 
                (informative['adx'] > self.adx_threshold.value)
            ).astype(int)
            
            # Merge informative data properly to avoid lookahead bias
            dataframe = merge_informative_pair(
                dataframe, informative,
                self.timeframe, self.regime_timeframe,
                ffill=True
            )
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic: Short when Fast VWMA crosses below Medium VWMA while Slow VWMA has downward slope
        AND we are in downtrending regime (downtrend with strong ADX)
        Use hyperopt parameters to modify base calculations
        """
        
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
        
        # Calculate crossover signals
        dataframe['vwma_fast_prev'] = dataframe['vwma_fast'].shift(1)
        dataframe['vwma_medium_prev'] = dataframe['vwma_medium'].shift(1)
        
        # Crossover: Fast VWMA crosses above Medium VWMA (bullish - exit signal for shorts)
        dataframe['vwma_crossover'] = (
            (dataframe['vwma_fast'] > dataframe['vwma_medium']) &
            (dataframe['vwma_fast_prev'] <= dataframe['vwma_medium_prev'])
        )
        
        # Crossunder: Fast VWMA crosses below Medium VWMA (bearish - entry signal for shorts)
        dataframe['vwma_crossunder'] = (
            (dataframe['vwma_fast'] < dataframe['vwma_medium']) &
            (dataframe['vwma_fast_prev'] >= dataframe['vwma_medium_prev'])
        )
        
        # Create plotting versions
        dataframe['vwma_crossover_plot'] = dataframe['vwma_crossover'].astype(int)
        dataframe['vwma_crossunder_plot'] = dataframe['vwma_crossunder'].astype(int)
        
        # Entry conditions for short with regime filter
        # Handle NaN values in slope angle
        dataframe['vwma_slow_slope_clean'] = dataframe['vwma_slow_slope'].fillna(0)
        
        # Check if regime data is available
        regime_column = f'trend_regime_short_{self.regime_timeframe}'
        if regime_column in dataframe.columns:
            # Short entry: crossunder + negative slope (less than max threshold) + downtrending regime
            short_condition = (
                dataframe['vwma_crossunder'] &
                (dataframe['vwma_slow_slope_clean'] < self.max_slope_slow.value) &
                (dataframe[regime_column] == 1) &  # Only enter in downtrending regime
                (dataframe['volume'] > 0)
            )
        else:
            # Fallback to original logic if regime data not available
            short_condition = (
                dataframe['vwma_crossunder'] &
                (dataframe['vwma_slow_slope_clean'] < self.max_slope_slow.value) &
                (dataframe['volume'] > 0)
            )
        
        dataframe.loc[short_condition, 'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic: Exit short on bullish cross (Fast VWMA crosses above Medium VWMA)
        """
        # Exit short on bullish crossover
        if 'vwma_crossover' in dataframe.columns:
            dataframe.loc[dataframe['vwma_crossover'], 'exit_short'] = 1
        
        return dataframe