import streamlit as st
import pandas as pd
import requests
import math
import time
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner PRO (REAL DATA FIXED)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration", datetime.today())
run_scan = st.sidebar.button("🚀 Lancer le scan")

risk_free_rate = 0.04

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

def put_price_bs(S, K, T, r, sigma):
    if T <= 0:
        return max(K - S, 0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    Nd1 = norm_cdf(-d1)
    Nd2 = norm_cdf(-d2)
    return K * math.exp(-r * T) * Nd2 - S * Nd1

# -------------------------
# DATA
# -------------------------
@st.cache_data
def load_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    return pd.read_csv(url)["Symbol"].tolist()

@st.cache_data(ttl=300)
def get_options(ticker):
    try:
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
        return requests.get(url).json().get("results", [])
    except:
        return []

@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
        return requests.get(url).json()["results"][0]["c"]
    except:
        return None

@st.cache_data(ttl=60)
def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()
        res = r.get("results", {})

        greeks = res.get("greeks", {}) or {}
        last_trade = res.get("last_trade", {}) or {}

        return {
            "delta_real": greeks.get("delta"),
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

    tickers = load_sp500()

    results = []
    progress = st.progress(0)

    for i, ticker in enumerate(tickers):

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

            if abs((opt_date - selected_date).days) > 2:
                continue

            strike = opt.get("strike_price")

            if not strike or strike >= price:
                continue

            # 🎯 DISTANCE FILTER
            distance = (price - strike) / price
            if not (0.02 <= distance <= 0.15):
                continue

            dte = (opt_date - datetime.today().date()).days
            if dte <= 0:
                continue

            T = dte / 365

            # 🎯 DELTA INTERNE
            delta_calc = put_delta(price, strike, T, risk_free_rate, 0.30)

            # 🔥 SNAPSHOT
            snap = get_snapshot(opt.get("ticker"))

            if snap:
                iv = snap["iv"] if snap["iv"] else 0.30
                delta_real = snap["delta_real"]
                theta = snap["theta"]
                vega = snap["vega"]

                # 💣 PREMIUM RÉEL
                if snap["last"] and snap["last"] > 0:
                    premium = snap["last"]
                else:
                    premium = put_price_bs(price, strike, T, risk_free_rate, iv)

            else:
                iv = 0.30
                delta_real = None
                theta = None
                vega = None
                premium = put_price_bs(price, strike, T, risk_free_rate, iv)

            if premium <= 0:
                continue

            annual_return = (premium / strike) * (365 / dte)

            # 💣 SCORE
            delta_score = 1 - abs(abs(delta_calc) - 0.25)
            iv_score = iv
            theta_score = abs(theta) if theta else 0

            score = (
                annual_return * 0.5 +
                delta_score * 0.2 +
                iv_score * 0.2 +
                theta_score * 0.1
            )

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": strike,
                "Distance %": round(distance * 100, 2),
                "Delta calc": round(delta_calc, 3),
                "Delta réel": delta_real,
                "Theta": theta,
                "Vega": vega,
                "IV": round(iv * 100, 1),
                "Premium": round(premium, 2),
                "Premium/Strike %": round(premium / strike * 100, 2),
                "Annual %": round(annual_return * 100, 2),
                "Score": round(score, 3)
            })

            time.sleep(0.003)

        progress.progress((i + 1) / len(tickers))

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
        st.stop()

    # 🎯 FILTRE FINAL DELTA
    df_filtered = df[
        (df["Delta calc"] <= -0.20) &
        (df["Delta calc"] >= -0.30)
    ]

    if df_filtered.empty:
        st.warning("⚠️ Aucun trade strict → affichage élargi")
        df_filtered = df

    df_filtered = df_filtered.sort_values("Score", ascending=False)

    # -------------------------
    # DISPLAY
    # -------------------------
    col1, col2 = st.columns([3,1])

    with col1:
        st.subheader("🔥 Wheel Trades")
        st.dataframe(df_filtered, use_container_width=True)

    with col2:
        st.subheader("🏆 TOP 10")
        st.write(df_filtered.head(10))

else:
    st.info("👉 Clique sur Lancer le scan")
