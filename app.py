import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (WORKING VERSION)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer le scan")

# -------------------------
# STOCKS TEST (LIQUIDES)
# -------------------------
tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

# -------------------------
# DATA
# -------------------------
@st.cache_data(ttl=60)
def get_chain_snapshot(ticker):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={API_KEY}"
        r = requests.get(url).json()
        return r.get("results", [])
    except:
        return []

# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []

    for ticker in tickers:

        chain = get_chain_snapshot(ticker)

        if not chain:
            continue

        for opt in chain:

            details = opt.get("details", {})
            greeks = opt.get("greeks", {}) or {}
            last_trade = opt.get("last_trade", {}) or {}

            if details.get("contract_type") != "put":
                continue

            # 🎯 expiration
            exp = details.get("expiration_date")
            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            if abs((opt_date - selected_date).days) > 2:
                continue

            # 🎯 strike
            strike = details.get("strike_price")

            # 🔥 FIX CRITIQUE (prix sous-jacent)
            underlying = opt.get("underlying_asset", {}) or {}
            price = underlying.get("last")

            if not strike or not price:
                continue

            if strike >= price:
                continue

            # 🎯 distance proxy delta
            distance = (price - strike) / price
            if not (0.02 <= distance <= 0.10):
                continue

            # 🎯 premium réel
            last = last_trade.get("price")

            if not last or last <= 0:
                continue

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": strike,
                "Distance %": round(distance * 100, 2),
                "Delta": greeks.get("delta"),
                "Theta": greeks.get("theta"),
                "Vega": greeks.get("vega"),
                "IV": round((opt.get("implied_volatility") or 0) * 100, 1),
                "Premium (LAST)": round(last, 2),
                "Premium/Strike %": round(last / strike * 100, 2)
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
    else:
        df = df.sort_values("Premium/Strike %", ascending=False)

        st.subheader("🔥 Résultats réels")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 Top 10")
        st.write(df.head(10))

else:
    st.info("👉 Clique sur Lancer le scan")
