import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🎯 TEA - Wheel Scanner (Phase 1: Sélection Options)")

# -------------------------
# DATE PICKER
# -------------------------
st.sidebar.header("📅 Expiration")

selected_date = st.sidebar.date_input(
    "Choisir une date d'expiration",
    datetime.today()
)

selected_date = selected_date.strftime("%Y-%m-%d")

# -------------------------
# LOAD TICKERS
# -------------------------
@st.cache_data
def load_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    return pd.read_csv(url)["Symbol"].tolist()

tickers = load_sp500()

# -------------------------
# DATA FUNCTIONS
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

        if "results" not in r:
            return None

        res = r["results"]

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
results = []

progress = st.progress(0)

for i, ticker in enumerate(tickers[:100]):  # limite pour vitesse

    price = get_price(ticker)
    if not price:
        continue

    options = get_options(ticker)

    for opt in options[:100]:

        if opt.get("contract_type") != "put":
            continue

        if opt.get("expiration_date") != selected_date:
            continue

        snapshot = get_snapshot(opt.get("ticker"))
        if not snapshot:
            continue

        delta = snapshot.get("delta")

        if delta is None:
            continue

        # 🎯 FILTRE DELTA
        if not (-0.30 <= delta <= -0.20):
            continue

        strike = opt.get("strike_price")

        results.append({
            "Ticker": ticker,
            "Price": round(price, 2),
            "Strike": strike,
            "Delta": round(delta, 2),
            "Bid": snapshot.get("bid", 0),
            "Ask": snapshot.get("ask", 0),
            "Volume": snapshot.get("volume", 0),
            "Expiration": selected_date
        })

    progress.progress((i + 1) / len(tickers[:100]))

# -------------------------
# DISPLAY PAR STOCK
# -------------------------
df = pd.DataFrame(results)

if not df.empty:

    st.subheader("📊 Options trouvées (-0.20 à -0.30 delta)")

    # tri
    df = df.sort_values(["Ticker", "Delta"])

    st.dataframe(df, use_container_width=True)

    # 🔥 regroupé par stock
    st.subheader("📌 Par stock")

    for ticker in df["Ticker"].unique():
        st.markdown(f"### {ticker}")
        st.dataframe(df[df["Ticker"] == ticker], use_container_width=True)

else:
    st.warning("⚠️ Aucune option trouvée pour cette date")

st.caption(f"Options trouvées: {len(df)}")
