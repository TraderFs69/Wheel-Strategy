import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.title("🔥 TEA - Wheel Scanner FINAL (TRUE DATA)")

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
    r = requests.get(url).json()
    return r["results"][0]["c"]

def get_options(ticker):
    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
    return requests.get(url).json().get("results", [])

def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()
        res = r.get("results", {})

        greeks = res.get("greeks", {}) or {}
        last = res.get("last_trade", {}).get("price", 0)

        return {
            "delta": greeks.get("delta"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            "iv": res.get("implied_volatility"),
            "last": last
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

            distance = (price - strike) / price

            if not (0.02 <= distance <= 0.10):
                continue

            dte = (opt_date - datetime.today().date()).days
            if dte <= 0:
                continue

            T = dte / 365

            delta_calc = put_delta(price, strike, T, 0.04, 0.30)

            # 🔥 SNAPSHOT PAR OPTION (LA CLÉ)
            snap = get_snapshot(opt.get("ticker"))

            if not snap:
                continue

            if not snap["last"] or snap["last"] <= 0:
                continue

            results.append({
                "Ticker": ticker,
                "Strike": strike,
                "Price": price,
                "Delta calc": round(delta_calc, 3),
                "Delta réel": snap["delta"],
                "Theta": snap["theta"],
                "Vega": snap["vega"],
                "IV": round((snap["iv"] or 0) * 100, 1),
                "Premium": round(snap["last"], 2),
                "Premium/Strike %": round(snap["last"] / strike * 100, 2),
                "Distance %": round(distance * 100, 2)
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
    else:
        df = df.sort_values("Premium/Strike %", ascending=False)
        st.dataframe(df, use_container_width=True)
