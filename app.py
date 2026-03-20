import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from massive import RESTClient
import time

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner SP500 (NO FILTER MODE)")

st.warning("⚠️ Mode debug : seulement filtre distance (-3% à -8%)")

selected_date = st.date_input("Expiration")
run = st.button("🚀 Lancer")

# -------------------------
# SP500
# -------------------------
@st.cache_data
def get_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    df = pd.read_csv(url)
    return df["Symbol"].tolist()

tickers = get_sp500()

# -------------------------
# CLOSE PRICE
# -------------------------
@st.cache_data(ttl=3600)
def get_close_price(ticker):
    try:
        data = client.get_previous_close_agg(ticker)
        return data[0].close if data else None
    except:
        return None

# -------------------------
# OPTIONS
# -------------------------
@st.cache_data(ttl=3600)
def get_options(ticker):
    try:
        return list(client.list_options_contracts(
            underlying_ticker=ticker,
            limit=500
        ))
    except:
        return []

# -------------------------
# SNAPSHOT REST
# -------------------------
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

            # 🎯 DATE EXACTE (on garde ça)
            if opt_date != selected_date:
                continue

            strike = opt.strike_price

            # 🔥 SEUL FILTRE
            distance = (price - strike) / price

            if not (0.03 <= distance <= 0.08):
                continue

            symbol = opt.ticker

            data = get_snapshot(ticker, symbol)

            time.sleep(0.005)

            if data is None:
                continue

            day = data.get("day", {})
            greeks = data.get("greeks", {})
            quote = data.get("last_quote", {})

            premium = day.get("close")
            bid = quote.get("bid")
            ask = quote.get("ask")

            delta = greeks.get("delta")
            theta = greeks.get("theta")
            vega = greeks.get("vega")

            results.append({
                "Ticker": ticker,
                "Strike": strike,
                "Price": round(price, 2),
                "Distance %": round(distance * 100, 2),

                "Premium": premium,
                "Bid": bid,
                "Ask": ask,

                "Delta": delta,
                "Theta": theta,
                "Vega": vega,

                "Symbol": symbol
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun résultat → problème vient de la DATA ou DATE")
    else:
        st.success(f"{len(df)} options trouvées")

        st.dataframe(df.sort_values(["Ticker", "Strike"]), use_container_width=True)
