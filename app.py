import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.title("🔥 TEA - Wheel Scanner (WORKING FINAL FIX)")

selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer")

tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

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

if run_scan:

    results = []

    for ticker in tickers:

        price = get_price(ticker)
        options = get_options(ticker)

        candidates = []

        for opt in options:

            if opt.get("contract_type") != "put":
                continue

            exp = opt.get("expiration_date")

            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            # ⚡ élargi tolérance
            if abs((opt_date - selected_date).days) > 5:
                continue

            strike = opt.get("strike_price")

            if not strike or strike >= price:
                continue

            distance = (price - strike) / price

            if 0.02 <= distance <= 0.12:
                candidates.append((opt, distance))

        # 🔥 garder seulement 20 meilleurs
        candidates = sorted(candidates, key=lambda x: x[1])[:20]

        for opt, distance in candidates:

            snap = get_snapshot(opt.get("ticker"))

            greeks = snap.get("greeks", {}) or {}
            last = snap.get("last_trade", {}).get("price", 0)

            results.append({
                "Ticker": ticker,
                "Strike": opt.get("strike_price"),
                "Distance %": round(distance * 100, 2),
                "Delta": greeks.get("delta"),
                "Theta": greeks.get("theta"),
                "Vega": greeks.get("vega"),
                "Premium": last
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Toujours aucun résultat → problème API plan")
    else:
        st.dataframe(df, use_container_width=True)
