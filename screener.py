import argparse
import contextlib
import io
import json
import logging
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

for _noisy in ("yfinance", "urllib3", "peewee"):
    logging.getLogger(_noisy).setLevel(logging.CRITICAL)

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screen_cache.json")
CACHE_HOURS, CACHE_VERSION, DEFAULT_FAIR_PE = 12, 6, 16.0

SECTOR_FAIR_PE = {
    "Technology": 22.0,
    "Communication Services": 19.0,
    "Healthcare": 18.5,
    "Consumer Defensive": 19.5,
    "Consumer Cyclical": 16.5,
    "Industrials": 16.5,
    "Basic Materials": 13.5,
    "Energy": 11.5,
    "Financial Services": 12.0,
    "Real Estate": 15.0,
    "Utilities": 14.5,
}

INDEXES = {
    "US": [("S&P 500", "%5EGSPC"), ("Dow Jones", "%5EDJI"), ("Nasdaq Comp", "%5EIXIC")],
    "EUROPE": [("Euro Stoxx 50", "%5ESTOXX50E"), ("FTSE 100", "%5EFTSE")],
    "INDIA": [("Nifty 50", "%5ENSEI"), ("Sensex", "%5EBSESN")],
}

UNIVERSE = {"US": """
AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO ORCL CRM ADBE AMD INTC QCOM TXN MU
AMAT LRCX PANW NOW SNOW ZM DOCU SHOP PYPL TWLO OKTA DDOG NET CRWD MDB TEAM
WDAY ADSK INTU IBM CSCO ACN DELL HPQ WDC STX ON MCHP SWKS QRVO TER KLAC ANET
ZS ROKU PINS SNAP SPOT TTWO RBLX U MTCH BMBL ETSY JNJ PFE MRK ABBV LLY BMY
AMGN GILD CVS UNH MRNA BNTX BIIB REGN VRTX ZTS BDX SYK MDT ISRG JPM BAC WFC
GS MS C SCHW BLK AXP V MA BRK-B PGR TRV ALL MET PRU AFL USB PNC XOM CVX COP
SLB HAL OXY PSX VLO MPC KMI WMT COST TGT HD LOW NKE SBUX MCD YUM CMG KO PEP
PG CL KMB GIS HSY MDLZ STZ EL DIS NFLX CMCSA T VZ TMUS WBD PARA LUMN EXPE BA
CAT DE GE HON LMT RTX NOC UPS FDX F GM RIVN LCID UBER LYFT ABNB DAL UAL CCL
NCLH RCL MGM LVS WYNN MAR HLT BKNG DG W
""", "EUROPE": """
SHEL.L AZN.L HSBA.L ULVR.L BP.L RIO.L GSK.L DGE.L GLEN.L BATS.L LSEG.L REL.L
NG.L BARC.L LLOY.L NWG.L PRU.L AAL.L TSCO.L VOD.L BT-A.L IMB.L CPG.L SSE.L
RR.L BA.L AHT.L IHG.L WPP.L SGRO.L ITV.L JD.L MKS.L SBRY.L KGF.L SMT.L ABF.L
BNZL.L CRDA.L HLMA.L MC.PA OR.PA TTE.PA SAN.PA AIR.PA SU.PA BNP.PA AI.PA
EL.PA CS.PA DG.PA KER.PA RMS.PA SGO.PA VIE.PA STLAP.PA ACA.PA ENGI.PA CAP.PA
PUB.PA ML.PA RNO.PA GLE.PA ORA.PA ASML.AS INGA.AS AD.AS PHIA.AS HEIA.AS
DSFIR.AS AKZA.AS WKL.AS RAND.AS KPN.AS NN.AS ASRNL.AS ABN.AS IMCD.AS SAP.DE
SIE.DE ALV.DE DTE.DE MBG.DE BMW.DE BAS.DE BAYN.DE MUV2.DE DBK.DE VOW3.DE
RWE.DE ADS.DE IFX.DE HEN3.DE FRE.DE ISP.MI ENEL.MI ENI.MI UCG.MI STLAM.MI
G.MI TRN.MI PST.MI SAN.MC IBE.MC ITX.MC BBVA.MC TEF.MC REP.MC AENA.MC
NESN.SW ROG.SW NOVN.SW UBSG.SW ZURN.SW ABBN.SW CFR.SW EQNR.OL DNB.OL NHY.OL
TEL.OL MOWI.OL ERIC-B.ST VOLV-B.ST ATCO-A.ST SEB-A.ST HM-B.ST SAND.ST
INVE-B.ST ASSA-B.ST SWED-A.ST TELIA.ST NOVO-B.CO MAERSK-B.CO DSV.CO CARL-B.CO
ORSTED.CO NOKIA.HE SAMPO.HE FORTUM.HE UPM.HE NESTE.HE ABI.BR KBC.BR UCB.BR
SOLB.BR GBLB.BR EDP.LS GALP.LS JMT.LS
""", "INDIA": """
RELIANCE.NS TCS.NS HDFCBANK.NS ICICIBANK.NS INFY.NS HINDUNILVR.NS ITC.NS
SBIN.NS BHARTIARTL.NS KOTAKBANK.NS LT.NS AXISBANK.NS BAJFINANCE.NS
ASIANPAINT.NS MARUTI.NS HCLTECH.NS SUNPHARMA.NS TITAN.NS ULTRACEMCO.NS
WIPRO.NS NESTLEIND.NS ONGC.NS NTPC.NS POWERGRID.NS TATAMOTORS.NS TATASTEEL.NS
JSWSTEEL.NS COALINDIA.NS GRASIM.NS ADANIENT.NS ADANIPORTS.NS HINDALCO.NS
CIPLA.NS DRREDDY.NS DIVISLAB.NS BRITANNIA.NS EICHERMOT.NS HEROMOTOCO.NS
BAJAJ-AUTO.NS M&M.NS TECHM.NS INDUSINDBK.NS SBILIFE.NS HDFCLIFE.NS
BAJAJFINSV.NS SHRIRAMFIN.NS APOLLOHOSP.NS TATACONSUM.NS BPCL.NS IOC.NS
GAIL.NS VEDL.NS DMART.NS PIDILITIND.NS DABUR.NS GODREJCP.NS MARICO.NS
COLPAL.NS BERGEPAINT.NS HAVELLS.NS SIEMENS.NS ABB.NS BOSCHLTD.NS LUPIN.NS
AUROPHARMA.NS TORNTPHARM.NS ALKEM.NS BIOCON.NS ZYDUSLIFE.NS MPHASIS.NS
LTIM.NS PERSISTENT.NS COFORGE.NS OFSS.NS NAUKRI.NS ZOMATO.NS PAYTM.NS
NYKAA.NS POLICYBZR.NS IRCTC.NS BANKBARODA.NS PNB.NS CANBK.NS UNIONBANK.NS
IDFCFIRSTB.NS FEDERALBNK.NS AUBANK.NS CHOLAFIN.NS MUTHOOTFIN.NS LICHSGFIN.NS
AMBUJACEM.NS SHREECEM.NS ACC.NS DALBHARAT.NS JKCEMENT.NS TVSMOTOR.NS
ASHOKLEY.NS BALKRISIND.NS MRF.NS APOLLOTYRE.NS PIIND.NS SRF.NS UPL.NS
TATACHEM.NS DEEPAKNTR.NS TRENT.NS PAGEIND.NS JUBLFOOD.NS INDHOTEL.NS VBL.NS
"""}
UNIVERSE = {k: v.split() for k, v in UNIVERSE.items()}

