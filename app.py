import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from massive import RESTClient
import time

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.title("🔥 TEA - Wheel Scanner SP500 (PRO)")

selected_date = st.date_input("Expiration")
run = st.button("Lancer")

# -------------------------
# 🔥 SP500 LIST (simple)
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
def get_close_price(ticker):
    try:
        data = client.get_previous_close_agg(ticker)
        if not data or len(data) == 0:
            return None
        return data[0].close
    except:
        return None

# -------------------------
# OPTIONS
# -------------------------
def get_options(ticker):
    try:
        return list(client.list_options_contracts(
            underlying_ticker=ticker,
            limit=500  # 🔥 réduit pour vitesse
        ))
    except:
        return []

# -------------------------
# SNAPSHOT REST
# -------------------------
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

    # 🔥 LIMITER POUR TEST
    tickers_sample = tickers[:50]  # 👉 augmente progressivement

    for ticker in tickers_sample:

        price = get_close_price(ticker)

        if price is None or price < 5:
            continue

        # 🔥 PRÉ-FILTRE (important)
        # élimine penny / junk
        if price < 20:
            continue

        options = get_options(ticker)

        for opt in options:

            if opt.contract_type != "put":
                continue

            exp = opt.expiration_date
            opt_date = datetime.strptime(exp, "%Y-%m-%d").date()

            if opt_date != selected_date:
                continue

            strike = opt.strike_price

            # 🔥 PRÉ-FILTRE CRITIQUE (AVANT API)
            distance = (price - strike) / price
            if not (0.03 <= distance <= 0.08):
                continue

            symbol = opt.ticker

            data = get_snapshot(ticker, symbol)

            time.sleep(0.01)

            if data is None:
                continue

            day = data.get("day", {})
            greeks = data.get("greeks", {})

            premium = day.get("close", None)
            delta = greeks.get("delta", None)
            oi = data.get("open_interest", 0)

            if premium is None or delta is None:
                continue

            # 🔥 FILTRES PRO
            if not (-0.30 <= delta <= -0.10):
                continue

            if oi < 500:
                continue

            # -------------------------
            # METRICS
            # -------------------------
            return_pct = premium / strike * 100

            dte = (opt_date - datetime.today().date()).days
            if dte <= 0:
                continue

            annual_return = return_pct * (365 / dte)
            score = annual_return * abs(delta)

            results.append({
                "Ticker": ticker,
                "Strike": strike,
                "Price": round(price, 2),
                "Distance %": round(distance * 100, 2),
                "Premium": premium,
                "Delta": round(delta, 3),
                "OI": oi,
                "Return %": round(return_pct, 2),
                "Annual %": round(annual_return, 2),
                "Score": round(score, 2)
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
    else:
        df = df.sort_values("Score", ascending=False)

        st.subheader("🔥 TOP WHEEL TRADES SP500")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 Top 10")
        st.write(df.head(10))
