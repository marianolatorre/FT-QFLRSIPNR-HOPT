# pragma pylint: disable=missing-docstring, invalid-name, too-few-public-methods
# pragma pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-locals

import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, CategoricalParameter, merge_informative_pair
import talib.abstract as ta


class QFLRSI_Strategy(IStrategy):
    """
    QFL + RSI Strategy Implementation
    Based on the Pine Script QFL single TF v1.3 + RSI Percentile Rank
    
    - Detects fractal highs/lows with volume confirmation
    - Uses higher timeframe for base detection
    - Enters on QFL + RSI percentile conditions
    - Exits on RSI 99% percentile
    """
    
    # Strategy interface version
    strategy_version = 1
    
    # Optimal timeframe for the strategy
    timeframe = '1h'
    
    # Can this strategy go short?
    can_short = False
    
    # Only allow one trade at a time
    max_open_trades = 1
    
    # Minimal ROI disabled - using RSI exit signals
    minimal_roi = {
        "0": 10
    }
    
    # Stoploss disabled - using RSI exit signals
    stoploss = -0.99
    
    # Trailing stoploss
    trailing_stop = False
    
    # Startup candle count
    startup_candle_count: int = 200
    
    # Plot configuration for web UI
    plot_config = {
        'main_plot': {
            'qfl_fractal_down': {
                'color': '#ba6670',
                'type': 'scatter',
                'scatterSymbolSize': 3
            },
            'atr_entry_threshold': {
                'color': '#c9bba5',
                'type': 'scatter',
                'scatterSymbolSize': 2
            }
        },
        'subplots': {
            'erherh': {
                'rsi': {
                    'color': '#0026ff',
                    'type': 'line'
                },
                'rsi_entry_level': {
                    'color': '#648951',
                    'type': 'scatter',
                    'scatterSymbolSize': 3
                },
                'rsi_exit_level': {
                    'color': '#ff0000',
                    'type': 'scatter',
                    'scatterSymbolSize': 3
                }
            }
        }
    }
    
    # QFL Parameters (equivalent to Pine Script inputs)
    # Make QFL timeframe configurable - options: '1h', '2h', '4h' for base detection
    qfl_timeframe = '1h'  # Higher timeframe for base detection
    volume_ma_period = IntParameter(5, 10, default=6, space='buy')
    
    # QFL entry method: percentage vs ATR-based
    use_atr_entry = True  # Set to False to use percentage-based entry
    buy_percentage = 3.5 #DecimalParameter(2.0, 5.0, default=3.5, space='buy')  # Used when use_atr_entry=False
    atr_multiplier = CategoricalParameter([1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0], default=2.0, space='buy')  # ATR multiplier for entry
    atr_period = CategoricalParameter([10, 12, 14, 16, 20], default=14, space='buy')  # ATR calculation period
    
    sell_percentage = 3.5 #DecimalParameter(2.0, 5.0, default=3.5, space='sell') 
    max_base_age = 0 #IntParameter(0, 50, default=0, space='buy')  # 0 = disabled
    allow_consecutive_signals = True  # Pine: allowConsecutiveSignals
    
    # RSI Parameters
    rsi_length = 14
    # rsi_timeframe = '15m'  # RSI timeframe (15m, 30m, 1h, 4h)
    rsi_lookback = 150  # Lookback period for percentile rank calculation
    rsi_entry_percentile = DecimalParameter(0.1, 5.0, default=1.0, space='buy')  # Entry percentile threshold
    rsi_exit_percentile = DecimalParameter(95.0, 99.9, default=99.0, space='sell')  # Exit percentile threshold
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators for QFL strategy
        """
        # Volume moving average
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=self.volume_ma_period.value)
        
        # RSI calculation on current timeframe
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=self.rsi_length)
        
        # ATR calculation (always calculate for plotting purposes)
        dataframe['atr'] = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=self.atr_period.value)
        
        # Calculate RSI Percentile Rank (PNR) with 150 candle lookback
        dataframe['rsi_pnr'] = dataframe['rsi'].rolling(window=self.rsi_lookback, min_periods=self.rsi_lookback).apply(
            lambda x: (x.iloc[-1] <= x).sum() / len(x) * 100, raw=False
        )
        
        # Calculate dynamic percentile levels based on parameters
        dataframe['rsi_entry_level'] = dataframe['rsi'].rolling(window=self.rsi_lookback, min_periods=self.rsi_lookback).quantile(self.rsi_entry_percentile.value / 100)
        dataframe['rsi_exit_level'] = dataframe['rsi'].rolling(window=self.rsi_lookback, min_periods=self.rsi_lookback).quantile(self.rsi_exit_percentile.value / 100)
        
        # Individual condition indicators will be set in entry logic
        
        # Since we're running 1h chart with 1h QFL timeframe, calculate directly on current timeframe
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
        
        # Debug logging (disabled)
        # print(f"DEBUG: QFL timeframe: {self.qfl_timeframe}, Strategy timeframe: {self.timeframe}")
        # print(f"DEBUG: Fractal up count: {dataframe['qfl_fractal_up'].notna().sum()}")
        # print(f"DEBUG: Fractal down count: {dataframe['qfl_fractal_down'].notna().sum()}")
        # if not dataframe['qfl_fractal_down'].isna().all():
        #     print(f"DEBUG: Latest fractal down: {dataframe['qfl_fractal_down'].iloc[-1]}")
        
        return dataframe
    
    def calculate_qfl_indicators(self, dataframe: DataFrame) -> DataFrame:
        """
        Calculate QFL fractals and bases on higher timeframe data
        Translates the Pine Script QFL logic to Python
        """
        # Volume moving average for fractal validation
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=self.volume_ma_period.value)
        
        # Fractal detection (Pine: up/down conditions)
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
        
        # Track fractal levels (Pine: fractalupF() and fractaldownF() functions)
        dataframe['fractal_up'] = np.nan
        dataframe['fractal_down'] = np.nan
        
        # Set fractal levels when conditions are met
        dataframe.loc[dataframe['fractal_up_condition'], 'fractal_up'] = dataframe['high'].shift(3)
        dataframe.loc[dataframe['fractal_down_condition'], 'fractal_down'] = dataframe['low'].shift(3)
        
        # Forward fill fractal levels (Pine: fd := down ? low[3] : nz(fd[1]))
        dataframe['fractal_up'] = dataframe['fractal_up'].ffill()
        dataframe['fractal_down'] = dataframe['fractal_down'].ffill()
        
        # Calculate base age (Pine: barssince(fuptf != fuptf[1]))
        dataframe['base_changed'] = dataframe['fractal_down'] != dataframe['fractal_down'].shift(1)
        dataframe['base_age'] = 0
        
        # Calculate bars since base change
        base_change_indices = dataframe[dataframe['base_changed']].index
        for i, idx in enumerate(dataframe.index):
            if len(base_change_indices) > 0:
                # Find most recent base change
                recent_changes = base_change_indices[base_change_indices <= idx]
                if len(recent_changes) > 0:
                    last_change = recent_changes[-1]
                    dataframe.loc[idx, 'base_age'] = idx - last_change
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        QFL Entry Logic
        Pine: buy = 100*(close/fdowntf) < 100 - percentage and agecond
        """
        # Age condition (Pine: agecond = maxbaseage == 0 or age < maxbaseage)
        age_condition = (
            (self.max_base_age == 0) | 
            (dataframe['qfl_base_age'] < self.max_base_age)
        )
        
        # QFL entry condition: ATR-based or percentage-based
        if self.use_atr_entry:
            # ATR-based entry: price below fractal by X ATRs
            dataframe['atr_entry_threshold'] = dataframe['qfl_fractal_down'] - (dataframe['atr'] * self.atr_multiplier.value)
            qfl_buy_condition = (
                (dataframe['close'] < dataframe['atr_entry_threshold']) &
                age_condition &
                (dataframe['qfl_fractal_down'].notna()) &
                (dataframe['atr'].notna()) &
                (dataframe['volume'] > 0)
            )
        else:
            # Percentage-based entry: price below fractal by X%
            dataframe['price_pct_below_fractal'] = 100 * (dataframe['close'] / dataframe['qfl_fractal_down'])
            dataframe['buy_threshold'] = 100 - self.buy_percentage
            qfl_buy_condition = (
                (dataframe['price_pct_below_fractal'] < dataframe['buy_threshold']) &
                age_condition &
                (dataframe['qfl_fractal_down'].notna()) &
                (dataframe['volume'] > 0)
            )
            # Still calculate ATR threshold for plotting comparison
            if 'atr' in dataframe.columns:
                dataframe['atr_entry_threshold'] = dataframe['qfl_fractal_down'] - (dataframe['atr'] * self.atr_multiplier.value)
            else:
                dataframe['atr_entry_threshold'] = np.nan
        
        # RSI condition: RSI below its percentile level (oversold)
        rsi_buy_condition = dataframe['rsi'] < dataframe['rsi_entry_level']
        
        # Set individual condition indicators for plotting
        # Use NaN for false conditions and a visible value for true conditions
        dataframe['qfl_condition'] = np.where(qfl_buy_condition, 1.0, np.nan)
        dataframe['rsi_condition'] = np.where(rsi_buy_condition, 1.0, np.nan)
        
        # Combined buy condition
        buy_condition = qfl_buy_condition & rsi_buy_condition
        # buy_condition = rsi_buy_condition
        
        # Handle consecutive signals like Pine Script
        if not self.allow_consecutive_signals:
            # Only trigger if not triggered on previous bar OR fractal changed
            fractal_changed = dataframe['qfl_fractal_down'] != dataframe['qfl_fractal_down'].shift(1)
            buy_condition = buy_condition & (
                (~buy_condition.shift(1).fillna(False)) | 
                fractal_changed
            )
        
        # Debug logging - show individual condition counts (disabled)
        # qfl_signals = dataframe[qfl_buy_condition]
        # rsi_signals = dataframe[rsi_buy_condition]
        # combined_signals = dataframe[buy_condition]
        # 
        # print(f"\n📊 CONDITION ANALYSIS:")
        # print(f"  🟢 QFL signals found: {len(qfl_signals)}")
        # print(f"  🟠 RSI signals found: {len(rsi_signals)}")
        # print(f"  🔵 Combined signals: {len(combined_signals)}")
        # 
        # if len(qfl_signals) > 0:
        #     print(f"  Last QFL signal: {qfl_signals.index[-1]} at ${qfl_signals.iloc[-1]['close']:.2f}")
        # if len(rsi_signals) > 0:
        #     print(f"  Last RSI signal: {rsi_signals.index[-1]} at RSI {rsi_signals.iloc[-1]['rsi']:.1f}")
        # 
        # # Debug logging - show ALL combined signals that trigger
        # if len(combined_signals) > 0:
        #     print(f"\n🚨 QFL+RSI BUY SIGNALS DETECTED ({len(combined_signals)} signals):")
        #     for idx, row in combined_signals.iterrows():
        #         if self.use_atr_entry:
        #             atr_dist = row['qfl_fractal_down'] - row['close']
        #             atr_mult = atr_dist / row['atr'] if row['atr'] > 0 else 0
        #             print(f"  📅 {row.name} | 💰 Price: ${row['close']:.2f} | 📉 Fractal: ${row['qfl_fractal_down']:.2f} | 📊 ATR Dist: {atr_mult:.2f}x | 📈 RSI: {row['rsi']:.1f} | 🎯 PNR: {row['rsi_pnr']:.1f}% | 🕐 Age: {row['qfl_base_age']}")
        #         else:
        #             print(f"  📅 {row.name} | 💰 Price: ${row['close']:.2f} | 📉 Fractal: ${row['qfl_fractal_down']:.2f} | 📊 QFL%: {row['price_pct_below_fractal']:.2f}% | 📈 RSI: {row['rsi']:.1f} | 🎯 PNR: {row['rsi_pnr']:.1f}% | 🕐 Age: {row['qfl_base_age']}")
        # else:
        #     print(f"\n❌ No QFL+RSI buy signals found in this period")
        #     # Show some sample conditions for debugging
        #     recent_data = dataframe.tail(5)
        #     print(f"DEBUG: Recent conditions (last 5 rows):")
        #     for idx, row in recent_data.iterrows():
        #         if self.use_atr_entry:
        #             qfl_ok = row['close'] < row['atr_entry_threshold']
        #             atr_dist = row['qfl_fractal_down'] - row['close']
        #             atr_mult = atr_dist / row['atr'] if row['atr'] > 0 else 0
        #             print(f"  {row.name}: close=${row['close']:.2f}, ATR_OK={qfl_ok}, ATR_dist={atr_mult:.2f}x, RSI={row['rsi']:.1f}")
        #         else:
        #             qfl_ok = row['price_pct_below_fractal'] < row['buy_threshold']
        #             rsi_ok = row['rsi'] < row['rsi_entry_level'] if not pd.isna(row['rsi_entry_level']) else False
        #             rsi_entry_str = f"{row['rsi_entry_level']:.1f}" if not pd.isna(row['rsi_entry_level']) else 'N/A'
        #             print(f"  {row.name}: close=${row['close']:.2f}, QFL_OK={qfl_ok}, RSI={row['rsi']:.1f}, RSI_Entry={rsi_entry_str}, RSI_OK={rsi_ok}")
        
        dataframe.loc[buy_condition, 'enter_long'] = 1
        
        # Short entry: disabled for now (will be used later for short entries, not long exits)
        # dataframe.loc[
        #     (
        #         (100 * (dataframe['close'] / dataframe['qfl_fractal_up']) > (100 + self.sell_percentage.value)) &
        #         age_condition &
        #         (dataframe['qfl_fractal_up'].notna()) &
        #         (dataframe['volume'] > 0)
        #     ),
        #     'enter_short'
        # ] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        QFL+RSI Exit Logic
        Exit when RSI above 99% percentile
        """
        # Exit long when RSI above exit percentile level (overbought)
        rsi_exit_condition = dataframe['rsi'] > dataframe['rsi_exit_level']
        
        dataframe.loc[rsi_exit_condition, 'exit_long'] = 1
        
        # Short trading disabled for this strategy
        # dataframe.loc[False, 'exit_short'] = 1
        
        return dataframe