# pragma pylint: disable=missing-docstring, invalid-name, too-few-public-methods
# pragma pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-locals

import pandas as pd
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, merge_informative_pair
import talib.abstract as ta


class VWMAStrategyATRRegime(IStrategy):
    """
    VWMA Strategy with ATR Volatility Regime Filter
    
    Uses 3 Volume Weighted Moving Averages with different lengths on 15m timeframe:
    - Fast VWMA (20 periods)
    - Medium VWMA (100 periods)  
    - Slow VWMA (300 periods)
    
    Regime Filter:
    - ATR Volatility Regime: Only enters in high volatility regime
    - Uses 4h timeframe for regime detection to avoid noise
    
    Entry conditions:
    - Long: Fast VWMA crosses above Medium VWMA while Slow VWMA has minimum upward slope
    - AND ATR > Multiplier × ATR_MA (high volatility regime)
    
    Exit: Uses stop loss and ROI
    """
    
    # Strategy interface version
    strategy_version = 1
    
    # Optimal timeframe for the strategy
    timeframe = '15m'
    
    # Can this strategy go short?
    can_short = False
    
    # Static ROI table - disabled (only exit on signal)
    minimal_roi = {
        "0": 10.0  # 100% ROI effectively disables ROI exits
    }
    
    # Stoploss
    stoploss = -0.08
    
    # Trailing stoploss
    trailing_stop = False
    
    # Startup candle count
    startup_candle_count: int = 350  # Increased for 300-period slow VWMA
    
    # Original VWMA parameters
    vwma_fast = IntParameter(10, 30, default=20, space='buy')
    vwma_medium = IntParameter(80, 120, default=100, space='buy')
    vwma_slow = IntParameter(280, 320, default=300, space='buy')
    slope_bars = IntParameter(1, 5, default=3, space='buy')
    min_slope_slow = DecimalParameter(-5.0, 5.0, default=0.0, space='buy', decimals=2)
    
    # ATR Regime parameters
    regime_timeframe = '4h'  # Higher timeframe for regime detection
    atr_period = IntParameter(10, 20, default=14, space='buy')
    atr_ma_period = IntParameter(30, 100, default=50, space='buy')
    atr_multiplier = DecimalParameter(1.0, 3.0, default=1.5, space='buy', decimals=2)
    
    # Informative pairs - define higher timeframe for the same pair
    def informative_pairs(self):
        pairs = self.dp.current_whitelist() if self.dp else []
        informative_pairs = [(pair, self.regime_timeframe) for pair in pairs]
        return informative_pairs
    
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
            'Crossover Signals': {
                'vwma_crossover_plot': {'color': '#00ff00', 'type': 'scatter'},
                'vwma_crossunder_plot': {'color': '#ff0000', 'type': 'scatter'},
            },
            'ATR Regime': {
                f'atr_{regime_timeframe}': {'color': '#00ffff', 'type': 'line'},
                f'atr_ma_{regime_timeframe}': {'color': '#ffff00', 'type': 'line'},
                f'high_vol_regime_{regime_timeframe}': {'color': '#ff00ff', 'type': 'scatter'},
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
        Populate indicators for VWMA strategy with ATR regime filter
        Calculate 3 VWMAs with different lengths on 15m timeframe
        Calculate ATR regime on 4h timeframe
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
            
            # Calculate ATR and ATR moving average on higher timeframe
            informative['atr'] = ta.ATR(informative, timeperiod=self.atr_period.value)
            informative[f'atr_ma'] = ta.SMA(informative['atr'], timeperiod=self.atr_ma_period.value)
            
            # Calculate high volatility regime
            informative['high_vol_regime'] = (
                informative['atr'] > (self.atr_multiplier.value * informative['atr_ma'])
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
        Entry logic: Long when Fast VWMA crosses above Medium VWMA while Slow VWMA has upward slope
        AND we are in high volatility regime
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
        
        # Create plotting versions
        dataframe['vwma_crossover_plot'] = dataframe['vwma_crossover'].astype(int)
        dataframe['vwma_crossunder_plot'] = dataframe['vwma_crossunder'].astype(int)
        
        # Entry conditions with regime filter
        # Handle NaN values in slope angle
        dataframe['vwma_slow_slope_clean'] = dataframe['vwma_slow_slope'].fillna(0)
        
        # Check if regime data is available
        regime_column = f'high_vol_regime_{self.regime_timeframe}'
        if regime_column in dataframe.columns:
            long_condition = (
                dataframe['vwma_crossover'] &
                (dataframe['vwma_slow_slope_clean'] > self.min_slope_slow.value) &
                (dataframe[regime_column] == 1) &  # Only enter in high volatility regime
                (dataframe['volume'] > 0)
            )
        else:
            # Fallback to original logic if regime data not available
            long_condition = (
                dataframe['vwma_crossover'] &
                (dataframe['vwma_slow_slope_clean'] > self.min_slope_slow.value) &
                (dataframe['volume'] > 0)
            )
        
        dataframe.loc[long_condition, 'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic: Exit on bearish cross (Fast VWMA crosses below Medium VWMA)
        """
        # Exit on bearish crossunder
        if 'vwma_crossunder' in dataframe.columns:
            dataframe.loc[dataframe['vwma_crossunder'], 'exit_long'] = 1
        
        return dataframe