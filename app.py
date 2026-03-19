import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner PRO MAX")

# -------------------------
# HEADER
# -------------------------
col1, col2, col3 = st.columns(3)
col1.metric("Mode", "Wheel PRO")
col2.metric("Data", "Polygon + Greeks")
col3.metric("Status", "Running")

# -------------------------
# SIDEBAR FILTERS
# -------------------------
st.sidebar.header("⚙️ Filters")

min_return = st.sidebar.slider("Min Annual Return %", 0, 50, 5)
min_safety = st.sidebar.slider("Min Distance OTM %", 0, 15, 2)
min_pop = st.sidebar.slider("Min POP %", 50, 95, 70)
min_oi = st.sidebar.slider("Min Open Interest", 0, 2000, 50)

# -------------------------
# LOAD TICKERS
# -------------------------
@st.cache_data
def load_sp500():
    try:
        df = pd.read_excel("sp500_constituents.xlsx")
        return df["Symbol"].tolist()
    except:
        url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
        df = pd.read_csv(url)
        return df["Symbol"].tolist()

tickers = load_sp500()

# -------------------------
# DATA FUNCTIONS
# -------------------------
@st.cache_data(ttl=300)
def get_price(ticker):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
    r = requests.get(url).json()
    return r["results"][0]["c"] if "results" in r else None


@st.cache_data(ttl=300)
def get_options_reference(ticker):
    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=100&apiKey={API_KEY}"
    r = requests.get(url).json()
    return r.get("results", [])


@st.cache_data(ttl=300)
def get_option_snapshot(option_ticker):
    url = f"https://api.polygon.io/v3/snapshot/options/{option_ticker}?apiKey={API_KEY}"
    r = requests.get(url).json()

    if "results" not in r:
        return None

    res = r["results"]

    try:
        greeks = res.get("greeks", {})
        last_quote = res.get("last_quote", {})

        bid = last_quote.get("bid", 0)
        ask = last_quote.get("ask", 0)
        mid = (bid + ask) / 2 if bid and ask else bid or ask or 0

        return {
            "delta": greeks.get("delta"),
            "theta": greeks.get("theta"),
            "iv": res.get("implied_volatility"),
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "volume": res.get("day", {}).get("volume", 0)
        }

    except:
        return None


@st.cache_data(ttl=3600)
def get_earnings_date(ticker):
    url = f"https://api.polygon.io/v3/reference/tickers/{ticker}?apiKey={API_KEY}"
    r = requests.get(url).json()

    try:
        return r["results"].get("earnings_date")
    except:
        return None


# -------------------------
# METRICS PRO
# -------------------------
def compute_metrics(price, strike, premium, dte, oi, delta, theta, iv, volume):

    if not premium or premium == 0 or delta is None:
        return None

    annual_return = (premium / strike) * (365 / dte)
    safety = (price - strike) / price

    pop = 1 - abs(delta)
    theta_income = abs(theta) if theta else 0

    liquidity = min((oi + volume) / 2000, 1)
    iv_score = min(iv / 0.5, 1) if iv else 0

    score = (
        annual_return * 0.30 +
        safety * 0.20 +
        pop * 0.20 +
        theta_income * 0.10 +
        iv_score * 0.10 +
        liquidity * 0.10
    )

    return annual_return, safety, pop, score


# -------------------------
# MAIN SCAN
# -------------------------
results = []

progress = st.progress(0)

for i, ticker in enumerate(tickers[:100]):

    price = get_price(ticker)
    if not price:
        continue

    earnings_date = get_earnings_date(ticker)

    options = get_options_reference(ticker)
    if not options:
        continue

    for opt in options:

        if opt.get("contract_type") != "put":
            continue

        strike = opt.get("strike_price")
        expiration = opt.get("expiration_date")
        option_symbol = opt.get("ticker")

        if not strike or not expiration or not option_symbol:
            continue

        expiration_dt = datetime.strptime(expiration, "%Y-%m-%d")
        dte = (expiration_dt - datetime.today()).days

        if dte < 20 or dte > 60:
            continue

        # 🚫 Earnings filter
        if earnings_date:
            earnings_dt = datetime.strptime(earnings_date, "%Y-%m-%d")
            if datetime.today() < earnings_dt < expiration_dt:
                continue

        oi = opt.get("open_interest", 0)
        if oi < min_oi:
            continue

        snapshot = get_option_snapshot(option_symbol)
        if not snapshot:
            continue

        delta = snapshot["delta"]
        theta = snapshot["theta"]
        iv = snapshot["iv"]
        premium = snapshot["mid"]
        volume = snapshot["volume"]

        if delta is None or not (-0.30 <= delta <= -0.10):
            continue

        metrics = compute_metrics(price, strike, premium, dte, oi, delta, theta, iv, volume)
        if not metrics:
            continue

        annual_return, safety, pop, score = metrics

        if annual_return * 100 < min_return:
            continue

        if safety * 100 < min_safety:
            continue

        if pop * 100 < min_pop:
            continue

        results.append({
            "Ticker": ticker,
            "Price": round(price, 2),
            "Strike": strike,
            "Premium": round(premium, 2),
            "DTE": dte,
            "Annual %": round(annual_return * 100, 2),
            "Safety %": round(safety * 100, 2),
            "POP %": round(pop * 100, 2),
            "Delta": round(delta, 2),
            "Theta": round(theta, 3) if theta else None,
            "IV": round(iv, 2) if iv else None,
            "Volume": volume,
            "OI": oi,
            "Score": round(score, 3)
        })

    progress.progress((i + 1) / len(tickers[:100]))

# -------------------------
# DISPLAY
# -------------------------
df = pd.DataFrame(results)

if not df.empty:
    df = df.sort_values("Score", ascending=False)

    colA, colB = st.columns([3,1])

    with colA:
        st.subheader("📊 Wheel Opportunities PRO")
        st.dataframe(df, use_container_width=True)

    with colB:
        st.subheader("🏆 Top 5")
        st.write(df.head(5))

else:
    st.error("⚠️ No trades found — ajuste tes filtres")

# -------------------------
# DEBUG
# -------------------------
st.caption(f"Tickers scanned: {len(tickers[:100])}")
