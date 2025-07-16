"""
ScalpHybridStrategy — Freqtrade IStrategy template for crypto scalping (long & short)
===================================================================================

Goals
-----
* **Scalping-oriented**: targets quick in/out moves on low-timeframe charts (default 5 m).
* **Robust & portable**: relies on a balanced mix of momentum, volatility, trend and volume filters that
  historically generalise well across large-cap and mid-cap cryptocurrencies.
* **Hyperopt-ready**: all key thresholds are declared as `*Parameter` objects so you can optimise with
  `freqtrade hyperopt` (GA/Random) and later validate with walk-forward analysis.

Core indicator blocks
---------------------
* **Trend**    – Fast/slow EMA crossover (adaptive length); ADX trend-strength; Higher-timeframe EMA filter.
* **Momentum** – RSI-14; Stochastic %K/%D; MFI-14 (optional).
* **Volatility** – Bollinger Bands (20-period, hyperopt-able devs); ATR-14 for dynamic SL sizing.
* **Volume**   – 20-period rolling mean to avoid illiquid candles.

Risk management
---------------
* **Static initial SL** expressed as % OR `n × ATR` (whichever is tighter).
* **Trailing** enabled once price moves `offset` into profit.
* **Layered ROI** table giving the hyperopt engine something to chew on.

Timeframes
----------
* **`timeframe`**:      5 m  (execution)
* **`informative_tf`**: 1 h  (macro trend filter)

Usage
-----
1. Copy this file into your `user_data/strategies` directory.
2. Run a coarse hyperopt (e.g. 250-500 generations) on 3–6 months of diverse pairs.
3. Walk-forward test the best candidates on unseen data.
4. Always paper-trade before going live.

© 2025 Mariano / ChatGPT — MIT-style licence. Use at your own risk.
"""

from functools import reduce
from typing import Dict, List

import numpy as np
import pandas as pd
from pandas import DataFrame

import talib.abstract as ta
from freqtrade.strategy import (
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
    merge_informative_pair,
)


