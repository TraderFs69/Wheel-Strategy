import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from massive import RESTClient
import time

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (EV FIXED)")

st.warning("⚠️ À utiliser après la fermeture du marché (EOD)")

# -------------------------
# UI
# -------------------------
col1, col2 = st.columns(2)

with col1:
    selected_date = st.date_input("Expiration")

with col2:
    max_tickers = st.slider("Tickers scannés", 20, 500, 150)

run = st.button("🚀 Lancer scan")

# -------------------------
# SP500
# -------------------------
@st.cache_data
def get_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    df = pd.read_csv(url)
    return df["Symbol"].tolist()

tickers = get_sp500()[:max_tickers]

# -------------------------
# DATA
# -------------------------
@st.cache_data(ttl=3600)
def get_close_price(ticker):
    try:
        data = client.get_previous_close_agg(ticker)
        return data[0].close if data else None
    except:
        return None

@st.cache_data(ttl=3600)
def get_options(ticker):
    try:
        return list(client.list_options_contracts(
            underlying_ticker=ticker,
            limit=500
        ))
    except:
        return []

@st.cache_data(ttl=600)
def get_snapshot(ticker, symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{ticker}/{symbol}?apiKey={API_KEY}"
        res = requests.get(url).json()
        return res.get("results", None)
    except:
        return None

# -------------------------
# MAIN
# -------------------------
if run:

    results = []
    progress = st.progress(0)

    for i, ticker in enumerate(tickers):

        progress.progress((i + 1) / len(tickers))

        price = get_close_price(ticker)
        if price is None:
            continue

        options = get_options(ticker)

        for opt in options:

            if opt.contract_type != "put":
                continue

            opt_date = datetime.strptime(opt.expiration_date, "%Y-%m-%d").date()

            if opt_date != selected_date:
                continue

            strike = opt.strike_price

            # 🎯 seul filtre
            distance = (price - strike) / price
            if not (0.03 <= distance <= 0.08):
                continue

            symbol = opt.ticker

            data = get_snapshot(ticker, symbol)
            if data is None:
                continue

            day = data.get("day", {})
            greeks = data.get("greeks", {})
            quote = data.get("last_quote", {})

            premium = day.get("close")
            bid = quote.get("bid")
            ask = quote.get("ask")

            delta = greeks.get("delta")

            # 🔥 FIX CRITIQUE
            if bid is None:
                continue

            if delta is None:
                delta = -0.2  # fallback réaliste

            # -------------------------
            # EV CALCULATION FIXED
            # -------------------------
            dte = (opt_date - datetime.today().date()).days
            if dte <= 0:
                continue

            prob_itm = abs(delta)
            prob_otm = 1 - prob_itm

            gain = bid
            loss = max(0, strike - price)  # 🔥 FIX MAJEUR

            EV = (prob_otm * gain) - (prob_itm * loss)
            annual_ev = EV * (365 / dte)

            results.append({
                "Ticker": ticker,
                "Strike": strike,
                "Price": round(price, 2),
                "Distance %": round(distance * 100, 2),

                "Premium": premium,
                "Bid": bid,
                "Ask": ask,

                "Delta": round(delta, 3),

                "EV": round(EV, 2),
                "EV Annual": round(annual_ev, 2),
                "DTE": dte
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
    else:
        df = df.sort_values("EV Annual", ascending=False)

        st.subheader("🔥 TOP EV TRADES")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 Top 10")

        for _, row in df.head(10).iterrows():
            st.markdown(f"""
            **{row['Ticker']}** | Strike {row['Strike']}  
            💰 Bid: {row['Bid']}  
            📊 Delta: {row['Delta']}  
            📈 EV: {row['EV']}  
            🚀 EV Annual: {row['EV Annual']}
            """)
