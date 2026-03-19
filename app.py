import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from massive import RESTClient
import time

API_KEY = st.secrets["POLYGON_API_KEY"]
client = RESTClient(API_KEY)

st.set_page_config(layout="wide")

st.title("🔥 TEA - Wheel Scanner PRO")

# 🔥 MÉMO IMPORTANT
st.warning("⚠️ À utiliser APRÈS la fermeture du marché (16h+) pour des données fiables")

# -------------------------
# PARAMÈTRES UI
# -------------------------
col1, col2, col3 = st.columns(3)

with col1:
    selected_date = st.date_input("Expiration")

with col2:
    max_tickers = st.slider("Nombre de tickers", 20, 200, 80)

with col3:
    min_oi = st.slider("Open Interest min", 0, 2000, 500)

run = st.button("🚀 Lancer le scan")

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
            limit=300
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

    progress = st.progress(0)
    results = []

    for i, ticker in enumerate(tickers):

        progress.progress((i + 1) / len(tickers))

        price = get_close_price(ticker)

        if price is None or price < 20:
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

            # 🔥 distance wheel
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

            # 🔥 PRIX
            premium = day.get("close")
            bid = quote.get("bid")
            ask = quote.get("ask")

            mid = None
            if bid is not None and ask is not None:
                mid = (bid + ask) / 2

            # 🔥 GREEKS
            delta = greeks.get("delta")
            oi = data.get("open_interest", 0)

            if premium is None or delta is None or bid is None:
                continue

            # 🔥 FILTRES
            if not (-0.30 <= delta <= -0.10):
                continue

            if oi < min_oi:
                continue

            # 🔥 METRICS
            dte = (opt_date - datetime.today().date()).days
            if dte <= 0:
                continue

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
                "Mid": round(mid, 2) if mid else None,

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

        # -------------------------
        # 🎨 STYLE VISUEL
        # -------------------------
        def color_score(val):
            if val > 20:
                return "background-color: #00c853; color: white"
            elif val > 10:
                return "background-color: #ffd600"
            else:
                return ""

        def color_return(val):
            if val > 1:
                return "color: #00c853"
            elif val < 0.3:
                return "color: red"
            return ""

        styled_df = df.style\
            .applymap(color_score, subset=["Score"])\
            .applymap(color_return, subset=["Return %"])\
            .format({
                "Return %": "{:.2f}%",
                "Annual %": "{:.2f}%"
            })

        st.subheader("🔥 TOP WHEEL TRADES")
        st.dataframe(styled_df, use_container_width=True)

        # -------------------------
        # 🏆 TOP PICKS
        # -------------------------
        st.subheader("🏆 Top 10 Opportunités")

        top10 = df.head(10)

        for _, row in top10.iterrows():
            st.markdown(f"""
            **{row['Ticker']}** | Strike {row['Strike']}  
            💰 Bid: {row['Bid']} | Premium: {row['Premium']}  
            📊 Delta: {row['Delta']} | OI: {row['OI']}  
            🚀 Return: {row['Return %']}% | Score: {row['Score']}
            """)
