import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (SNAPSHOT MODE)")

selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer le scan")

tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

def get_chain_snapshot(ticker):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={API_KEY}"
        r = requests.get(url).json()
        return r.get("results", [])
    except:
        return []

if run_scan:

    results = []

    for ticker in tickers:

        chain = get_chain_snapshot(ticker)

        for opt in chain:

            details = opt.get("details", {})
            greeks = opt.get("greeks", {}) or {}
            last_trade = opt.get("last_trade", {}) or {}

            if details.get("contract_type") != "put":
                continue

            exp = details.get("expiration_date")

            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            if abs((opt_date - selected_date).days) > 2:
                continue

            strike = details.get("strike_price")
            price = opt.get("underlying_asset", {}).get("price")

            if not strike or not price:
                continue

            if strike >= price:
                continue

            distance = (price - strike) / price

            # 🎯 filtre intelligent delta proxy
            if not (0.02 <= distance <= 0.10):
                continue

            delta = greeks.get("delta")
            theta = greeks.get("theta")
            vega = greeks.get("vega")

            last = last_trade.get("price")

            if not last or last <= 0:
                continue

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": strike,
                "Distance %": round(distance * 100, 2),
                "Delta": delta,
                "Theta": theta,
                "Vega": vega,
                "Premium (LAST)": last,
                "Premium/Strike %": round(last / strike * 100, 2)
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
    else:
        df = df.sort_values("Premium/Strike %", ascending=False)
        st.dataframe(df, use_container_width=True)
