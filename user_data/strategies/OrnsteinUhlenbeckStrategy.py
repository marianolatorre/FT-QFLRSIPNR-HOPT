# pragma pylint: disable=missing-docstring, invalid-name, too-few-public-methods
# pragma pylint: disable=too-many-instance-attributes, too-many-arguments, too-many-locals

import pandas as pd
import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter

class OrnsteinUhlenbeckStrategy(IStrategy):
    """
    Ornstein-Uhlenbeck Mean Reversion Strategy (Long Only)
    """
    
    # Strategy interface version
    strategy_version = 1
    
    # Optimal timeframe for the strategy
    timeframe = '15m'
    
    # This strategy is long-only
    can_short = False
    
    # Minimal ROI table
    minimal_roi = {
        "0": 0.1,
        "60": 0.05,
        "120": 0.01
    }
    
    # Stoploss
    stoploss = -0.10
    
    # Trailing stoploss
    trailing_stop = False
    
    # Startup candle count
    startup_candle_count: int = 300
    
    # Hyperopt parameters
    lookback_period = IntParameter(20, 400, default=100, space='buy')
    entry_threshold = DecimalParameter(1.0, 4.0, default=2.0, space='buy', decimals=1)
    exit_threshold = DecimalParameter(0.0, 2.0, default=0.5, space='buy', decimals=1)
    half_life_period = IntParameter(5, 200, default=21, space='buy')

    # Plot configuration for web UI
    plot_config = {
        'main_plot': {
            'ou_upper_band': {'color': '#ff0000', 'type': 'line'},
            'ou_lower_band': {'color': '#00ff00', 'type': 'line'},
        },
        'subplots': {
            'OU Mean': {
                'ou_mean': {'color': '#0000ff', 'type': 'line'},
            },
            'Z-Score': {
                'z_score': {'color': '#00ff00', 'type': 'line'},
            },
        }
    }

    def estimate_ou_parameters(self, log_prices: pd.Series, lookback: int):
        """
        Estimate Ornstein-Uhlenbeck parameters (θ, μ, σ) using a rolling window.
        """
        # This calculation is iterative and can be slow; consider vectorizing for performance
        ou_params = []
        for i in range(lookback, len(log_prices)):
            window = log_prices[i-lookback:i]
            if len(window) < 2:
                ou_params.append((np.nan, np.nan, np.nan))
                continue
            
            delta_t = 1
            mu = window.mean()
            
            try:
                autocorr = window.autocorr(lag=1)
                theta = -np.log(autocorr) / delta_t if autocorr > 0 else np.nan
            except Exception:
                theta = np.nan

            sigma = window.std() * np.sqrt(2 * theta / delta_t) if pd.notna(theta) and theta > 0 else np.nan
            ou_params.append((theta, mu, sigma))
        
        return pd.DataFrame(ou_params, columns=['theta', 'mu', 'sigma'], index=log_prices.index[lookback:])

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Populate indicators for the Ornstein-Uhlenbeck strategy.
        """
        log_prices = np.log(dataframe['close'])
        ou_params_df = self.estimate_ou_parameters(log_prices, self.lookback_period.value)
        
        dataframe['ou_theta'] = ou_params_df['theta']
        dataframe['ou_mean'] = ou_params_df['mu']
        dataframe['ou_sigma'] = ou_params_df['sigma']
        dataframe['z_score'] = (log_prices - dataframe['ou_mean']) / dataframe['ou_sigma']
        
        dataframe['ou_upper_band'] = np.exp(dataframe['ou_mean'] + self.entry_threshold.value * dataframe['ou_sigma'])
        dataframe['ou_lower_band'] = np.exp(dataframe['ou_mean'] - self.entry_threshold.value * dataframe['ou_sigma'])
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry logic for the Ornstein-Uhlenbeck strategy.
        """
        long_condition = (
            (dataframe['z_score'] < -self.entry_threshold.value) &
            (dataframe['volume'] > 0)
        )
        dataframe.loc[long_condition, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit logic for the Ornstein-Uhlenbeck strategy.
        """
        long_exit_condition = (
            (dataframe['z_score'] >= -self.exit_threshold.value)
        )
        dataframe.loc[long_exit_condition, 'exit_long'] = 1
        return dataframe