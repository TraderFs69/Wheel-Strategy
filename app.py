import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("⚡ TEA - Wheel Scanner (EXPIRATION MODE)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration", datetime.today())
run_scan = st.sidebar.button("🚀 Calculer")

# -------------------------
# DATA
# -------------------------
@st.cache_data(ttl=300)
def get_all_options_by_date(date_str):
    try:
        url = f"https://api.polygon.io/v3/reference/options/contracts?expiration_date={date_str}&limit=1000&apiKey={API_KEY}"
        r = requests.get(url).json()
        return r.get("results", [])
    except:
        return []


@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
        return requests.get(url).json()["results"][0]["c"]
    except:
        return None


@st.cache_data(ttl=300)
def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()
        res = r.get("results", {})

        greeks = res.get("greeks", {}) or {}
        quote = res.get("last_quote", {}) or {}

        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)
        premium = (bid + ask) / 2 if bid and ask else bid or 0

        return {
            "delta": greeks.get("delta"),
            "premium": premium,
            "bid": bid,
            "ask": ask
        }
    except:
        return None


# -------------------------
# SCAN
# -------------------------
if run_scan:

    date_str = selected_date.strftime("%Y-%m-%d")
    st.write(f"🔎 Scan direct expiration: {date_str}")

    options = get_all_options_by_date(date_str)

    st.write(f"Options récupérées: {len(options)}")

    results = []
    progress = st.progress(0)

    for i, opt in enumerate(options):

        if opt.get("contract_type") != "put":
            continue

        ticker = opt.get("underlying_ticker")
        strike = opt.get("strike_price")

        if not ticker or not strike:
            continue

        price = get_price(ticker)
        if not price:
            continue

        # 🎯 DISTANCE (delta proxy)
        if strike >= price:
            continue

        distance = (price - strike) / price

        if not (0.03 <= distance <= 0.10):
            continue

        # 🔥 snapshot seulement ici
        snap = get_snapshot(opt.get("ticker"))
        if not snap:
            continue

        delta = snap.get("delta")
        if delta is None:
            continue

        if not (-0.30 <= delta <= -0.20):
            continue

        results.append({
            "Ticker": ticker,
            "Price": round(price, 2),
            "Strike": strike,
            "Delta": round(delta, 2),
            "Premium": round(snap["premium"], 2),
            "Premium/Strike %": round(snap["premium"] / strike * 100, 2),
            "Bid": snap["bid"],
            "Ask": snap["ask"]
        })

        progress.progress((i + 1) / len(options))

    df = pd.DataFrame(results)

    if not df.empty:
        st.subheader("🔥 Wheel Trades détectés")
        st.dataframe(df.sort_values("Premium/Strike %", ascending=False), use_container_width=True)
    else:
        st.error("⚠️ Aucun trade trouvé")

else:
    st.info("👉 Clique sur Calculer")
