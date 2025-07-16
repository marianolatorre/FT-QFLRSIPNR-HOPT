# Prompt for another agent: Build a robust crypto scalping strategy for Freqtrade

You’re an experienced algorithmic‑trading engineer tasked with **writing a complete, compilable Freqtrade strategy** from scratch.  The end‑user will later hyper‑optimize and walk‑forward test it on multiple cryptocurrency pairs.  Follow every requirement below.

---
## 1 .  General information
* **Strategy name**: `ScalpHybridStrategy`
* **Purpose**: High‑frequency scalp entries on both **long and short** sides.
* **Platform**: Freqtrade ≥ 2025‑07 (`INTERFACE_VERSION = 3`).  Make sure every callback signature matches the current docs.
* **File**: one Python file only, ready to drop into `user_data/strategies/`.

---
## 2 .  Timeframes
| Role | TF |
|------|----|
| Execution / signals | `5m` |
| Informative (trend gate) | `1h` |

Add `merge_informative_pair` so 1‑hour data are forward‑filled into the 5‑minute frame.

---
## 3 .  Indicator block
Implement these indicators exactly and expose the marked ones as **hyperopt parameters** using `IntParameter` or `DecimalParameter`.

| Category | Indicator | Parameter ranges |
|----------|-----------|------------------|
| **Trend** | EMA fast | 5 – 20 (default = 9) |
|          | EMA slow | 21 – 100 (default = 50) |
|          | ADX | threshold 15 – 40 (default = 20) |
| **Momentum** | RSI‑14 | buy < *buy_rsi* (10 – 35, default = 25); sell > *sell_rsi* (65 – 90, default = 75) |
|          | Stochastic slow %K / %D | fixed 14, 3, 3 |
| **Volatility** | Bollinger Bands (period 20) | `nbdev` 1.5 – 2.8 (default = 2.0) |
|          | ATR‑14 | used for optional dynamic SL |
| **Volume** | Rolling mean 20 | Boolean filter: candle volume > vol_mean × *vol_mult* (0.8 – 2.0, default = 1.0) |

---
## 4 .  Entry / exit logic
### Long entry
1. `rsi < buy_rsi`  
2. `close < bb_lower`  
3. `ema_fast > ema_slow`  
4. `adx > adx_threshold`  
5. `vol_ok`  
6. **1‑hour filter**: `ema_fast_1h > ema_slow_1h`

### Short entry
Mirror the long rules (e.g. `rsi > sell_rsi`, price above `bb_upper`, etc.) and require `ema_fast_1h < ema_slow_1h`.

### Long exit
* `rsi > sell_rsi` **OR** `close > bb_mid` **OR** fast EMA crosses below slow.

### Short exit
Opposite of long exit.

Mark the signals on the `dataframe` columns `enter_long`, `enter_short`, `exit_long`, `exit_short` as required by v3.

---
## 5 .  Risk and money management
### 5.1  Static & dynamic stop
* Default hard `stoploss = -0.035` (‑3.5 %).
* Provide an OPTIONAL dynamic ATR‑based SL in `custom_stoploss`: once trade moves > +1 %, trail at `current_rate – 1×ATR` (long) or `current_rate + 1×ATR` (short).

### 5.2  ROI ladder (hyperopt will overwrite)
```python
minimal_roi = {
    "0": 0.012,  # 1.2 %
    "10": 0.008,
    "30": 0.004,
    "60": 0
}
```

### 5.3  Trailing
```python
trailing_stop = True
trailing_stop_positive = 0.005
trailing_stop_positive_offset = 0.01
trailing_only_offset_is_reached = True
```

### 5.4  **Fixed‑risk position sizing**
Implement a _risk‑per‑trade_ system so every losing trade damages the account by **exactly the same equity fraction**.

1. Add `risk_per_trade = DecimalParameter(0.003, 0.01, default=0.005, decimals=3, space="stake")` (0.5 % default).
2. Create `custom_stake_amount` with official signature
```python
stake = equity * risk_per_trade / stop_pct
```
   *Where `stop_pct` is*:  
   * the absolute value of `stoploss` if static, **or**  
   * `atr / price` if using the dynamic ATR stop (take the larger of the two for safety).
3. Clamp between `min_stake` and `max_stake`.
4. Never hyper‑optimise `risk_per_trade`.

---
## 6 .  Parameters for hyperopt spaces
* Trend lengths & ADX threshold ➜ `space="buy"`
* RSI thresholds & BB `nbdev` ➜ appropriate buy/sell spaces
* Volume multiplier ➜ `space="buy"`
* Risk parameter ➜ `space="stake"`

Include `startup_candle_count = 200` and `process_only_new_candles = True` to avoid look‑ahead bias.

---
## 7 .  Final deliverable
Return **one Python file** with:
* Full doc‑string explaining goals & usage.
* All required imports (`talib.abstract as ta`, `merge_informative_pair`, etc.).
* No test or helper files.
* Verified that it **compiles** under `python -m freqtrade –V` 2025‑07.

---
### Acceptance checklist
- [ ] `freqtrade backtesting` runs with at least BTC/USDT on 2025‑Q1 data without error.
- [ ] All parameters appear in `freqtrade hyperopt --print`.
- [ ] `custom_stake_amount` successfully adjusts stake so historical losers always equal `equity × risk_per_trade`.
- [ ] Strategy class name matches file name.

Once implemented, we will hyper‑opt, walk‑forward, then deploy to live trading.  **Focus on correctness and compilation; optimisation will come later.**
