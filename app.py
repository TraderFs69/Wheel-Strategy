import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner PRO")

# -------------------------
# HEADER
# -------------------------
col1, col2, col3 = st.columns(3)
col1.metric("Mode", "Wheel")
col2.metric("Data", "Polygon")
col3.metric("Status", "Running")

# -------------------------
# SIDEBAR FILTERS (ASSOUPLIS)
# -------------------------
st.sidebar.header("⚙️ Filters")

min_return = st.sidebar.slider("Min Annual Return %", 0, 50, 5)
min_safety = st.sidebar.slider("Min Distance OTM %", 0, 15, 2)
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

def approx_delta(price, strike):
    dist = (price - strike) / price
    if dist < 0.03:
        return -0.35
    elif dist < 0.06:
        return -0.25
    elif dist < 0.10:
        return -0.15
    else:
        return -0.10

def estimate_premium(price, strike):
    # approximation simple si pas de bid/ask
    return max(0.5, abs(price - strike) * 0.05)

def compute_metrics(price, strike, premium, dte, oi):
    annual_return = (premium / strike) * (365 / dte)
    safety = (price - strike) / price
    liquidity = min(oi / 1000, 1)

    score = (
        annual_return * 0.4 +
        safety * 0.3 +
        liquidity * 0.2 +
        0.1
    )

    return annual_return, safety, score

# -------------------------
# MAIN SCAN
# -------------------------
results = []

progress = st.progress(0)

for i, ticker in enumerate(tickers[:100]):  # limiter pour vitesse initiale

    price = get_price(ticker)
    if not price:
        continue

    options = get_options_reference(ticker)

    if not options:
        continue

    for opt in options:

        if opt.get("contract_type") != "put":
            continue

        strike = opt.get("strike_price")
        expiration = opt.get("expiration_date")

        if not strike or not expiration:
            continue

        expiration = datetime.strptime(expiration, "%Y-%m-%d")
        dte = (expiration - datetime.today()).days

        if dte < 20 or dte > 60:
            continue

        oi = opt.get("open_interest", 100)

        if oi < min_oi:
            continue

        delta = approx_delta(price, strike)

        if not (-0.35 <= delta <= -0.10):
            continue

        premium = estimate_premium(price, strike)

        annual_return, safety, score = compute_metrics(price, strike, premium, dte, oi)

        if annual_return * 100 < min_return:
            continue

        if safety * 100 < min_safety:
            continue

        results.append({
            "Ticker": ticker,
            "Price": round(price, 2),
            "Strike": strike,
            "Premium (est)": round(premium, 2),
            "DTE": dte,
            "Annual %": round(annual_return * 100, 2),
            "Safety %": round(safety * 100, 2),
            "Score": round(score, 2)
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
        st.subheader("📊 Wheel Opportunities")
        st.dataframe(df, use_container_width=True)

    with colB:
        st.subheader("🏆 Top 5")
        st.write(df.head(5))

else:
    st.error("⚠️ No trades found — data source limited or filters too strict")

# -------------------------
# DEBUG INFO
# -------------------------
st.caption(f"Tickers scanned: {len(tickers[:100])}")
