import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (TEST 5 STOCKS)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer le scan")

risk_free_rate = 0.04

# -------------------------
# STOCKS LIQUIDES
# -------------------------
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
@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
        return requests.get(url).json()["results"][0]["c"]
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
        res = r.get("results", {})

        greeks = res.get("greeks", {}) or {}
        last_trade = res.get("last_trade", {}) or {}

        return {
            "delta": greeks.get("delta"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            "iv": res.get("implied_volatility"),
            "last": last_trade.get("price", 0)
        }
    except:
        return None

# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []

    for ticker in tickers:

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

            # 🎯 MATCH DATE
            if abs((opt_date - selected_date).days) > 2:
                continue

            strike = opt.get("strike_price")

            if not strike or strike >= price:
                continue

            # 🎯 DISTANCE (plus proche = plus liquide)
            distance = (price - strike) / price
            if not (0.02 <= distance <= 0.07):
                continue

            # 🎯 OPEN INTEREST
            if opt.get("open_interest", 0) < 100:
                continue

            dte = (opt_date - datetime.today().date()).days
            if dte <= 0:
                continue

            T = dte / 365

            delta_calc = put_delta(price, strike, T, risk_free_rate, 0.30)

            # 🔥 SNAPSHOT
            snap = get_snapshot(opt.get("ticker"))

            # 💣 FILTRE CRITIQUE
            if not snap or not snap["last"] or snap["last"] < 0.05:
                continue

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": strike,
                "Distance %": round(distance * 100, 2),
                "Delta calc": round(delta_calc, 3),
                "Delta réel": snap["delta"],
                "Theta": snap["theta"],
                "Vega": snap["vega"],
                "IV": round((snap["iv"] or 0) * 100, 1),
                "Premium (LAST)": round(snap["last"], 2),
                "Premium/Strike %": round(snap["last"] / strike * 100, 2)
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
        st.stop()

    df = df.sort_values("Premium/Strike %", ascending=False)

    st.subheader("🔥 Résultats (TEST RÉEL)")
    st.dataframe(df, use_container_width=True)

else:
    st.info("👉 Clique sur Lancer le scan")
