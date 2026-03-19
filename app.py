import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.title("🔥 TEA - Wheel Scanner FINAL PRO")

selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer")

tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

# -------------------------
# MATH
# -------------------------
def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def put_delta(S, K, T, r, sigma):
    if T <= 0:
        return 0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return norm_cdf(d1) - 1

# -------------------------
# DATA
# -------------------------
def get_price(ticker):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
    return requests.get(url).json()["results"][0]["c"]

def get_options(ticker):
    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
    return requests.get(url).json().get("results", [])

def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()
        return r.get("results", {})
    except:
        return {}

# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []

    for ticker in tickers:

        price = get_price(ticker)
        options = get_options(ticker)

        candidates = []

        # STEP 1: FILTER INTELLIGENT
        for opt in options:

            if opt.get("contract_type") != "put":
                continue

            exp = opt.get("expiration_date")

            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            if abs((opt_date - selected_date).days) > 3:
                continue

            strike = opt.get("strike_price")

            if not strike or strike >= price:
                continue

            distance = (price - strike) / price

            if 0.02 <= distance <= 0.10:
                candidates.append((opt, distance))

        # 🔥 limiter pour performance
        candidates = sorted(candidates, key=lambda x: x[1])[:25]

        # STEP 2: SNAPSHOT PAR OPTION
        for opt, distance in candidates:

            snap = get_snapshot(opt.get("ticker")) or {}

            greeks = snap.get("greeks", {}) or {}
            last_trade = snap.get("last_trade", {}) or {}

            dte = (datetime.strptime(opt.get("expiration_date"), "%Y-%m-%d").date() - datetime.today().date()).days
            T = dte / 365 if dte > 0 else 0

            delta_calc = put_delta(price, opt.get("strike_price"), T, 0.04, 0.30)

            delta_real = greeks.get("delta")
            delta_used = delta_real if delta_real else delta_calc

            premium = last_trade.get("price", 0)

            results.append({
                "Ticker": ticker,
                "Strike": opt.get("strike_price"),
                "Distance %": round(distance * 100, 2),
                "Delta utilisé": round(delta_used, 3),
                "Delta réel": delta_real,
                "Theta": greeks.get("theta"),
                "Vega": greeks.get("vega"),
                "Premium": premium,
                "Premium/Strike %": round(premium / opt.get("strike_price") * 100, 2) if premium else 0
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
    else:
        df = df.sort_values("Premium/Strike %", ascending=False)

        st.subheader("🔥 Résultats")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 Top 10")
        st.write(df.head(10))