CHECKS = [
    ("PE",  lambda m: m["pe"],              lambda v, m: 0 < v <= m["fair_pe"] * 1.35),
    ("FPE", lambda m: m["fpe"],             lambda v, m: 0 < v <= m["fair_pe"] * 1.15 and (m["pe"] is None or v <= m["pe"] * 1.08)),
    ("PEG", lambda m: m["peg"],             lambda v, m: 0 < v <= 2.0),
    ("EVE", lambda m: m["ev_ebitda"],       lambda v, m: 0 < v < 14),
    ("PB",  lambda m: m["pb"],              lambda v, m: 0 < v < (2.0 if m["is_fin"] else max(4.0, (m["roe"] or 0.15) * 25))),
    ("FCF", lambda m: m["fcf_yield"],       lambda v, m: v > 4.5),
    ("ROE", lambda m: m["roe"],             lambda v, m: v > 0.12),
    ("ROA", lambda m: m["roa"],             lambda v, m: v > (0.010 if m["is_fin"] else 0.05)),
    ("OMR", lambda m: m["op_margin"],       lambda v, m: v > 0.10),
    ("MRG", lambda m: m["margin_trend"],    lambda v, m: v > -0.02),
    ("REV", lambda m: m["rev_ratio"],       lambda v, m: v >= 0.90),
    ("GRW", lambda m: m["profit_ratio"],    lambda v, m: v >= 0.70 and m["profitable"]),
    ("CSH", lambda m: m["cash_quality"],    lambda v, m: v >= 0.90),
    ("CR",  lambda m: m["cr"],              lambda v, m: v > 1.0),
    ("DBT", lambda m: m["de"],              lambda v, m: v < 180),
    ("NDE", lambda m: m["net_debt_ebitda"], lambda v, m: v < 3.0),
    ("ICV", lambda m: m["interest_cover"],  lambda v, m: v > 4.0),
    ("SHR", lambda m: m["share_growth"],    lambda v, m: v <= 2.0),
]

