import streamlit as st
import pandas as pd
from datetime import datetime
from massive import RESTClient

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.title("🔥 TEA - AAPL Wheel Debug")

selected_date = st.date_input("Expiration")
run = st.button("Lancer")

# -------------------------
# GET UNDERLYING PRICE (FIABLE)
# -------------------------
def get_underlying_price():
    try:
        trade = client.get_last_trade("AAPL")
        return trade.price
    except:
        return None

# -------------------------
# GET OPTIONS
# -------------------------
def get_options():
    try:
        return list(client.list_options_contracts(
            underlying_ticker="AAPL",
            limit=1000
        ))
    except:
        return []

# -------------------------
# MAIN
# -------------------------
if run:

    price = get_underlying_price()

    if price is None:
        st.error("Erreur prix AAPL")
        st.stop()

    st.write(f"Prix AAPL: {price}")

    options = get_options()

    results = []

    for opt in options:

        if opt.contract_type != "put":
            continue

        exp = opt.expiration_date
        opt_date = datetime.strptime(exp, "%Y-%m-%d").date()

        # 🔥 date EXACTE (comme tu veux)
        if opt_date != selected_date:
            continue

        strike = opt.strike_price

        # 🔥 DISTANCE 3% à 10%
        distance = (price - strike) / price

        if not (0.03 <= distance <= 0.10):
            continue

        symbol = opt.ticker

        try:
            snap = client.get_snapshot_option("AAPL", symbol)
        except:
            continue

        # -------------------------
        # DATA
        # -------------------------
        quote = snap.last_quote if snap.last_quote else None
        greeks = snap.greeks if snap.greeks else None

        bid = getattr(quote, "bid", None) if quote else None
        ask = getattr(quote, "ask", None) if quote else None

        delta = getattr(greeks, "delta", None) if greeks else None
        theta = getattr(greeks, "theta", None) if greeks else None
        vega = getattr(greeks, "vega", None) if greeks else None

        results.append({
            "Strike": strike,
            "Distance %": round(distance * 100, 2),
            "Bid": bid,
            "Ask": ask,
            "Delta": delta,
            "Theta": theta,
            "Vega": vega,
            "Symbol": symbol
        })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun résultat")
    else:
        st.dataframe(df.sort_values("Strike"))
