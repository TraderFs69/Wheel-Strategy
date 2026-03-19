import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from massive import RESTClient
import time

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner SP500 FULL")

st.warning("⚠️ Scanner complet SP500 → peut prendre plusieurs minutes (run après 16h)")

# -------------------------
# UI
# -------------------------
col1, col2, col3 = st.columns(3)

with col1:
    selected_date = st.date_input("Expiration")

with col2:
    batch_size = st.slider("Batch size", 20, 150, 80)

with col3:
    min_oi = st.slider("OI minimum", 0, 2000, 500)

run = st.button("🚀 Lancer FULL SCAN")

# -------------------------
# SP500 LIST
# -------------------------
@st.cache_data
def get_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    df = pd.read_csv(url)
    return df["Symbol"].tolist()

tickers = get_sp500()

# -------------------------
# CACHE
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
            limit=200
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
    status = st.empty()

    total = len(tickers)

    for i in range(0, total, batch_size):

        batch = tickers[i:i + batch_size]

        status.write(f"Batch {i} → {i+len(batch)}")

        for ticker in batch:

            price = get_close_price(ticker)
            if price is None or price < 20:
                continue

            options = get_options(ticker)

            for opt in options:

                if opt.contract_type != "put":
                    continue

                opt_date = datetime.strptime(opt.expiration_date, "%Y-%m-%d").date()

                if opt_date != selected_date:
                    continue

                strike = opt.strike_price

                # 🔥 pré-filtre
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

                if premium is None or bid is None:
                    continue

                delta = greeks.get("delta")
                oi = data.get("open_interest", 0)

                if delta is None:
                    continue

                # 🔥 filtres
                if not (-0.30 <= delta <= -0.10):
                    continue

                if oi < min_oi:
                    continue

                dte = (opt_date - datetime.today().date()).days
                if dte <= 0:
                    continue

                # 🔥 metrics
                return_pct = bid / strike * 100
                annual_return = return_pct * (365 / dte)
                score = annual_return * abs(delta)

                results.append({
                    "Ticker": ticker,
                    "Strike": strike,
                    "Price": round(price, 2),
                    "Distance %": round(distance * 100, 2),

                    "Premium": premium,
                    "Bid": bid,
                    "Ask": ask,

                    "Delta": round(delta, 3),
                    "OI": oi,

                    "Return %": round(return_pct, 2),
                    "Annual %": round(annual_return, 2),
                    "Score": round(score, 2)
                })

        # 🔥 update progress
        progress.progress(min((i + batch_size) / total, 1.0))

        # 🔥 pause anti rate limit
        time.sleep(1)

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
    else:
        df = df.sort_values("Score", ascending=False)

        st.subheader("🔥 TOP SP500 WHEEL TRADES")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 Top 20")
        st.write(df.head(20))