NEWS_KEYWORDS = [
    (("guidance", "outlook", "forecast", "cut", "slash", "warn"), "Guidance Cut Reset"),
    (("tariff", "trade", "export", "customs", "sanction"), "Tariff & Trade Risk"),
    (("lawsuit", "litigation", "probe", "sec", "doj", "regulator", "fine", "antitrust"), "Regulatory Headwinds"),
    (("trial", "fda", "clinical", "patent", "drug", "approval"), "Pipeline / Patent Risk"),
    (("downgrade", "target", "underperform", "sell"), "Analyst Rating Reset"),
    (("china", "asia", "weak demand", "slowdown", "consumer"), "Macro Demand Slowdown"),
    (("supply", "inventory", "delay", "shortage", "recall"), "Supply / Ops Hitch"),
    (("rate", "yield", "fed", "inflation", "credit"), "Rate & Macro Pressure"),
    (("ceo", "cfo", "resign", "executive", "restructur", "layoff"), "Mgmt / Restructuring"),
]


@contextlib.contextmanager
def quiet():
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        yield


def region_of(symbol):
    if symbol.endswith((".NS", ".BO")):
        return "INDIA"
    return "EUROPE" if "." in symbol else "US"


def cell(value, spec, scale=1.0, suffix=""):
    return "-" if value is None else format(value * scale, spec) + suffix


def basis_strength(basis):
    if not basis or basis == "-":
        return -1
    if basis == "R":
        return 0
    return basis.count("+") + 1


def fetch_and_show_indexes():
    index_data = {}
    print()
    for region, entries in INDEXES.items():
        index_data[region] = []
        print(f"  {region} INDEXES")
        print("-" * 126)
        for name, symbol in entries:
            try:
                url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
                       f"{symbol}?interval=1d&range=5d")
                meta = requests.get(
                    url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
                ).json()["chart"]["result"][0]["meta"]
                now, prev = meta["regularMarketPrice"], meta["chartPreviousClose"]
                chg = now - prev
                pct = (chg / prev * 100) if prev else 0.0
                print(f"  {name:<15} {now:>11,.2f}   {chg:+,.2f} ({pct:+.2f}%)")
                index_data[region].append({
                    "name": name,
                    "price": round(now, 2),
                    "change": round(chg, 2),
                    "pct_change": round(pct, 2),
                })
            except Exception:
                print(f"  {name:<15} unavailable")
                index_data[region].append({
                    "name": name,
                    "price": None,
                    "change": None,
                    "pct_change": None,
                })
        print()
    return index_data


