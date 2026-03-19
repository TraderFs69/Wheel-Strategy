import streamlit as st
import pandas as pd
from datetime import datetime
from massive import RESTClient

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.title("🔥 TEA - AAPL Wheel (EOD)")

selected_date = st.date_input("Expiration")
run = st.button("Lancer")

# -------------------------
# PRIX CLOSE (EOD)
# -------------------------
def get_close_price():
    try:
        data = client.get_previous_close_agg("AAPL")

        if not data or len(data) == 0:
            return None

        return data[0].close  # 🔥 FIX IMPORTANT

    except Exception as e:
        st.write(f"Erreur prix: {e}")
        return None

# -------------------------
# OPTIONS
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
# MAIN
# -------------------------
if run:

    price = get_close_price()

    if price is None:
        st.error("❌ Impossible de récupérer le close AAPL")
        st.stop()

    st.success(f"Close AAPL: {round(price, 2)}")

    options = get_options()

    if not options:
        st.error("❌ Aucune option retournée")
        st.stop()

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

        # 🔥 DISTANCE 3% à 8% (comme tu veux)
        distance = (price - strike) / price

        if not (0.03 <= distance <= 0.08):
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
        st.error("⚠️ Aucun résultat (date ou strikes trop restrictifs)")
    else:
        st.dataframe(df.sort_values("Strike"))
