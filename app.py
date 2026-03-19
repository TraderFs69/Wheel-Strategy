import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("⚡ TEA - Wheel Scanner (DELTA MODE)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration", datetime.today())
run_scan = st.sidebar.button("🚀 Calculer")

target_min = -0.30
target_max = -0.20

# -------------------------
# LOAD TICKERS
# -------------------------
@st.cache_data
def load_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    return pd.read_csv(url)["Symbol"].tolist()

tickers = load_sp500()

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


@st.cache_data(ttl=300)
def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()
        res = r.get("results", {})

        greeks = res.get("greeks", {}) or {}
        quote = res.get("last_quote", {}) or {}

        return {
            "delta": greeks.get("delta"),
            "bid": quote.get("bid", 0),
            "ask": quote.get("ask", 0)
        }
    except:
        return None


# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []
    progress = st.progress(0)

    for i, ticker in enumerate(tickers[:50]):  # rapide

        price = get_price(ticker)
        if not price:
            continue

        options = get_options(ticker)

        # 🎯 filtre expiration + puts
        filtered = []

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

            filtered.append(opt)

        # 🎯 tri par distance strike (proche du prix)
        filtered.sort(key=lambda x: abs(price - x.get("strike_price", 0)))

        # 🔥 on prend seulement les 10 meilleurs candidats
        candidates = filtered[:10]

        # 🔥 snapshot seulement sur ceux-là
        for opt in candidates:

            snapshot = get_snapshot(opt.get("ticker"))
            if not snapshot:
                continue

            delta = snapshot.get("delta")

            if delta is None:
                continue

            if not (target_min <= delta <= target_max):
                continue

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": opt.get("strike_price"),
                "Delta": round(delta, 2),
                "Bid": snapshot.get("bid", 0),
                "Ask": snapshot.get("ask", 0),
                "Expiration": opt.get("expiration_date")
            })

        progress.progress((i + 1) / len(tickers[:50]))

    df = pd.DataFrame(results)

    if not df.empty:
        st.subheader("🔥 Options proches delta -0.20 à -0.30")
        st.dataframe(df, use_container_width=True)

    else:
        st.warning("⚠️ Aucun résultat — élargis delta ou date")

else:
    st.info("👉 Clique sur Calculer")