def get_universe(args):
    regions = (["US", "EUROPE", "INDIA"] if args.region == "both"
               else [{"us": "US", "eu": "EUROPE", "in": "INDIA"}[args.region]])
    symbols = sorted({s for r in regions for s in UNIVERSE[r]})
    return symbols[:args.limit] if args.limit else symbols


def series(frame, label):
    try:
        if frame is None or frame.empty or label not in frame.index:
            return []
        cols = sorted(list(frame.columns))
        return [
            float(frame.loc[label, c]) for c in cols
            if frame.loc[label, c] == frame.loc[label, c]
            and frame.loc[label, c] is not None
        ]
    except Exception:
        return []


def extract_news_titles(ticker):
    titles = []
    try:
        for item in (ticker.news or [])[:6]:
            if isinstance(item, dict):
                t = item.get("title") or (item.get("content") or {}).get("title")
                if t:
                    titles.append(str(t))
    except Exception:
        pass
    return titles


def pull_company(symbol, period="5y"):
    import yfinance as yf

    with quiet():
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        history = ticker.history(period=period, interval="1mo", auto_adjust=False)
        frames = {}
        for key, getter in (
            ("income", "income_stmt"),
            ("cash", "cashflow"),
            ("balance", "balance_sheet"),
        ):
            try:
                frames[key] = getattr(ticker, getter)
            except Exception:
                frames[key] = None
        news_titles = extract_news_titles(ticker)

    if history is None or history.empty:
        return None
    closes = [float(x) for x in history["Close"].dropna().tolist()]
    if not closes:
        return None

    ccy = info.get("currency") or ""
    fin_ccy = info.get("financialCurrency") or ccy
    raw_price = info.get("currentPrice") or closes[-1]
    raw_ath = max(closes)
    raw_low52 = info.get("fiftyTwoWeekLow") or min(closes[-12:])

    price_scale = 0.01 if ccy == "GBp" else 1.0
    price = raw_price * price_scale
    ath = raw_ath * price_scale
    low52 = raw_low52 * price_scale if raw_low52 else price
    norm_ccy = "GBP" if ccy == "GBp" else ccy

    recent_closes = closes[-60:]
    returns = [
        (recent_closes[i] - recent_closes[i - 1]) / recent_closes[i - 1]
        for i in range(1, len(recent_closes)) if recent_closes[i - 1] > 0
    ]
    if len(returns) >= 6:
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        ann_vol = math.sqrt(var_r) * math.sqrt(12)
    else:
        ann_vol = 0.28

    row = {
        "symbol": symbol,
        "region": region_of(symbol),
        "name": info.get("shortName") or symbol,
        "sector": info.get("sector") or "Unknown",
        "currency": norm_ccy,
        "fin_currency": fin_ccy,
        "price": price,
        "ath": ath,
        "low52": low52,
        "ann_vol": ann_vol,
        "news": news_titles,
    }

    for key, field in (
        ("pe", "trailingPE"),
        ("fpe", "forwardPE"),
        ("peg", "pegRatio"),
        ("pb", "priceToBook"),
        ("eps", "trailingEps"),
        ("f_eps", "forwardEps"),
        ("target", "targetMeanPrice"),
        ("analysts", "numberOfAnalystOpinions"),
        ("cr", "currentRatio"),
        ("de", "debtToEquity"),
        ("roe", "returnOnEquity"),
        ("roa", "returnOnAssets"),
        ("op_margin", "operatingMargins"),
        ("rev_growth", "revenueGrowth"),
        ("earn_growth", "earningsGrowth"),
        ("ev_ebitda", "enterpriseToEbitda"),
        ("fcf", "freeCashflow"),
        ("mcap", "marketCap"),
        ("debt", "totalDebt"),
        ("cash_bal", "totalCash"),
        ("ebitda", "ebitda"),
    ):
        val = info.get(field)
        if key == "target" and val is not None:
            val = val * price_scale
        row[key] = val

    for key, frame, label in (
        ("revenues", "income", "Total Revenue"),
        ("profits", "income", "Net Income"),
        ("gross", "income", "Gross Profit"),
        ("ebit", "income", "EBIT"),
        ("interest", "income", "Interest Expense"),
        ("ocf", "cash", "Operating Cash Flow"),
        ("shares", "balance", "Ordinary Shares Number"),
        ("goodwill", "balance", "Goodwill"),
        ("assets", "balance", "Total Assets"),
    ):
        row[key] = series(frames[frame], label)
    return row


