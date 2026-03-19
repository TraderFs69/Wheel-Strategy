import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (FINAL WORKING VERSION)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer")

# -------------------------
# STOCKS TEST
# -------------------------
tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

# -------------------------
# BUILD OPTION SYMBOL (FIX CRITIQUE)
# -------------------------
def build_option_symbol(ticker, expiration, strike, contract_type):
    try:
        date = datetime.strptime(expiration, "%Y-%m-%d")
        yymmdd = date.strftime("%y%m%d")

        strike_int = int(float(strike) * 1000)
        strike_str = str(strike_int).zfill(8)

        cp = "P" if contract_type == "put" else "C"

        return f"O:{ticker}{yymmdd}{cp}{strike_str}"
    except:
        return None

# -------------------------
# DATA FUNCTIONS
# -------------------------
def get_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
        r = requests.get(url).json()
        return r["results"][0]["c"]
    except:
        return None

def get_options(ticker):
    try:
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
        return requests.get(url).json().get("results", [])
    except:
        return []

def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()
        return r.get("results", {})
    except:
        return {}

# -------------------------
# BLACK-SCHOLES DELTA (fallback)
# -------------------------
def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def put_delta(S, K, T, r, sigma):
    if T <= 0:
        return 0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return norm_cdf(d1) - 1

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

        candidates = []

        # -------------------------
        # STEP 1: FILTER
        # -------------------------
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

        # 🔥 limiter appels API
        candidates = sorted(candidates, key=lambda x: x[1])[:20]

        # -------------------------
        # STEP 2: SNAPSHOT
        # -------------------------
        for opt, distance in candidates:

            symbol = build_option_symbol(
                ticker,
                opt.get("expiration_date"),
                opt.get("strike_price"),
                opt.get("contract_type")
            )

            if not symbol:
                continue

            snap = get_snapshot(symbol) or {}

            greeks = snap.get("greeks", {}) or {}
            last_trade = snap.get("last_trade", {}) or {}

            dte = (datetime.strptime(opt.get("expiration_date"), "%Y-%m-%d").date() - datetime.today().date()).days
            T = dte / 365 if dte > 0 else 0

            delta_calc = put_delta(price, opt.get("strike_price"), T, 0.04, 0.30)

            delta_real = greeks.get("delta")
            delta_used = delta_real if delta_real is not None else delta_calc

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

else:
    st.info("👉 Clique sur Lancer le scan")
