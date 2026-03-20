import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from massive import RESTClient
import time

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner SP500 (LIVE STABLE)")

st.warning("⚠️ Mode LIVE avec fallback → prix toujours disponible")

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
# LIVE PRICE (FIXED)
# -------------------------
@st.cache_data(ttl=60)
def get_live_price(ticker):
    try:
        quote = client.get_last_quote(ticker)

        if quote and quote.bid is not None and quote.ask is not None:
            price = (quote.bid + quote.ask) / 2
            if price > 0:
                return price

        trade = client.get_last_trade(ticker)
        if trade and hasattr(trade, "price") and trade.price > 0:
            return trade.price

        # 🔥 fallback CLOSE (très important)
        data = client.get_previous_close_agg(ticker)
        if data and len(data) > 0:
            return data[0].close

        return None

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

        price = get_live_price(ticker)

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

            # 🔥 FIX : filtre légèrement élargi pour live
            distance = (price - strike) / price

            if not (0.02 <= distance <= 0.10):
                continue

            symbol = opt.ticker

            data = get_snapshot(ticker, symbol)

            time.sleep(0.005)

            if data is None:
                continue

            day = data.get("day", {})
            greeks = data.get("greeks", {})

            premium = day.get("close")

            delta = greeks.get("delta")
            theta = greeks.get("theta")
            vega = greeks.get("vega")

            # 🔥 SCORE
            score = None
            if premium is not None and price:
                score = (premium / price) * 100

            results.append({
                "Ticker": ticker,
                "Strike": strike,
                "Price": round(price, 2),
                "Distance %": round(distance * 100, 2),

                "Premium": premium,
                "Score %": round(score, 2) if score else None,

                "Delta": delta,
                "Theta": theta,
                "Vega": vega,

                "Symbol": symbol
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun résultat → probablement la date sélectionnée")
    else:
        st.success(f"{len(df)} options trouvées")

        st.dataframe(df.sort_values(["Ticker", "Strike"]), use_container_width=True)