def metrics(d):
    revenues, profits = d.get("revenues") or [], d.get("profits") or []
    gross, ebit = d.get("gross") or [], d.get("ebit") or []
    interest, ocf = d.get("interest") or [], d.get("ocf") or []
    shares, goodwill = d.get("shares") or [], d.get("goodwill") or []
    assets = d.get("assets") or []
    fcf, mcap, ebitda = d.get("fcf"), d.get("mcap"), d.get("ebitda")
    sector = d.get("sector") or "Unknown"
    region = d.get("region") or "US"

    m = {
        k: d.get(k) for k in (
            "pe", "fpe", "peg", "pb", "cr", "de", "roe", "roa",
            "op_margin", "rev_growth", "earn_growth", "ev_ebitda",
        )
    }
    m["is_fin"] = sector == "Financial Services"

    base_pe = SECTOR_FAIR_PE.get(sector, DEFAULT_FAIR_PE)
    region_mult = 1.25 if region == "INDIA" else 1.0
    roe_mult = 1.15 if (m["roe"] and m["roe"] > 0.22) else 1.0
    m["fair_pe"] = base_pe * region_mult * roe_mult

    m["profitable"] = (
        (bool(profits) and profits[-1] > 0)
        or (bool(m["pe"]) and m["pe"] > 0 and bool(m["roe"]) and m["roe"] > 0)
        or (bool(m["fpe"]) and m["fpe"] > 0 and bool(profits) and sum(profits[-2:]) > 0)
    )

    same_ccy = (d.get("currency") == d.get("fin_currency")) or not d.get("fin_currency")
    m["fcf_yield"] = (
        (fcf / mcap * 100) if (fcf and mcap and mcap > 0 and same_ccy) else None
    )
    m["net_debt_ebitda"] = (
        (((d.get("debt") or 0) - (d.get("cash_bal") or 0)) / ebitda)
        if (ebitda and ebitda > 0) else None
    )
    m["interest_cover"] = (
        (ebit[-1] / abs(interest[-1]))
        if ebit and interest and abs(interest[-1]) > 0 else None
    )
    m["rev_ratio"] = (
        (revenues[-1] / max(revenues))
        if len(revenues) >= 2 and max(revenues) > 0 else None
    )
    m["profit_ratio"] = (
        (profits[-1] / max(profits))
        if len(profits) >= 2 and max(profits) > 0 else None
    )
    m["cash_quality"] = (
        (ocf[-1] / profits[-1])
        if ocf and profits and profits[-1] > 0 else None
    )
    m["goodwill_share"] = (
        (goodwill[-1] / assets[-1] * 100)
        if goodwill and assets and assets[-1] > 0 else None
    )
    m["share_growth"] = (
        (((shares[-1] / shares[0]) ** (1 / (len(shares) - 1))) - 1) * 100
        if len(shares) >= 2 and shares[0] > 0 and shares[-1] > 0 else None
    )

    m["margin_trend"] = None
    if len(gross) >= 2 and len(revenues) >= 2:
        pairs = min(len(gross), len(revenues))
        margins = [
            gross[-i] / revenues[-i]
            for i in range(1, pairs + 1) if revenues[-i]
        ]
        if len(margins) >= 2:
            m["margin_trend"] = margins[0] - margins[-1]
    return m


