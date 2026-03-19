import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.title("🔥 TEA - Wheel Scanner (PRO VERSION AUTONOME)")

selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer")

tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

# -------------------------
# BLACK-SCHOLES
# -------------------------
def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def norm_pdf(x):
    return (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x**2)

def greeks_put(S, K, T, r, sigma):

    if T <= 0:
        return 0, 0, 0

    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    delta = norm_cdf(d1) - 1
    theta = (-S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))) + (r * K * math.exp(-r * T) * norm_cdf(-d2))
    vega = S * norm_pdf(d1) * math.sqrt(T)

    return delta, theta, vega

# -------------------------
# DATA
# -------------------------
def get_price(ticker):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
    return requests.get(url).json()["results"][0]["c"]

def get_options(ticker):
    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
    return requests.get(url).json().get("results", [])

def get_quote(symbol):
    try:
        url = f"https://api.polygon.io/v3/quotes/options/{symbol}?limit=1&apiKey={API_KEY}"
        r = requests.get(url).json()
        res = r.get("results", [])
        if res:
            bid = res[0].get("bid_price", 0)
            ask = res[0].get("ask_price", 0)
            return bid, ask
    except:
        pass
    return 0, 0

# -------------------------
# BUILD SYMBOL
# -------------------------
def build_option_symbol(ticker, expiration, strike):
    date = datetime.strptime(expiration, "%Y-%m-%d")
    yymmdd = date.strftime("%y%m%d")

    strike_int = int(float(strike) * 1000)
    strike_str = str(strike_int).zfill(8)

    return f"O:{ticker}{yymmdd}P{strike_str}"

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

            if abs((opt_date - selected_date).days) > 3:
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

            # 🔥 CALCUL GREEKS
            delta, theta, vega = greeks_put(price, strike, T, 0.04, 0.30)

            # 🔥 QUOTE RÉELLE
            symbol = build_option_symbol(ticker, exp, strike)
            bid, ask = get_quote(symbol)

            if bid == 0 and ask == 0:
                continue

            premium = (bid + ask) / 2 if bid and ask else max(bid, ask)

            results.append({
                "Ticker": ticker,
                "Strike": strike,
                "Price": price,
                "Delta": round(delta, 3),
                "Theta": round(theta, 2),
                "Vega": round(vega, 2),
                "Premium": round(premium, 2),
                "Premium/Strike %": round(premium / strike * 100, 2),
                "Distance %": round(distance * 100, 2)
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé (marché calme ou filtre)")
    else:
        df = df.sort_values("Premium/Strike %", ascending=False)
        st.dataframe(df, use_container_width=True)

else:
    st.info("👉 Clique sur Lancer")
