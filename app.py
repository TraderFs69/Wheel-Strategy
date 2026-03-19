import streamlit as st
import pandas as pd
import requests
import math
import time
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (FINAL STABLE)")

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

# -------------------------
# BUILD SYMBOL
# -------------------------
def build_option_symbol(ticker, expiration, strike):
    try:
        date = datetime.strptime(expiration, "%Y-%m-%d")
        yymmdd = date.strftime("%y%m%d")

        strike_int = int(float(strike) * 1000)
        strike_str = str(strike_int).zfill(8)

        return f"O:{ticker}{yymmdd}P{strike_str}"
    except:
        return None

# -------------------------
# PREMIUM (REAL + FALLBACK)
# -------------------------
def get_option_premium(symbol, price, strike, T):

    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()

        res = r.get("results", {})

        last = res.get("last_trade", {}) or {}
        quote = res.get("last_quote", {}) or {}

        bid = quote.get("bid")
        ask = quote.get("ask")
        last_price = last.get("price")

        # 1️⃣ MID PRICE
        if bid and ask and bid > 0 and ask > 0:
            return (bid + ask) / 2

        # 2️⃣ LAST
        if last_price and last_price > 0:
            return last_price

    except:
        pass

    # 💣 FALLBACK INTELLIGENT
    intrinsic = max(0, strike - price)
    extrinsic = price * 0.02 * math.sqrt(T)

    return intrinsic + extrinsic

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

            # 💣 FILTRE EXACT DATE
            if opt_date != selected_date:
                continue

            strike = opt.get("strike_price")

            if not strike or strike >= price:
                continue

            distance = (price - strike) / price

            if not (0.01 <= distance <= 0.15):
                continue

            dte = (opt_date - datetime.today().date()).days
            if dte <= 0:
                continue

            T = dte / 365

            delta, theta, vega = greeks_put(price, strike, T, 0.04, 0.30)

            symbol = build_option_symbol(ticker, exp, strike)
            if not symbol:
                continue

            premium = get_option_premium(symbol, price, strike, T)

            time.sleep(0.15)  # rate limit protection

            results.append({
                "Ticker": ticker,
                "Expiration": exp,
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
        st.error("⚠️ Aucun trade trouvé (très improbable maintenant)")
    else:
        df = df.sort_values("Premium/Strike %", ascending=False)

        st.subheader("🔥 Résultats")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 Top 10")
        st.write(df.head(10))

        st.write("📅 Dates présentes :", df["Expiration"].unique())

else:
    st.info("👉 Clique sur Lancer le scan")