def diagnose_drop(d, m):
    if (m["rev_ratio"] is not None and m["rev_ratio"] < 0.88) or (
        m["rev_growth"] is not None and m["rev_growth"] < -0.05
    ):
        return "Revenue Contraction"
    if m["margin_trend"] is not None and m["margin_trend"] < -0.03:
        return "Margin Squeeze"
    if (m["profit_ratio"] is not None and m["profit_ratio"] < 0.78) or (
        m["earn_growth"] is not None and m["earn_growth"] < -0.12
    ):
        return "Recent Earnings Dip"
    if m["pe"] and m["fpe"] and m["fpe"] > m["pe"] * 1.12:
        return "Soft Forward Outlook"
    if (m["net_debt_ebitda"] is not None and m["net_debt_ebitda"] > 2.4) or (
        m["de"] is not None and m["de"] > 120 and not m["is_fin"]
    ):
        return "Debt & Rate Pressure"
    if m["cash_quality"] is not None and m["cash_quality"] < 0.80:
        return "Soft Cash Conversion"

    blob = " ".join(d.get("news") or []).lower()
    for words, label in NEWS_KEYWORDS:
        if any(w in blob for w in words):
            return label

    if m["pe"] and m["pe"] < m["fair_pe"] * 0.72:
        return "Multiple Compression"
    if d.get("sector") in ("Basic Materials", "Energy", "Industrials", "Consumer Cyclical"):
        return "Cyclical Sector Dip"
    return "Sector Valuation Reset"


def estimate_months(upside, d, m):
    if not upside or upside <= 0:
        return None
    ann_vol = max(0.16, min(0.60, d.get("ann_vol") or 0.28))
    base_years = (upside / 100.0) / (ann_vol * 1.15)
    mos = base_years * 12.0

    if m["pe"] and m["fpe"] and m["fpe"] < m["pe"] * 0.90:
        mos *= 0.82
    elif m["profit_ratio"] is not None and m["profit_ratio"] < 0.80:
        mos *= 1.25

    low52, price = d.get("low52") or 0, d.get("price") or 0
    if low52 > 0 and price > low52 * 1.10:
        mos *= 0.90

    return int(round(max(4.0, min(36.0, mos))))


