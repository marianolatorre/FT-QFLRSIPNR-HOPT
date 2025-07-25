# pragma pylint: disable=missing-docstring, invalid-name, too-few-public-methods
# pragma pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-locals

import pandas as pd
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, CategoricalParameter, BooleanParameter
import talib.abstract as ta


class RPSROIShort(IStrategy):
    """
    RSI PNR Slope Short Strategy - ROI Exit Version
    
    Based on RSI Percentile Nearest Rank (PNR) slope indicator.
    
    Entry conditions:
    - Short: RSI PNR sell signal (rsidiffMAX crosses above 99th percentile) while VWMA slow has downward slope
    
    RSI PNR Logic:
    - rsidiffMIN = highest(RSI, lookback) - RSI
    - rsidiffMAX = RSI - lowest(RSI, lookback)  
    - Sell when rsidiffMAX crosses above its 99th percentile threshold
    
    Exit: Uses ROI table only (no exit signals)
    """
    
    # Strategy interface version
    strategy_version = 1
    
    # Optimal timeframe for the strategy
    timeframe = '15m'
    
    # Can this strategy go short?
    can_short = True
    
    # Static ROI table - disabled by default, hyperopt will override when 'roi' space is active
    minimal_roi = {
        "0": 10.0  # High ROI effectively disables ROI exits for signal-based strategies
    }
    
    # Stoploss
    stoploss = -0.08
    
    # Trailing stoploss
    trailing_stop = False
    
    # Startup candle count (max of percentile window + RSI period + VWMA slow + buffer)
    startup_candle_count: int = 400
    
    # Sell space parameters (entry signal for short)
    sell_rsi_lookback = IntParameter(5, 40, default=10, space='sell')
    sell_rsi_percentile_window = IntParameter(100, 200, default=150, space='sell')
    source_type = CategoricalParameter(['close', 'vwma', 'ema'], default='close', space='sell')
    
    # VWMA filter toggle and parameters (sell space)
    use_vwma_filter = BooleanParameter(default=True, space='sell')
    vwma_slow = IntParameter(280, 320, default=300, space='sell')
    slope_bars = IntParameter(1, 5, default=3, space='sell')
    max_slope_slow = DecimalParameter(-5.0, 5.0, default=0.0, space='sell', decimals=2)
        
    # Plot configuration for web UI (red theme for shorts)
    plot_config = {
        'main_plot': {
            'vwma_slow': {'color': '#990000', 'type': 'line'},   # Very dark red
        },
        'subplots': {
            'RSI': {
                'rsi': {'color': '#ffffff', 'type': 'line'},
            },
            'RSI PNR Sell (Entry)': {
                'rsidiffMAX': {'color': '#ff0000', 'type': 'line'},
                'rsidiffMAX_threshold': {'color': '#ffff00', 'type': 'line'},
            },
            'VWMA Slow Slope': {
                'vwma_slow_slope': {'color': '#ff3366', 'type': 'line'},
            },
            'Short Signals': {
                'rsi_pnr_sell_signal': {'color': '#ff0000', 'type': 'scatter'}  # Short entry
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
    
    def get_rsi_source(self, dataframe: DataFrame, source_type: str) -> pd.Series:
        """
        Get the RSI source based on the selected type
        """
        if source_type == 'close':
            return dataframe['close']
        elif source_type == 'vwma':
            return self.vwma(dataframe, 20)  # Standard 20-period VWMA
        elif source_type == 'ema':
            return ta.EMA(dataframe, timeperiod=20)  # Standard 20-period EMA
        else:
            return dataframe['close']  # Default fallback
    
    def calculate_rsi_pnr_sell(self, rsi_series: pd.Series, lookback: int, percentile_window: int) -> tuple:
        """
        Calculate RSI PNR components for SELL signal (short entry)
        Returns rsidiffMAX and its threshold
        """
        # Calculate rsidiffMAX for sell signal (how far RSI is above recent low)
        rsidiffMAX = rsi_series - rsi_series.rolling(window=lookback).min()
        
        # Calculate 99th percentile threshold
        rsidiffMAX_threshold = rsidiffMAX.rolling(window=percentile_window).quantile(0.99)
        
        return rsidiffMAX, rsidiffMAX_threshold
    
    def calculate_rsi_pnr_buy(self, rsi_series: pd.Series, lookback: int, percentile_window: int) -> tuple:
        """
        Calculate RSI PNR components for BUY signal (short exit)
        Returns rsidiffMIN and its threshold
        """
        # Calculate rsidiffMIN for buy signal (how far RSI is below recent high)
        rsidiffMIN = rsi_series.rolling(window=lookback).max() - rsi_series
        
        # Calculate 99th percentile threshold
        rsidiffMIN_threshold = rsidiffMIN.rolling(window=percentile_window).quantile(0.99)
        
        return rsidiffMIN, rsidiffMIN_threshold
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators for RSI PNR Slope short strategy
        """
        # Calculate VWMA slow with default period (will be optimized in populate_entry_trend)
        dataframe['vwma_slow_base'] = self.vwma(dataframe, 300)
        
        # Calculate slope angle of slow VWMA using default slope_bars (3)
        dataframe['vwma_slow_slope_base'] = self.calculate_slope_angle(dataframe['vwma_slow_base'], 3)
        
        # Calculate RSI with default parameters (will be recalculated with hyperopt params)
        rsi_source = self.get_rsi_source(dataframe, 'close')
        dataframe['rsi_base'] = ta.RSI(rsi_source, timeperiod=14)
        
        # Calculate RSI PNR for sell signal with default parameters
        rsidiffMAX, rsidiffMAX_threshold = self.calculate_rsi_pnr_sell(
            dataframe['rsi_base'], 10, 150
        )
        dataframe['rsidiffMAX_base'] = rsidiffMAX
        dataframe['rsidiffMAX_threshold_base'] = rsidiffMAX_threshold
        
        # Calculate RSI PNR for buy signal with default parameters
        rsidiffMIN, rsidiffMIN_threshold = self.calculate_rsi_pnr_buy(
            dataframe['rsi_base'], 10, 150
        )
        dataframe['rsidiffMIN_base'] = rsidiffMIN
        dataframe['rsidiffMIN_threshold_base'] = rsidiffMIN_threshold
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic: Short when RSI PNR sell signal occurs while VWMA slow has downward slope
        Use hyperopt parameters to modify base calculations
        """
        
        # Recalculate VWMA slow with hyperopt parameters if they differ from defaults
        if self.vwma_slow.value != 300 or self.slope_bars.value != 3:
            dataframe['vwma_slow'] = self.vwma(dataframe, self.vwma_slow.value)
            dataframe['vwma_slow_slope'] = self.calculate_slope_angle(dataframe['vwma_slow'], self.slope_bars.value)
        else:
            dataframe['vwma_slow'] = dataframe['vwma_slow_base']
            dataframe['vwma_slow_slope'] = dataframe['vwma_slow_slope_base']
        
        # Recalculate RSI with hyperopt parameters
        rsi_source = self.get_rsi_source(dataframe, self.source_type.value)
        dataframe['rsi'] = ta.RSI(rsi_source, timeperiod=14)
        
        # Calculate RSI PNR for sell signal with sell space hyperopt parameters
        rsidiffMAX, rsidiffMAX_threshold = self.calculate_rsi_pnr_sell(
            dataframe['rsi'], self.sell_rsi_lookback.value, self.sell_rsi_percentile_window.value
        )
        dataframe['rsidiffMAX'] = rsidiffMAX
        dataframe['rsidiffMAX_threshold'] = rsidiffMAX_threshold
        
        # Calculate crossover signals
        dataframe['rsidiffMAX_prev'] = dataframe['rsidiffMAX'].shift(1)
        dataframe['rsidiffMAX_threshold_prev'] = dataframe['rsidiffMAX_threshold'].shift(1)
        
        # RSI PNR Sell signal: rsidiffMAX crosses above its threshold (sell signal "s")
        dataframe['rsi_pnr_sell_signal'] = (
            (dataframe['rsidiffMAX'] > dataframe['rsidiffMAX_threshold']) &
            (dataframe['rsidiffMAX_prev'] <= dataframe['rsidiffMAX_threshold_prev'])
        )
        
        # Handle NaN values in slope angle
        dataframe['vwma_slow_slope_clean'] = dataframe['vwma_slow_slope'].fillna(0)
        
        # Entry conditions for short with optional VWMA filter
        if self.use_vwma_filter.value:
            short_condition = (
                dataframe['rsi_pnr_sell_signal'] &
                (dataframe['vwma_slow_slope_clean'] < self.max_slope_slow.value) &
                (dataframe['volume'] > 0)
            )
        else:
            short_condition = (
                dataframe['rsi_pnr_sell_signal'] &
                (dataframe['volume'] > 0)
            )
        
        dataframe.loc[short_condition, 'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        ROI-only exit strategy - no exit signals needed
        Exits are handled entirely by minimal_roi configuration
        """
        return dataframe