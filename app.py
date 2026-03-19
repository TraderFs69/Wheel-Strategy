import streamlit as st
import pandas as pd
import requests
import math
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner PRO (Ranking + Greeks réels)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration", datetime.today())
run_scan = st.sidebar.button("🚀 Calculer")

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
@st.cache_data(ttl=300)
def get_options(ticker):
    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
    return requests.get(url).json().get("results", [])

@st.cache_data(ttl=300)
def get_price(ticker):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
    try:
        return requests.get(url).json()["results"][0]["c"]
    except:
        return None

@st.cache_data(ttl=300)
def get_snapshot(symbol):
    url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
    r = requests.get(url).json()
    res = r.get("results", {})

    greeks = res.get("greeks", {}) or {}

    return {
        "delta_real": greeks.get("delta"),
        "theta": greeks.get("theta"),
        "vega": greeks.get("vega"),
        "iv": res.get("implied_volatility")
    }

# -------------------------
# TICKERS
# -------------------------
tickers = ["AAPL","MSFT","NVDA","AMD","TSLA","META","AMZN"]

# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []
    progress = st.progress(0)

    for i, ticker in enumerate(tickers):

        price = get_price(ticker)
        if not price:
            continue

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

            if abs((opt_date - selected_date).days) > 2:
                continue

            strike = opt.get("strike_price")

            if not strike or strike >= price:
                continue

            # 🎯 distance
            distance = (price - strike) / price
            if not (0.03 <= distance <= 0.10):
                continue

            dte = (opt_date - datetime.today().date()).days
            T = max(dte / 365, 0.01)

            # delta interne
            delta = put_delta(price, strike, T, risk_free_rate, 0.30)

            if not (-0.30 <= delta <= -0.20):
                continue

            candidates.append((opt, delta, T, dte, distance))

        # 🔥 ENRICHIR SEULEMENT TOP 10
        for opt, delta, T, dte, distance in candidates[:10]:

            snap = get_snapshot(opt.get("ticker"))

            iv = snap["iv"] if snap["iv"] else 0.30

            premium = put_price_bs(price, opt.get("strike_price"), T, risk_free_rate, iv)

            # -------------------------
            # 💣 RANKING
            # -------------------------
            annual_return = (premium / opt.get("strike_price")) * (365 / dte)

            score = (
                annual_return * 0.5 +
                abs(delta) * 0.3 +
                (iv if iv else 0.3) * 0.2
            )

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": opt.get("strike_price"),
                "Delta calc": round(delta, 3),
                "Delta réel": snap["delta_real"],
                "Theta": snap["theta"],
                "Vega": snap["vega"],
                "IV": round(iv * 100, 1) if iv else None,
                "Premium": round(premium, 2),
                "Premium/Strike %": round(premium / opt.get("strike_price") * 100, 2),
                "Annual %": round(annual_return * 100, 2),
                "Score": round(score, 3)
            })

        progress.progress((i + 1) / len(tickers))

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values("Score", ascending=False)

        st.subheader("🔥 Top Wheel Trades (Ranking)")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 TOP 5")
        st.write(df.head(5))

    else:
        st.error("⚠️ Aucun trade trouvé — élargir critères")

else:
    st.info("👉 Clique sur Calculer")
