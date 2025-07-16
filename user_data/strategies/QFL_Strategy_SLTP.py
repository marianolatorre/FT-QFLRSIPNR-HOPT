# pragma pylint: disable=missing-docstring, invalid-name, too-few-public-methods
# pragma pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-locals

import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, merge_informative_pair
import talib.abstract as ta


class QFL_Strategy_SLTP(IStrategy):
    """
    QFL (Quickfinger Luc) Strategy Implementation with SL/TP Hyperopt
    Based on the Pine Script QFL single TF v1.3
    
    - Detects fractal highs/lows with volume confirmation
    - Uses higher timeframe for base detection
    - Enters on percentage breaks below/above bases
    - Exits purely via optimized stop loss and take profit (ROI)
    """
    
    # Strategy interface version
    strategy_version = 1
    
    # Optimal timeframe for the strategy
    timeframe = '1h'
    
    # Can this strategy go short?
    can_short = False
    
    # Static ROI table - optimized automatically by Freqtrade when using --spaces roi
    minimal_roi = {
        "0": 0.10,
        "40": 0.04,
        "100": 0.02,
        "240": 0
    }
    
    # Hyperopt-optimized stoploss
    stoploss_opt = DecimalParameter(-0.35, -0.02, default=-0.15, space='stoploss')
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # Set stoploss value
        self.stoploss = self.stoploss_opt.value
    
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
            }
        }
    }
    
    # QFL Parameters (equivalent to Pine Script inputs)
    # Make QFL timeframe configurable - options: '1h', '2h', '4h' for base detection
    qfl_timeframe = '1h'  # Higher timeframe for base detection
    # volume_ma_period = IntParameter(5, 10, default=6, space='buy')
    volume_ma_period = 6
    buy_percentage = DecimalParameter(0.5, 10.0, default=3.5, space='buy')
    #max_base_age = IntParameter(0, 50, default=0, space='buy')  # 0 = disabled
    max_base_age = 0  # 0 = disabled
    allow_consecutive_signals = True  # Pine: allowConsecutiveSignals
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators for QFL strategy
        """
        # Volume moving average
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=self.volume_ma_period)
        
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
        
        # Debug logging
        print(f"DEBUG: QFL timeframe: {self.qfl_timeframe}, Strategy timeframe: {self.timeframe}")
        print(f"DEBUG: Fractal up count: {dataframe['qfl_fractal_up'].notna().sum()}")
        print(f"DEBUG: Fractal down count: {dataframe['qfl_fractal_down'].notna().sum()}")
        if not dataframe['qfl_fractal_down'].isna().all():
            print(f"DEBUG: Latest fractal down: {dataframe['qfl_fractal_down'].iloc[-1]}")
        
        return dataframe
    
    def calculate_qfl_indicators(self, dataframe: DataFrame) -> DataFrame:
        """
        Calculate QFL fractals and bases on higher timeframe data
        Translates the Pine Script QFL logic to Python
        """
        # Volume moving average for fractal validation
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=self.volume_ma_period)
        
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
        
        # Calculate percentage below fractal
        dataframe['price_pct_below_fractal'] = 100 * (dataframe['close'] / dataframe['qfl_fractal_down'])
        dataframe['buy_threshold'] = 100 - self.buy_percentage.value
        
        # Long entry: price falls X% below down fractal (QFL "crack")
        # Pine: signal = buy and (allowConsecutiveSignals or not buy[1] or fdowntf != fdowntf[1])
        buy_condition = (
            (dataframe['price_pct_below_fractal'] < dataframe['buy_threshold']) &
            age_condition &
            (dataframe['qfl_fractal_down'].notna()) &
            (dataframe['volume'] > 0)
        )
        
        # Handle consecutive signals like Pine Script
        if not self.allow_consecutive_signals:
            # Only trigger if not triggered on previous bar OR fractal changed
            fractal_changed = dataframe['qfl_fractal_down'] != dataframe['qfl_fractal_down'].shift(1)
            buy_condition = buy_condition & (
                (~buy_condition.shift(1).fillna(False)) | 
                fractal_changed
            )
        
        # Debug logging - show ALL signals that trigger
        # signal_rows = dataframe[buy_condition]
        # if len(signal_rows) > 0:
        #     print(f"\n🚨 QFL BUY SIGNALS DETECTED ({len(signal_rows)} signals):")
        #     for idx, row in signal_rows.iterrows():
        #         print(f"  📅 {row.name} | 💰 BTC Price: ${row['close']:.2f} | 📉 Fractal Base: ${row['qfl_fractal_down']:.2f} | 📊 Below%: {row['price_pct_below_fractal']:.2f}% (threshold: {row['buy_threshold']:.2f}%) | 🕐 Age: {row['qfl_base_age']}")
        # else:
        #     print(f"\n❌ No QFL buy signals found in this period")
        #     # Show some sample conditions for debugging
        #     recent_data = dataframe.tail(5)
        #     print(f"DEBUG: Recent conditions (last 5 rows):")
        #     for idx, row in recent_data.iterrows():
        #         below_threshold = row['price_pct_below_fractal'] < row['buy_threshold']
        #         print(f"  {row.name}: close=${row['close']:.2f}, fractal=${row['qfl_fractal_down']:.2f}, below%={row['price_pct_below_fractal']:.2f}%, threshold={row['buy_threshold']:.2f}%, below_threshold={below_threshold}")
        
        dataframe.loc[buy_condition, 'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        QFL Exit Logic - DISABLED
        This strategy relies purely on stop loss and take profit (ROI) for exits
        """
        # No exit signals - pure SL/TP reliance
        return dataframe