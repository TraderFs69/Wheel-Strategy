import streamlit as st
import pandas as pd
import requests
import numpy as np
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (Delta Interne)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration", datetime.today())
run_scan = st.sidebar.button("🚀 Calculer")

# paramètres modèle
risk_free_rate = 0.04
volatility = 0.30  # approximation

# -------------------------
# NORMAL CDF
# -------------------------
def norm_cdf(x):
    return 0.5 * (1 + np.math.erf(x / np.sqrt(2)))

# -------------------------
# DELTA PUT (Black-Scholes)
# -------------------------
def put_delta(S, K, T, r, sigma):
    if T <= 0:
        return 0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm_cdf(d1) - 1

# -------------------------
# DATA
# -------------------------
@st.cache_data(ttl=300)
def get_options(ticker):
    try:
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
        return requests.get(url).json().get("results", [])
    except:
        return []

@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
        return requests.get(url).json()["results"][0]["c"]
    except:
        return None

@st.cache_data(ttl=300)
def get_bid_ask(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()
        res = r.get("results", {})
        quote = res.get("last_quote", {}) or {}

        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)

        premium = (bid + ask) / 2 if bid and ask else bid or 0

        return premium, bid, ask
    except:
        return 0, 0, 0

# -------------------------
# TICKERS (rapide)
# -------------------------
tickers = ["AAPL","MSFT","NVDA","AMD","TSLA","META","AMZN"]

# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []
    progress = st.progress(0)

    for i, ticker in enumerate(tickers):

        price = get_price(ticker)
        if not price:
            continue

        options = get_options(ticker)

        for opt in options:

            if opt.get("contract_type") != "put":
                continue

            exp = opt.get("expiration_date")

            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            if abs((opt_date - selected_date).days) > 2:
                continue

            strike = opt.get("strike_price")

            if not strike or strike >= price:
                continue

            # temps en années
            dte = (opt_date - datetime.today().date()).days
            T = max(dte / 365, 0.01)

            # 🎯 DELTA INTERNE
            delta = put_delta(price, strike, T, risk_free_rate, volatility)

            if not (-0.30 <= delta <= -0.20):
                continue

            premium, bid, ask = get_bid_ask(opt.get("ticker"))

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": strike,
                "Delta (calc)": round(delta, 3),
                "Premium": round(premium, 2),
                "Premium/Strike %": round(premium / strike * 100, 2) if strike else 0,
                "Bid": bid,
                "Ask": ask,
                "DTE": dte
            })

        progress.progress((i + 1) / len(tickers))

    df = pd.DataFrame(results)

    if not df.empty:
        st.subheader("🔥 Wheel Trades (Delta Interne)")
        st.dataframe(df.sort_values("Premium/Strike %", ascending=False), use_container_width=True)
    else:
        st.error("⚠️ Aucun trade trouvé (élargir critères)")

else:
    st.info("👉 Clique sur Calculer")
