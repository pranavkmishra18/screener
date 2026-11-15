# Global Deep-Value & Fundamental Stock Screener

🔗 **Live Dashboard:** [https://pranavkmishra18.github.io/screener/](https://pranavkmishra18.github.io/screener/)

An automated, multi-region stock screener that scans ~500 large-cap companies across the **US, Europe, and India** (`yfinance`) to identify fundamentally strong businesses trading at significant discounts. Powered by **GitHub Actions** (auto-refreshing every 30 minutes) and hosted on **GitHub Pages**.

---

## How It Works

1. **Drawdown Filter (`FALL`):** Measures each stock's drop from its rolling 5-year monthly high (`--fall 25` by default) to avoid 20-year-old dot-com bubble distortions.
2. **18-Point Fundamental Quality Score (`SCORE`):** Evaluates valuation, profitability, earnings trajectory, cash conversion, and balance sheet health.
3. **Multi-Pillar Upside Triangulation (`BASIS` & `UPSIDE`):**
   * **`A` (Analyst Target):** Upside to average Wall Street consensus target price.
   * **`E` (Fair P/E Multiple):** Upside to a sector-, region-, and ROE-adjusted baseline P/E multiple.
   * **`F` (Free Cash Flow Yield):** Upside relative to a 5.0% Free Cash Flow yield benchmark.
   * **`R` (Recovery Fallback):** Conservative partial recovery model when analyst/cash-flow data is unavailable.
4. **Recovery Horizon (`MOS`):** Estimates months (`4m`–`36m`) to realize projected upside using 5-year annualized volatility, forward earnings acceleration (`FP/E` vs `P/E`), and 52-week momentum.
5. **Drop Catalyst Diagnosis (`WHY DOWN`):** Combines financial statement forensics with live Yahoo Finance news headlines to summarize why the stock is down in 3–4 words.

---

## The 18 Fundamental Checks

| Flag | Metric | Passing Condition |
| :--- | :--- | :--- |
| **`PE`** | Trailing P/E | `0 < PE <= 1.35x Sector Fair P/E` |
| **`FPE`** | Forward P/E | `0 < FP/E <= 1.15x Fair P/E` and not spiking above Trailing P/E |
| **`PEG`** | PEG Ratio | `0 < PEG <= 2.0` |
| **`EVE`** | EV / EBITDA | `0 < EV/EBITDA < 14` |
| **`PB`** | Price-to-Book | `< 2.0` (Financials) or scaled by ROE for asset-light compounders |
| **`FCF`** | Free Cash Flow Yield | `> 4.5%` |
| **`ROE`** | Return on Equity | `> 12%` |
| **`ROA`** | Return on Assets | `> 1.0%` (Financials) or `> 5.0%` (Non-Financials) |
| **`OMR`** | Operating Margin | `> 10%` |
| **`MRG`** | Gross Margin Trend | `> -2%` (5-year newest vs. oldest) |
| **`REV`** | Revenue Stability | Latest annual revenue `>= 90%` of 5-year peak |
| **`GRW`** | Profit Stability | Profitable and latest net income `>= 70%` of 5-year peak |
| **`CSH`** | Cash Conversion | Operating Cash Flow `>= 90%` of Net Income |
| **`CR`** | Current Ratio | `> 1.0` |
| **`DBT`** | Debt-to-Equity | `< 180%` |
| **`NDE`** | Net Debt / EBITDA | `< 3.0x` |
| **`ICV`** | Interest Coverage | `EBIT / Interest Expense > 4.0x` |
| **`SHR`** | Share Dilution | Compound annual share count growth `<= 2.0%` |

---

## Local CLI Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run full screen across US, Europe, and India
python screener.py

# Export dashboard data to data.json
python screener.py --json data.json --fresh --workers 10

# Custom filters (e.g., India only, min 30% drop, max 12 months recovery)
python screener.py --region in --fall 30 --max-months 12
