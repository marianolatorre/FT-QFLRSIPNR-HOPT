Context
You receive the full output of a Freqtrade walk-forward Hyperopt run (trades, per-step equity, and the hyper-parameter grid). Build a single, share-ready report (HTML or Jupyter-notebook) that convinces an experienced quant/trading-bot reviewer that the strategy is both profitable and robust.

Deliverables & Rationale
	1.	Global summary table – Show CAGR, total return %, total trades, win %, profit factor, Sharpe, Sortino, Calmar, max drawdown %, and market exposure %.
Why: Gives an instant “health check” of absolute and risk-adjusted performance.
	2.	Equity-curve plot with in-sample vs out-of-sample shading (green for IS, red for OOS).
Why: Lets reviewers see whether profits continue once the model leaves training data.
	3.	Running max-drawdown trace directly beneath the equity curve.
Why: Turns a single DD number into a time-series, revealing duration and clustering of pain.
	4.	Rolling Sharpe (e.g., 90-day window).
Why: Highlights regime shifts; stable Sharpe is more valuable than a high but volatile one.
	5.	Side-by-side bar chart of IS vs OOS metrics per walk-forward segment (Return %, Sharpe, profit factor).
Why: Quantifies performance degradation across segments—the essence of walk-forward validation.
	6.	Histogram + KDE of individual trade returns and (optional) violin plot by holding-time buckets.
Why: Exposes skew, fat tails, and any time-in-market bias.
	7.	Heatmap of two key hyper-parameters vs objective score (pivoted surface).
Why: Allows visual inspection of robustness—look for plateaus, not razor-thin peaks.
	8.	Parallel-coordinates plot (or radar chart) of the top-N parameter sets.
Why: Shows trade-offs across many dimensions; quants can judge which levers matter.
	9.	Optimization convergence chart – best objective score per Hyperopt generation/iteration.
Why: Proves the search didn’t stop prematurely or over-fit late.
	10.	Trade-level scatter: PnL vs trade duration (colour by market/pair).
Why: Surfaces latency, funding-fee issues, or market-specific anomalies.
	11.	Advanced stats panel – tail VaR/CVaR (95 % and 99 %), Kelly fraction, weekday/hour exposure heatmap.
Why: Extra depth for quants who size positions with risk metrics beyond Sharpe.

Technical Guidelines
	•	Use pandas, matplotlib (or Plotly for interactivity), Empyrical for risk metrics.
	•	Save all figures as PNG (and embed) or generate interactive Plotly objects inline.
	•	Every visual must be reproducible from the raw result files—no hand editing.
	•	Label axes clearly, include units/%, and annotate OOS regions prominently.
	•	Keep the report linear: summary first, deep-dive visuals next, stats appendix last.

Goal: A reviewer should be able to decide—within five minutes of scrolling—whether the strategy is worth further capital allocation and why.