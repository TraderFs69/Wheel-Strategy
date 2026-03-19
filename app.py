import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (STABLE VERSION)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer le scan")

# -------------------------
# STOCKS TEST
# -------------------------
tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

# -------------------------
# DATA FUNCTIONS
# -------------------------
@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
        r = requests.get(url).json()
        return r["results"][0]["c"]
    except:
        return None

@st.cache_data(ttl=300)
def get_options(ticker):
    try:
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
        return requests.get(url).json().get("results", [])
    except:
        return []

@st.cache_data(ttl=60)
def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()
        return r.get("results", {})
    except:
        return {}

# -------------------------
# MAIN SCAN
# -------------------------
if run_scan:

    results = []

    for ticker in tickers:

        price = get_price(ticker)
        if not price:
            continue

        options = get_options(ticker)

        candidates = []

        # -------------------------
        # STEP 1: FIND CANDIDATES
        # -------------------------
        for opt in options:

            if opt.get("contract_type") != "put":
                continue

            exp = opt.get("expiration_date")

            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            # 🔥 tolérance élargie
            if abs((opt_date - selected_date).days) > 5:
                continue

            strike = opt.get("strike_price")

            if not strike or strike >= price:
                continue

            distance = (price - strike) / price

            if 0.02 <= distance <= 0.12:
                candidates.append((opt, distance))

        # 🔥 limiter à 20 options (important)
        candidates = sorted(candidates, key=lambda x: x[1])[:20]

        # -------------------------
        # STEP 2: SNAPSHOT
        # -------------------------
        for opt, distance in candidates:

            snap = get_snapshot(opt.get("ticker")) or {}

            greeks = snap.get("greeks", {}) or {}
            last_trade = snap.get("last_trade", {}) or {}

            results.append({
                "Ticker": ticker,
                "Strike": opt.get("strike_price"),
                "Distance %": round(distance * 100, 2),
                "Delta": greeks.get("delta"),
                "Theta": greeks.get("theta"),
                "Vega": greeks.get("vega"),
                "Premium (LAST)": last_trade.get("price", 0)
            })

    df = pd.DataFrame(results)

    # -------------------------
    # DISPLAY
    # -------------------------
    if df.empty:
        st.error("⚠️ Aucun résultat trouvé")
    else:
        st.subheader("🔥 Résultats bruts (debug)")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 Top 10 (par premium)")
        df_sorted = df.sort_values("Premium (LAST)", ascending=False)
        st.write(df_sorted.head(10))

else:
    st.info("👉 Clique sur Lancer le scan")