class ScalpHybridStrategy(IStrategy):
    """Freqtrade strategy that supports both long and short scalping."""

    # --- Interface version ---
    INTERFACE_VERSION: int = 3  # Freqtrade ≥2024.x

    # --- Strategy timeframe configuration ---
    timeframe: str = "5m"
    informative_tf: str = "1h"

    process_only_new_candles: bool = True
    startup_candle_count: int = 200  # makes sure we have enough history for all indicators

    # --- Hyperoptable indicator lengths / thresholds ---
    # Trend
    ema_fast_period = IntParameter(5, 20, default=9, space="buy")
    ema_slow_period = IntParameter(21, 100, default=50, space="buy")
    adx_threshold = IntParameter(15, 40, default=20, space="buy")

    # Momentum
    buy_rsi = IntParameter(10, 35, default=25, space="buy")
    sell_rsi = IntParameter(65, 90, default=75, space="sell")

    # Volatility
    bb_mult = DecimalParameter(1.5, 2.8, default=2.0, decimals=2, space="buy")

    # Volume filter (min multiple of rolling mean)
    vol_mult = DecimalParameter(0.8, 2.0, default=1.0, decimals=2, space="buy")
    
    # Risk per trade (for position sizing)
    risk_per_trade = DecimalParameter(0.003, 0.01, default=0.005, decimals=3, space="stake")

    # --- ROI table (will often be overridden by hyperopt) ---
    minimal_roi: Dict[str, float] = {
        "0": 0.012,   # 1.2 %
        "10": 0.008,  # after 10 m cut to 0.8 %
        "30": 0.004,  # after 30 m cut to 0.4 %
        "60": 0       # after 60 m accept market exit
    }

    # --- Stoploss & trailing ---
    stoploss: float = -0.035  # 3.5 % initial hard SL (tight for scalping)

    trailing_stop: bool = True
    trailing_stop_positive: float = 0.005   # arm at +0.5 %
    trailing_stop_positive_offset: float = 0.01  # offset 1 % so trigger @ +1 %
    trailing_only_offset_is_reached: bool = True

    # --- Order types ---
    use_exit_signal: bool = True
    exit_profit_only: bool = False
    ignore_roi_if_entry_signal: bool = False

    order_types: Dict[str, str] = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # ============================
    # Indicator calculation
    # ============================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # type: ignore[override]
        # --- Base timeframe (5 m) ---
        ema_fast_len = int(self.ema_fast_period.value)
        ema_slow_len = int(self.ema_slow_period.value)

        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=ema_fast_len)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=ema_slow_len)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["mfi"] = ta.MFI(dataframe)

        slowk, slowd = ta.STOCH(dataframe)
        dataframe["stoch_k"], dataframe["stoch_d"] = slowk, slowd

        # Bollinger Bands using hyperopt-able multiplier
        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=self.bb_mult.value, nbdevdn=self.bb_mult.value, matype=0)
        dataframe["bb_lower"] = bb['lowerband']
        dataframe["bb_mid"] = bb['middleband']
        dataframe["bb_upper"] = bb['upperband']
        dataframe["bb_width"] = (bb['upperband'] - bb['lowerband']) / bb['middleband']

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe)

        # Volume filter
        dataframe["vol_mean"] = dataframe["volume"].rolling(20).mean()
        dataframe["vol_ok"] = dataframe["volume"] > dataframe["vol_mean"] * self.vol_mult.value

        # --- Higher TF (1 h) ---
        informative = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=self.informative_tf)
        informative["ema_fast"] = ta.EMA(informative, timeperiod=ema_fast_len)
        informative["ema_slow"] = ta.EMA(informative, timeperiod=ema_slow_len)
        informative["trend_ok"] = informative["ema_fast"] > informative["ema_slow"]

        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, self.informative_tf, ffill=True)

        # Add plotting reference lines and condition indicators
        dataframe['buy_rsi_line'] = self.buy_rsi.value
        dataframe['sell_rsi_line'] = self.sell_rsi.value
        dataframe['adx_threshold_line'] = self.adx_threshold.value
        
        # Add individual condition checks for visual debugging (handle NaN values)
        dataframe['cond1_rsi'] = (dataframe['rsi'] < self.buy_rsi.value).fillna(False).astype(int)
        dataframe['cond2_bb'] = (dataframe['close'] < dataframe['bb_lower']).fillna(False).astype(int)
        dataframe['cond3_ema'] = (dataframe['ema_fast'] > dataframe['ema_slow']).fillna(False).astype(int)
        dataframe['cond4_adx'] = (dataframe['adx'] > self.adx_threshold.value).fillna(False).astype(int)
        dataframe['cond5_vol'] = dataframe['vol_ok'].fillna(False).astype(int)
        dataframe['cond6_trend'] = dataframe['trend_ok_1h'].fillna(False).astype(int)
        
        # Count how many conditions are met
        dataframe['conditions_met'] = (
            dataframe['cond1_rsi'] + 
            dataframe['cond2_bb'] + 
            dataframe['cond3_ema'] + 
            dataframe['cond4_adx'] + 
            dataframe['cond5_vol'] + 
            dataframe['cond6_trend']
        )

        return dataframe

    # ============================
    # Entry logic — LONG
    # ============================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # type: ignore[override]
        conditions: List[pd.Series] = []

        conditions.append(dataframe["rsi"] < self.buy_rsi.value)
        conditions.append(dataframe["close"] < dataframe["bb_lower"])
        conditions.append(dataframe["ema_fast"] > dataframe["ema_slow"])
        conditions.append(dataframe["adx"] > self.adx_threshold.value)
        conditions.append(dataframe["vol_ok"])
        conditions.append(dataframe["trend_ok_1h"])

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "enter_long"] = 1
        return dataframe

    # ============================
    # Entry logic — SHORT
    # ============================
    def populate_entry_short_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # type: ignore[override]
        conditions: List[pd.Series] = []

        conditions.append(dataframe["rsi"] > self.sell_rsi.value)
        conditions.append(dataframe["close"] > dataframe["bb_upper"])
        conditions.append(dataframe["ema_fast"] < dataframe["ema_slow"])
        conditions.append(dataframe["adx"] > self.adx_threshold.value)
        conditions.append(dataframe["vol_ok"])
        conditions.append(~dataframe["trend_ok_1h"])

        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "enter_short"] = 1
        return dataframe

    # ============================
    # Exit logic — LONG
    # ============================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # type: ignore[override]
        conditions: List[pd.Series] = []

        conditions.append(dataframe["rsi"] > self.sell_rsi.value)
        conditions.append(dataframe["close"] > dataframe["bb_mid"])
        conditions.append(dataframe["ema_fast"] < dataframe["ema_slow"])  # fast momentum stall

        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), "exit_long"] = 1
        return dataframe

    # ============================
    # Exit logic — SHORT
    # ============================
    def populate_exit_short_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # type: ignore[override]
        conditions: List[pd.Series] = []

        conditions.append(dataframe["rsi"] < self.buy_rsi.value)
        conditions.append(dataframe["close"] < dataframe["bb_mid"])
        conditions.append(dataframe["ema_fast"] > dataframe["ema_slow"])  # trend flip

        if conditions:
            dataframe.loc[reduce(lambda x, y: x | y, conditions), "exit_short"] = 1
        return dataframe

    # ============================
    # Custom stake amount — risk-per-trade position sizing
    # ============================
    def custom_stake_amount(self, pair: str, current_time, current_rate, proposed_stake, min_stake, max_stake, **kwargs):
        """Calculate position size based on risk per trade."""
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if dataframe is None or len(dataframe) < 1:
                return proposed_stake
                
            last_atr = dataframe.iloc[-1]["atr"]
            
            # Calculate stop percentage
            static_stop_pct = abs(self.stoploss)
            atr_stop_pct = last_atr / current_rate if current_rate > 0 else static_stop_pct
            
            # Use the larger of the two stops for safety
            stop_pct = max(static_stop_pct, atr_stop_pct)
            
            # Calculate stake based on risk per trade
            if stop_pct > 0:
                stake = (self.wallets.get_total_stake_amount() * self.risk_per_trade.value) / stop_pct
            else:
                stake = proposed_stake
                
            # Clamp between min and max stake
            stake = max(min_stake, min(stake, max_stake))
            
            return stake
            
        except Exception:
            return proposed_stake

    # ============================
    # Custom stoploss (optional) — tighten to ATR after breakeven
    # ============================
    def custom_stoploss(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs):  # noqa: N802,E501
        """Tighter dynamic SL: once in profit, follow price at 1 × ATR below/above close."""
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if dataframe is None or len(dataframe) < 1:
                return self.stoploss

            last_atr = dataframe.iloc[-1]["atr"]
            if current_profit > 0.01:
                # Long trades: raise SL; Short trades: lower SL
                if trade.is_short:
                    # For short trades, stop above current rate
                    new_stop = (current_rate + last_atr - trade.open_rate) / trade.open_rate
                    return max(self.stoploss, new_stop)
                else:
                    # For long trades, stop below current rate
                    new_stop = (current_rate - last_atr - trade.open_rate) / trade.open_rate
                    return max(self.stoploss, new_stop)
            return self.stoploss
        except Exception:
            return self.stoploss

    def plot_config(self):
        """
        Plot configuration for the web UI to visualize all indicators
        """
        return {
            'main_plot': {
                'tema': {},
                'ema_fast': {'color': 'blue'},
                'ema_slow': {'color': 'red'},
                'bb_lower': {'color': 'green'},
                'bb_mid': {'color': 'orange'},
                'bb_upper': {'color': 'green'},
            },
            'subplots': {
                'RSI': {
                    'rsi': {'color': 'blue'},
                    'buy_rsi_line': {'color': 'green', 'type': 'line'},
                    'sell_rsi_line': {'color': 'red', 'type': 'line'},
                },
                'ADX': {
                    'adx': {'color': 'purple'},
                    'adx_threshold_line': {'color': 'red', 'type': 'line'},
                },
                'Stochastic': {
                    'stoch_k': {'color': 'blue'},
                    'stoch_d': {'color': 'red'},
                },
                'Volume': {
                    'volume': {'color': 'lightblue'},
                    'vol_mean': {'color': 'orange'},
                },
                'ATR': {
                    'atr': {'color': 'darkgreen'},
                },
                'Trend_1h': {
                    'trend_ok_1h': {'color': 'purple', 'type': 'line'},
                },
                'Conditions': {
                    'cond1_rsi': {'color': 'red', 'type': 'line'},
                    'cond2_bb': {'color': 'green', 'type': 'line'},
                    'cond3_ema': {'color': 'blue', 'type': 'line'},
                    'cond4_adx': {'color': 'purple', 'type': 'line'},
                    'cond5_vol': {'color': 'orange', 'type': 'line'},
                    'cond6_trend': {'color': 'pink', 'type': 'line'},
                    'conditions_met': {'color': 'black'},
                }
            }
        }