def assess(d, min_fall, min_score, max_months=None):
    ath, price = d.get("ath") or 0, d.get("price") or 0
    fall = ((ath - price) / ath * 100) if ath else 0
    upside_peak = ((ath - price) / price * 100) if price else None
    m = metrics(d)

    flags = [
        name for name, get, test in CHECKS
        if get(m) is not None and test(get(m), m)
    ]
    possible = sum(1 for name, get, test in CHECKS if get(m) is not None)
    points = len(flags)
    score = (points / possible * 100) if possible else 0

    target = d.get("target")
    analysts = d.get("analysts") or 0
    min_analysts = 3 if d.get("region") == "US" else 0
    by_target = (
        ((target - price) / price * 100)
        if (target and price and target > price * 0.4 and analysts >= min_analysts)
        else None
    )

    pe, fpe, fair_pe = m["pe"], m["fpe"], m["fair_pe"]
    eff_pe = (
        min(pe, fpe * 1.15) if (pe and pe > 0 and fpe and fpe > 0)
        else (pe if (pe and pe > 0) else fpe)
    )
    raw_by_earnings = (
        min(150.0, ((fair_pe / eff_pe) - 1.0) * 100)
        if (eff_pe and eff_pe > 0) else None
    )
    by_earnings = (
        raw_by_earnings
        if (raw_by_earnings is not None and (raw_by_earnings > 0 or by_target is None))
        else None
    )

    fcf_y = m["fcf_yield"]
    by_fcf = (
        min(120.0, ((fcf_y / 5.0) - 1.0) * 100)
        if (fcf_y and fcf_y > 5.0) else None
    )

    anchors = []
    basis_parts = []
    for tag, val in (("A", by_target), ("E", by_earnings), ("F", by_fcf)):
        if val is not None:
            anchors.append(val)
            basis_parts.append(tag)

    if not anchors and m["profitable"] and upside_peak and upside_peak > 15:
        anchors.append(min(65.0, upside_peak * 0.45))
        basis_parts.append("R")

    upside = sum(anchors) / len(anchors) if anchors else None
    basis = "+".join(basis_parts) if basis_parts else "-"
    b_rank = basis_strength(basis)
    mos = estimate_months(upside, d, m)
    why_down = diagnose_drop(d, m)

    base_ok = (
        m["profitable"]
        and (m["is_fin"] or m["cr"] is None or m["cr"] > 0.85)
        and (m["pe"] is None or m["pe"] > 0)
        and (m["fpe"] is None or m["fpe"] <= (m["pe"] or 999) * 1.25)
        and (max_months is None or (mos is not None and mos <= max_months))
    )

    qualifies = (
        base_ok
        and fall >= min_fall
        and score >= min_score
        and upside is not None and upside >= 8.0
    )

    qualifies_tier2 = (
        base_ok
        and not qualifies
        and fall >= max(15.0, min_fall * 0.65)
        and score >= max(48.0, min_score - 10.0)
        and upside is not None and upside > 2.0
    )

    return {
        "symbol": d["symbol"],
        "name": d["name"],
        "sector": d.get("sector") or "Unknown",
        "region": d["region"],
        "currency": d.get("currency", ""),
        "price": round(price, 2) if price is not None else None,
        "ath": round(ath, 2) if ath is not None else None,
        "fall": round(fall, 1) if fall is not None else None,
        "pe": round(m["pe"], 1) if m["pe"] is not None else None,
        "fpe": round(m["fpe"], 1) if m["fpe"] is not None else None,
        "roe": round(m["roe"], 4) if m["roe"] is not None else None,
        "flags": flags,
        "points": points,
        "possible": possible,
        "score": round(score, 1),
        "upside_peak": round(upside_peak, 1) if upside_peak is not None else None,
        "upside": round(upside, 1) if upside is not None else None,
        "mos": mos,
        "basis": basis,
        "basis_rank": b_rank,
        "why_down": why_down,
        "qualifies": qualifies,
        "qualifies_tier2": qualifies_tier2,
    }


def print_group(title, rows, limit, pool, args):
    print(f"  {title}")
    print("-" * 126)
    if not rows:
        print("  Nothing cleared the filters here.")
        if pool:
            bits = []
            for label, count in (
                (f"are less than {args.fall:.0f}% below their {args.period} peak",
                 sum(1 for r in pool if r["fall"] < args.fall)),
                (f"scored under {args.score:.0f}%",
                 sum(1 for r in pool if r["score"] < args.score)),
                ("had no positive upside estimate",
                 sum(1 for r in pool if not r["upside"] or r["upside"] <= 0)),
            ):
                if count:
                    bits.append(f"{count} {label}")
            print(f"  (of {len(pool)} checked, " + "; ".join(bits) + ")")
        else:
            print("  (no companies from this market were downloaded)")
        print()
        return

    print(
        f"  {'NO':<4}{'TICKER':<14}{'SECTOR':<22}{'PRICE':>10}{'FALL':>6}"
        f"{'P/E':>6}{'FP/E':>6}{'ROE':>6}{'SCORE':>7}{'UPSIDE':>8}"
        f"{'MOS':>5}{'BASIS':>6}  {'WHY DOWN (3-4 WDS)':<22}"
    )
    for idx, r in enumerate(rows[:limit], 1):
        mos_str = f"{r['mos']}m" if r["mos"] is not None else "-"
        print(
            f"  {idx:<4}{r['symbol'][:13]:<14}{r['sector'][:21]:<22}"
            f"{r['price']:>10,.2f}{r['fall']:>5.0f}%"
            f"{cell(r['pe'], '.1f'):>6}{cell(r['fpe'], '.1f'):>6}"
            f"{cell(r['roe'], '.0f', 100, '%'):>6}"
            f"{str(r['points']) + '/' + str(r['possible']):>7}"
            f"{cell(r['upside'], '+.0f', suffix='%'):>8}"
            f"{mos_str:>5}{r['basis']:>6}  {r['why_down'][:22]:<22}"
        )
    print()


