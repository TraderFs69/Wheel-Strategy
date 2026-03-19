import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("⚡ TEA - Wheel Scanner (Analyse complète)")

# -------------------------
# INPUT
# -------------------------
st.sidebar.header("📅 Paramètres")

selected_date = st.sidebar.date_input(
    "Choisir une expiration (vendredi recommandé)",
    datetime.today()
)

run_scan = st.sidebar.button("🚀 Calculer")

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

        res = r.get("results", {})

        greeks = res.get("greeks", {}) or {}
        quote = res.get("last_quote", {}) or {}

        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)

        premium = (bid + ask) / 2 if bid and ask else bid or 0

        return {
            "delta": greeks.get("delta"),
            "bid": bid,
            "ask": ask,
            "premium": premium
        }
    except:
        return None


# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []
    progress = st.progress(0)

    for i, ticker in enumerate(tickers[:50]):

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

            # 🎯 zone delta approx
            distance = (price - strike) / price

            if 0.03 <= distance <= 0.10:

                results.append({
                    "Ticker": ticker,
                    "OptionSymbol": opt.get("ticker"),
                    "Price": round(price, 2),
                    "Strike": strike,
                    "Distance %": round(distance * 100, 2),
                    "Expiration": exp
                })

        progress.progress((i + 1) / len(tickers[:50]))

    df = pd.DataFrame(results)

    # -------------------------
    # AJOUT DELTA + PREMIUM
    # -------------------------
    if not df.empty:

        st.subheader("⏳ Enrichissement (delta + premium)...")

        deltas = []
        premiums = []
        bids = []
        asks = []

        progress2 = st.progress(0)

        for i, row in df.iterrows():
            snap = get_snapshot(row["OptionSymbol"])

            if snap:
                deltas.append(snap["delta"])
                premiums.append(snap["premium"])
                bids.append(snap["bid"])
                asks.append(snap["ask"])
            else:
                deltas.append(None)
                premiums.append(0)
                bids.append(0)
                asks.append(0)

            progress2.progress((i + 1) / len(df))

        df["Delta"] = deltas
        df["Premium"] = premiums
        df["Bid"] = bids
        df["Ask"] = asks

        # nettoyage
        df = df[df["Delta"].notna()]

        # 🎯 METRIQUE CLÉ
        df["Premium/Strike %"] = (df["Premium"] / df["Strike"] * 100).round(2)

        df = df.sort_values(["Ticker", "Delta"])

        # -------------------------
        # DISPLAY
        # -------------------------
        st.subheader("🔥 Analyse Wheel complète")
        st.dataframe(df, use_container_width=True)

        st.subheader("📌 Par stock")
        for ticker in df["Ticker"].unique():
            st.markdown(f"### {ticker}")
            st.dataframe(df[df["Ticker"] == ticker], use_container_width=True)

    else:
        st.error("⚠️ Aucun résultat — change la date")

    st.caption(f"Options trouvées: {len(df)}")

else:
    st.info("👉 Clique sur Calculer")
