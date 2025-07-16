import logging
from functools import reduce
from typing import Dict, List

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import (
    IStrategy,
    DecimalParameter,
    IntParameter,
    CategoricalParameter,
    merge_informative_pair,
    stoploss_from_open,
)

logger = logging.getLogger(__name__)


class FreqAI_Simple_Strategy(IStrategy):
    """
    FreqAI strategy that combines QFL (Quickfinger Luc) with technical indicators
    and lets FreqAI predict the next candle direction using QFL features.
    """

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Minimal ROI designed for the strategy
    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04
    }

    # Optimal stoploss designed for the strategy
    stoploss = -0.10

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Run "populate_indicators" only for new candle
    process_only_new_candles = True

    # These values can be overridden in the config
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # Strategy parameters
    buy_rsi_enabled = CategoricalParameter([True, False], default=True, space="buy")
    buy_rsi = IntParameter(20, 40, default=30, space="buy")
    
    sell_rsi_enabled = CategoricalParameter([True, False], default=True, space="sell")
    sell_rsi = IntParameter(60, 80, default=70, space="sell")

    # QFL Parameters
    qfl_timeframe = '1h'  # Higher timeframe for QFL base detection
    volume_ma_period = IntParameter(5, 10, default=6, space='buy')
    buy_percentage = DecimalParameter(2.0, 5.0, default=3.5, space='buy')
    sell_percentage = DecimalParameter(2.0, 5.0, default=3.5, space='sell') 
    max_base_age = IntParameter(0, 50, default=0, space='buy')  # 0 = disabled
    allow_consecutive_signals = True

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        """
        # Add higher timeframe for QFL if different from main timeframe
        pairs = []
        if self.qfl_timeframe != self.timeframe:
            # We'll get the pair dynamically in populate_indicators
            # For now, return empty list since we handle this in populate_indicators
            pass
        return pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators that will be used by FreqAI for feature engineering
        """
        # === BASIC TECHNICAL INDICATORS ===
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lowerband']) / (dataframe['bb_upperband'] - dataframe['bb_lowerband'])
        
        # EMA
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=26)
        
        # SMA
        dataframe['sma_short'] = ta.SMA(dataframe, timeperiod=10)
        dataframe['sma_long'] = ta.SMA(dataframe, timeperiod=30)
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # ADX
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # Volume indicators
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        # Price action features
        dataframe['price_change'] = dataframe['close'].pct_change()
        dataframe['high_low_ratio'] = dataframe['high'] / dataframe['low']
        dataframe['close_open_ratio'] = dataframe['close'] / dataframe['open']
        
        # Volatility
        dataframe['volatility'] = dataframe['close'].rolling(window=20).std()

        # === QFL INDICATORS ===
        # Volume moving average for QFL
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=self.volume_ma_period.value)
        
        # Get QFL indicators from higher timeframe or calculate directly
        if self.qfl_timeframe == self.timeframe:
            # Calculate QFL indicators on current timeframe
            dataframe = self.calculate_qfl_indicators(dataframe)
            dataframe['qfl_fractal_up'] = dataframe['fractal_up']
            dataframe['qfl_fractal_down'] = dataframe['fractal_down']
            dataframe['qfl_base_age'] = dataframe['base_age']
        else:
            # Get higher timeframe data for QFL base detection
            if self.dp:
                qfl_tf_data = self.dp.get_pair_dataframe(
                    pair=metadata['pair'], 
                    timeframe=self.qfl_timeframe
                )
                
                if not qfl_tf_data.empty:
                    # Calculate QFL indicators on higher timeframe
                    qfl_tf_data = self.calculate_qfl_indicators(qfl_tf_data)
                    
                    # Merge with current timeframe
                    dataframe = merge_informative_pair(
                        dataframe, 
                        qfl_tf_data, 
                        self.timeframe, 
                        self.qfl_timeframe, 
                        ffill=True
                    )
                    
                    # Rename columns for easier access
                    dataframe['qfl_fractal_up'] = dataframe[f'fractal_up_{self.qfl_timeframe}']
                    dataframe['qfl_fractal_down'] = dataframe[f'fractal_down_{self.qfl_timeframe}']
                    dataframe['qfl_base_age'] = dataframe[f'base_age_{self.qfl_timeframe}']
                    
                    # Clean up temporary columns
                    cols_to_drop = [col for col in dataframe.columns if col.endswith(f'_{self.qfl_timeframe}')]
                    dataframe.drop(columns=cols_to_drop, inplace=True)

        # === FREQAI QFL FEATURES ===
        # Fill NaN values for calculations
        dataframe['qfl_fractal_down'] = dataframe['qfl_fractal_down'].fillna(method='ffill')
        dataframe['qfl_fractal_up'] = dataframe['qfl_fractal_up'].fillna(method='ffill')
        dataframe['qfl_base_age'] = dataframe['qfl_base_age'].fillna(0)

        # 1. Value of qfl_fractal_down (already available)
        # 2. Difference in percentage between qfl_fractal_down and the price
        dataframe['qfl_fractal_down_pct_diff'] = (
            (dataframe['close'] - dataframe['qfl_fractal_down']) / 
            dataframe['qfl_fractal_down'] * 100
        ).fillna(0)
        
        # 3. Age of the base (qfl_base_age) - already available
        
        # Additional QFL-derived features for FreqAI
        dataframe['qfl_fractal_up_pct_diff'] = (
            (dataframe['close'] - dataframe['qfl_fractal_up']) / 
            dataframe['qfl_fractal_up'] * 100
        ).fillna(0)
        
        # Distance ratios
        dataframe['qfl_fractal_distance_ratio'] = (
            dataframe['qfl_fractal_down'] / dataframe['qfl_fractal_up']
        ).fillna(1)
        
        # QFL buy/sell thresholds for features
        dataframe['qfl_buy_threshold'] = 100 - self.buy_percentage.value
        dataframe['qfl_sell_threshold'] = 100 + self.sell_percentage.value
        
        # QFL signal strength (how close to trigger)
        dataframe['qfl_buy_strength'] = (
            dataframe['qfl_buy_threshold'] - (100 * dataframe['close'] / dataframe['qfl_fractal_down'])
        ).fillna(0)
        
        dataframe['qfl_sell_strength'] = (
            (100 * dataframe['close'] / dataframe['qfl_fractal_up']) - dataframe['qfl_sell_threshold']
        ).fillna(0)
        
        return dataframe

    def calculate_qfl_indicators(self, dataframe: DataFrame) -> DataFrame:
        """
        Calculate QFL fractals and bases - adapted from QFL_Strategy.py
        """
        # Volume moving average for fractal validation
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=self.volume_ma_period.value)
        
        # Fractal detection
        # Up fractal: high[3]>high[4] and high[4]>high[5] and high[2]<high[3] and high[1]<high[2] and volume[3]>vam[3]
        dataframe['fractal_up_condition'] = (
            (dataframe['high'].shift(3) > dataframe['high'].shift(4)) &
            (dataframe['high'].shift(4) > dataframe['high'].shift(5)) &
            (dataframe['high'].shift(2) < dataframe['high'].shift(3)) &
            (dataframe['high'].shift(1) < dataframe['high'].shift(2)) &
            (dataframe['volume'].shift(3) > dataframe['volume_ma'].shift(3))
        )
        
        # Down fractal: low[3]<low[4] and low[4]<low[5] and low[2]>low[3] and low[1]>low[2] and volume[3]>vam[3]
        dataframe['fractal_down_condition'] = (
            (dataframe['low'].shift(3) < dataframe['low'].shift(4)) &
            (dataframe['low'].shift(4) < dataframe['low'].shift(5)) &
            (dataframe['low'].shift(2) > dataframe['low'].shift(3)) &
            (dataframe['low'].shift(1) > dataframe['low'].shift(2)) &
            (dataframe['volume'].shift(3) > dataframe['volume_ma'].shift(3))
        )
        
        # Track fractal levels
        dataframe['fractal_up'] = np.nan
        dataframe['fractal_down'] = np.nan
        
        # Set fractal levels when conditions are met
        dataframe.loc[dataframe['fractal_up_condition'], 'fractal_up'] = dataframe['high'].shift(3)
        dataframe.loc[dataframe['fractal_down_condition'], 'fractal_down'] = dataframe['low'].shift(3)
        
        # Forward fill fractal levels
        dataframe['fractal_up'] = dataframe['fractal_up'].ffill()
        dataframe['fractal_down'] = dataframe['fractal_down'].ffill()
        
        # Calculate base age
        dataframe['base_changed'] = dataframe['fractal_down'] != dataframe['fractal_down'].shift(1)
        dataframe['base_age'] = 0
        
        # Calculate bars since base change
        base_change_indices = dataframe[dataframe['base_changed']].index
        for i, idx in enumerate(dataframe.index):
            if len(base_change_indices) > 0:
                recent_changes = base_change_indices[base_change_indices <= idx]
                if len(recent_changes) > 0:
                    last_change = recent_changes[-1]
                    dataframe.loc[idx, 'base_age'] = idx - last_change
        
        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        Combined QFL + FreqAI entry logic
        """
        conditions = []
        
        # === QFL CONDITIONS ===
        # Age condition for QFL base
        qfl_age_condition = (
            (self.max_base_age.value == 0) | 
            (df['qfl_base_age'] < self.max_base_age.value)
        )
        
        # QFL buy condition: price falls X% below down fractal
        df['price_pct_below_fractal'] = 100 * (df['close'] / df['qfl_fractal_down'])
        df['buy_threshold'] = 100 - self.buy_percentage.value
        
        qfl_buy_condition = (
            (df['price_pct_below_fractal'] < df['buy_threshold']) &
            qfl_age_condition &
            (df['qfl_fractal_down'].notna()) &
            (df['volume'] > 0)
        )
        
        # === FREQAI CONDITIONS ===
        freqai_bullish = False
        if '&-s_close' in df.columns and 'do_predict' in df.columns:
            freqai_bullish = (
                (df['&-s_close'] > df['close']) &  # FreqAI predicts price will go up
                (df['do_predict'] == 1)  # Only when FreqAI is active
            )
        
        # === TECHNICAL CONDITIONS ===
        # Basic RSI condition
        rsi_condition = True
        if self.buy_rsi_enabled.value:
            rsi_condition = df['rsi'] < self.buy_rsi.value
        
        # Volume condition
        volume_condition = df['volume'] > df['volume_sma']
        
        # === COMBINED ENTRY LOGIC ===
        # Option 1: QFL + FreqAI confirmation
        qfl_freqai_entry = qfl_buy_condition
        if isinstance(freqai_bullish, pd.Series):
            qfl_freqai_entry = qfl_freqai_entry & freqai_bullish
        
        # Option 2: Strong FreqAI signal even without QFL
        strong_freqai_entry = False
        if isinstance(freqai_bullish, pd.Series):
            strong_freqai_entry = (
                freqai_bullish & 
                rsi_condition & 
                volume_condition &
                (df['qfl_buy_strength'] > -2.0)  # Not too far from QFL level
            )
        
        # Final entry condition
        final_entry = qfl_freqai_entry
        if isinstance(strong_freqai_entry, pd.Series):
            final_entry = final_entry | strong_freqai_entry
        
        df.loc[final_entry, 'enter_long'] = 1
        
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        Combined QFL + FreqAI exit logic
        """
        # === QFL EXIT CONDITIONS ===
        # QFL exit: price rises X% above up fractal
        qfl_exit_condition = (
            (100 * (df['close'] / df['qfl_fractal_up']) > (100 + self.sell_percentage.value)) &
            (df['qfl_fractal_up'].notna())
        )
        
        # === FREQAI EXIT CONDITIONS ===
        freqai_bearish = False
        if '&-s_close' in df.columns and 'do_predict' in df.columns:
            freqai_bearish = (
                (df['&-s_close'] < df['close']) &  # FreqAI predicts price will go down
                (df['do_predict'] == 1)  # Only when FreqAI is active
            )
        
        # === TECHNICAL EXIT CONDITIONS ===
        # RSI overbought condition
        rsi_exit = False
        if self.sell_rsi_enabled.value:
            rsi_exit = df['rsi'] > self.sell_rsi.value
        
        # === COMBINED EXIT LOGIC ===
        # Option 1: QFL exit signal
        final_exit = qfl_exit_condition
        
        # Option 2: Strong FreqAI bearish + RSI overbought
        if isinstance(freqai_bearish, pd.Series):
            strong_freqai_exit = freqai_bearish & rsi_exit if rsi_exit is not False else freqai_bearish
            final_exit = final_exit | strong_freqai_exit
        
        df.loc[final_exit, 'exit_long'] = 1
        
        return df

    def leverage(self, pair: str, current_time: 'datetime', current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        """
        Customize leverage for each new trade. This method is only called in futures mode.
        """
        return 1.0