def load_cache(fresh, wanted, period):
    if fresh:
        return None
    try:
        with open(CACHE, "r", encoding="utf-8") as handle:
            saved = json.load(handle)
        if saved.get("version") != CACHE_VERSION:
            return None
        if saved.get("period", "5y") != period:
            return None
        if not set(wanted).issubset(set(saved.get("symbols", []))):
            return None
        if (datetime.now().timestamp() - saved["fetched"]) / 3600 >= CACHE_HOURS:
            return None
        return [c for c in saved["companies"] if c["symbol"] in set(wanted)]
    except Exception:
        return None


def gather(symbols, workers, period="5y"):
    companies, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(pull_company, s, period): s for s in symbols}
        for future in as_completed(futures):
            done += 1
            print(f"  downloading {done}/{len(symbols)}", end="\r", flush=True)
            try:
                row = future.result()
                if row:
                    companies.append(row)
            except Exception:
                continue
    print(" " * 50, end="\r")
    try:
        with open(CACHE, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "version": CACHE_VERSION,
                    "period": period,
                    "symbols": list(symbols),
                    "fetched": datetime.now().timestamp(),
                    "companies": companies,
                },
                handle,
            )
    except Exception:
        pass
    return companies


def run_screen(args, index_data):
    wanted = get_universe(args)
    companies = load_cache(args.fresh, wanted, args.period)
    if companies is None:
        print(f"  Downloading {len(wanted)} companies, this takes a few minutes...")
        companies = gather(wanted, args.workers, args.period)
    if not companies:
        print("  No company data could be downloaded. Check the connection,")
        print("  then try:  python screener.py --region us --limit 5 --fresh\n")
        return

    scored = [assess(c, args.fall, args.score, args.max_months) for c in companies]

    custom_sort_key = lambda r: (
        -round(r["score"], 2),
        -r["basis_rank"],
        -(r["upside"] or 0),
    )

    regions_output = {}
    for region in ("US", "EUROPE", "INDIA"):
        pool = [r for r in scored if r["region"] == region]
        if not pool and args.region != "both":
            continue

        tier1 = sorted([r for r in pool if r["qualifies"]], key=custom_sort_key)
        tier2 = sorted([r for r in pool if r["qualifies_tier2"]], key=custom_sort_key)
        combined = sorted((tier1 + tier2)[:args.top], key=custom_sort_key)
        regions_output[region] = combined

        print_group(
            f"UNDERVALUED WITH STRONG FUNDAMENTALS - {region}",
            combined,
            args.top,
            pool,
            args,
        )

    if args.json:
        payload = {
            "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period": args.period,
            "min_fall": args.fall,
            "min_score": args.score,
            "total_scanned": len(scored),
            "indexes": index_data,
            "regions": regions_output,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"  Saved dashboard JSON to {args.json}\n")


def main():
    parser = argparse.ArgumentParser(
        description="US, Europe and India deep-value & fundamental quality screener"
    )
    parser.add_argument("--fall", type=float, default=25, help="Min %% drop from peak")
    parser.add_argument("--score", type=float, default=55, help="Min %% fundamental checks passed")
    parser.add_argument("--top", type=int, default=10, help="Max stocks to show per region")
    parser.add_argument("--max-months", type=int, default=None, help="Max estimated months to upside")
    parser.add_argument("--period", choices=["3y", "5y", "10y", "max"], default="5y")
    parser.add_argument("--region", choices=["us", "eu", "in", "both"], default="both")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--indexes-only", action="store_true")
    parser.add_argument("--json", type=str, default=None, help="Output JSON file path (e.g. data.json)")
    args = parser.parse_args()

    index_data = fetch_and_show_indexes()
    if args.indexes_only:
        return 0
    try:
        import yfinance  # noqa: F401
    except Exception as err:
        print(f"  Cannot import yfinance ({type(err).__name__}: {err})")
        print("  Install it with:  python -m pip install yfinance\n")
        return 1
    run_screen(args, index_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
