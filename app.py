import streamlit as st
import pandas as pd
import math
import time
from datetime import datetime
from massive import RESTClient

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner (MASSIVE SDK FINAL)")

selected_date = st.sidebar.date_input("Expiration")
run_scan = st.sidebar.button("🚀 Lancer")

tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]

# -------------------------
# BLACK-SCHOLES
# -------------------------
def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def norm_pdf(x):
    return (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x**2)

def greeks_put(S, K, T, r, sigma):
    if T <= 0:
        return 0, 0, 0

    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    delta = norm_cdf(d1) - 1
    theta = (-S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))) + (r * K * math.exp(-r * T) * norm_cdf(-d2))
    vega = S * norm_pdf(d1) * math.sqrt(T)

    return delta, theta, vega

# -------------------------
# PRICE (FIX ICI)
# -------------------------
def get_price(ticker):
    try:
        data = client.get_previous_close_agg(ticker)

        if not data or len(data) == 0:
            return None

        return data[0].close  # 🔥 FIX

    except Exception as e:
        st.write(f"Erreur prix {ticker}: {e}")
        return None

# -------------------------
# OPTIONS
# -------------------------
def get_options(ticker):
    try:
        return list(client.list_options_contracts(underlying_ticker=ticker, limit=500))
    except Exception as e:
        st.write(f"Erreur options {ticker}: {e}")
        return []

# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []

    for ticker in tickers:

        price = get_price(ticker)
        if not price:
            continue

        options = get_options(ticker)

        if not options:
            st.write(f"Aucune option pour {ticker}")
            continue

        for opt in options:

            if opt.contract_type != "put":
                continue

            exp = opt.expiration_date
            opt_date = datetime.strptime(exp, "%Y-%m-%d").date()

            if opt_date != selected_date:
                continue

            strike = opt.strike_price

            if strike >= price:
                continue

            distance = (price - strike) / price

            if not (0.01 <= distance <= 0.15):
                continue

            dte = (opt_date - datetime.today().date()).days
            if dte <= 0:
                continue

            T = dte / 365

            # fallback greeks
            delta_calc, theta_calc, vega_calc = greeks_put(price, strike, T, 0.04, 0.30)

            # 🔥 UTILISER LE BON SYMBOL
            symbol = opt.ticker

            try:
                st.write(f"DEBUG → {ticker} | {symbol}")
                snap = client.get_snapshot_option(ticker, symbol)
            except Exception as e:
                st.write(f"Erreur snapshot {symbol}: {e}")
                continue

            time.sleep(0.1)

            greeks = snap.greeks if snap.greeks else None
            last = snap.last_trade if snap.last_trade else None
            quote = snap.last_quote if snap.last_quote else None

            delta_real = getattr(greeks, "delta", None) if greeks else None
            theta_real = getattr(greeks, "theta", None) if greeks else None
            vega_real = getattr(greeks, "vega", None) if greeks else None

            delta = delta_real if delta_real is not None else delta_calc
            theta = theta_real if theta_real is not None else theta_calc
            vega = vega_real if vega_real is not None else vega_calc

            bid = getattr(quote, "bid", None) if quote else None
            ask = getattr(quote, "ask", None) if quote else None
            last_price = getattr(last, "price", None) if last else None

            if bid and ask:
                premium = (bid + ask) / 2
            elif last_price:
                premium = last_price
            else:
                intrinsic = max(0, strike - price)
                extrinsic = price * 0.02 * math.sqrt(T)
                premium = intrinsic + extrinsic

            results.append({
                "Ticker": ticker,
                "Expiration": exp,
                "Strike": strike,
                "Price": price,
                "Delta": round(delta, 3),
                "Theta": round(theta, 2),
                "Vega": round(vega, 2),
                "Premium": round(premium, 2),
                "Premium/Strike %": round(premium / strike * 100, 2),
                "Distance %": round(distance * 100, 2)
            })

    df = pd.DataFrame(results)

    if df.empty:
        st.error("⚠️ Aucun trade trouvé")
    else:
        df = df.sort_values("Premium/Strike %", ascending=False)

        st.subheader("🔥 Résultats")
        st.dataframe(df, use_container_width=True)

        st.subheader("🏆 Top 10")
        st.write(df.head(10))
