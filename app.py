import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from massive import RESTClient

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.title("🔥 TEA - AAPL Wheel (REST API PRO)")

selected_date = st.date_input("Expiration")
run = st.button("Lancer")

# -------------------------
# CLOSE PRICE (EOD)
# -------------------------
def get_close_price():
    try:
        data = client.get_previous_close_agg("AAPL")

        if not data or len(data) == 0:
            return None

        return data[0].close

    except Exception as e:
        st.write(f"Erreur prix: {e}")
        return None

# -------------------------
# OPTIONS LIST
# -------------------------
def get_options():
    try:
        return list(client.list_options_contracts(
            underlying_ticker="AAPL",
            limit=1000
        ))
    except Exception as e:
        st.write(f"Erreur options: {e}")
        return []

# -------------------------
# SNAPSHOT REST (KEY PART)
# -------------------------
def get_snapshot_rest(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/AAPL/{symbol}?apiKey={API_KEY}"
        res = requests.get(url).json()

        if "results" not in res:
            return None

        return res["results"]

    except:
        return None

# -------------------------
# MAIN
# -------------------------
if run:

    price = get_close_price()

    if price is None:
        st.error("❌ Impossible de récupérer le close AAPL")
        st.stop()

    st.success(f"Close AAPL: {round(price, 2)}")

    options = get_options()

    results = []

    for opt in options:

        if opt.contract_type != "put":
            continue

        exp = opt.expiration_date
        opt_date = datetime.strptime(exp, "%Y-%m-%d").date()

        # 🎯 date exacte
        if opt_date != selected_date:
            continue

        strike = opt.strike_price

        # 🎯 distance 3% à 8%
        distance = (price - strike) / price

        if not (0.03 <= distance <= 0.08):
            continue

        symbol = opt.ticker

        data = get_snapshot_rest(symbol)

        if data is None:
            continue

        # -------------------------
        # EXTRACTION EXACTE
        # -------------------------
        day = data.get("day", {})
        greeks = data.get("greeks", {})

        bid = None  # REST snapshot ne donne pas toujours bid/ask
        ask = None

        premium = day.get("close", None)

        delta = greeks.get("delta", None)
        theta = greeks.get("theta", None)
        vega = greeks.get("vega", None)

        # 🔥 DEBUG (match navigateur)
        st.write({
            "symbol": symbol,
            "strike": strike,
            "premium": premium,
            "delta": delta
        })

        if premium is None or delta is None:
            continue

        results.append({
            "Strike": strike,
            "Distance %": round(distance * 100, 2),
            "Premium": premium,
            "Delta": round(delta, 3),
            "Theta": round(theta, 3) if theta else None,
            "Vega": round(vega, 3) if vega else None,
            "Symbol": symbol
        })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun résultat")
    else:
        st.dataframe(df.sort_values("Strike"))
