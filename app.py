import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("⚡ TEA - Wheel Scanner (DELTA SMART)")

# -------------------------
# INPUT
# -------------------------
selected_date = st.sidebar.date_input("Expiration", datetime.today())
run_scan = st.sidebar.button("🚀 Calculer")

# Delta cible
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
            "ask": quote.get("ask", 0),
            "volume": res.get("day", {}).get("volume", 0)
        }
    except:
        return None


# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []
    progress = st.progress(0)

    for i, ticker in enumerate(tickers[:50]):  # limite vitesse

        price = get_price(ticker)
        if not price:
            continue

        options = get_options(ticker)

        filtered = []

        # 🎯 PRÉ-FILTRE INTELLIGENT
        for opt in options:

            if opt.get("contract_type") != "put":
                continue

            exp = opt.get("expiration_date")

            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            # tolérance date
            if abs((opt_date - selected_date).days) > 2:
                continue

            strike = opt.get("strike_price")

            if not strike:
                continue

            # seulement OTM
            if strike >= price:
                continue

            distance = (price - strike) / price

            # 🔥 ZONE DELTA CIBLE
            if distance < 0.03 or distance > 0.12:
                continue

            filtered.append(opt)

        # 🔥 tri par proximité logique
        filtered.sort(key=lambda x: abs(price - x.get("strike_price")))

        # 🔥 limiter pour performance
        candidates = filtered[:20]

        # 🎯 SNAPSHOT UNIQUEMENT ICI
        for opt in candidates:

            snapshot = get_snapshot(opt.get("ticker"))
            if not snapshot:
                continue

            delta = snapshot.get("delta")

            if delta is None:
                continue

            if not (target_min <= delta <= target_max):
                continue

            bid = snapshot.get("bid", 0)
            ask = snapshot.get("ask", 0)
            volume = snapshot.get("volume", 0)

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": opt.get("strike_price"),
                "Delta": round(delta, 2),
                "Bid": bid,
                "Ask": ask,
                "Volume": volume,
                "Expiration": opt.get("expiration_date")
            })

        progress.progress((i + 1) / len(tickers[:50]))

    df = pd.DataFrame(results)

    if not df.empty:
        st.subheader("🔥 Options delta -0.20 à -0.30")
        st.dataframe(df, use_container_width=True)

        st.subheader("📌 Par stock")
        for ticker in df["Ticker"].unique():
            st.markdown(f"### {ticker}")
            st.dataframe(df[df["Ticker"] == ticker], use_container_width=True)

    else:
        st.warning("⚠️ Aucun résultat — essaie autre date ou élargir zone")

    st.caption(f"Options trouvées: {len(df)}")

else:
    st.info("👉 Clique sur Calculer")
