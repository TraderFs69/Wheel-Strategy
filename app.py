import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("⚡ TEA - Wheel Scanner (Distance = Delta proxy)")

# -------------------------
# INPUT
# -------------------------
st.sidebar.header("📅 Paramètres")

selected_date = st.sidebar.date_input(
    "Choisir une expiration (vendredi recommandé)",
    datetime.today()
)

run_scan = st.sidebar.button("🚀 Calculer")

# -------------------------
# LOAD TICKERS
# -------------------------
@st.cache_data
def load_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    return pd.read_csv(url)["Symbol"].tolist()

tickers = load_sp500()

# -------------------------
# DATA FUNCTIONS
# -------------------------
@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
        return requests.get(url).json()["results"][0]["c"]
    except:
        return None


@st.cache_data(ttl=300)
def get_options(ticker):
    try:
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
        return requests.get(url).json().get("results", [])
    except:
        return []

# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []
    progress = st.progress(0)

    selected_date_str = selected_date.strftime("%Y-%m-%d")

    st.write(f"🔎 Scan pour expiration: {selected_date_str}")

    for i, ticker in enumerate(tickers[:50]):  # rapide

        price = get_price(ticker)
        if not price:
            continue

        options = get_options(ticker)

        for opt in options:

            # seulement puts
            if opt.get("contract_type") != "put":
                continue

            exp = opt.get("expiration_date")

            if not exp:
                continue

            # tolérance date (important)
            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            if abs((opt_date - selected_date).days) > 2:
                continue

            strike = opt.get("strike_price")

            if not strike:
                continue

            # seulement OTM
            if strike >= price:
                continue

            # 🎯 distance = proxy delta
            distance = (price - strike) / price

            # 🔥 ZONE DELTA approx (-0.20 à -0.30)
            if 0.03 <= distance <= 0.10:

                results.append({
                    "Ticker": ticker,
                    "Price": round(price, 2),
                    "Strike": strike,
                    "Distance %": round(distance * 100, 2),
                    "Expiration": exp
                })

        progress.progress((i + 1) / len(tickers[:50]))

    df = pd.DataFrame(results)

    if not df.empty:

        df = df.sort_values(["Ticker", "Strike"])

        st.subheader("🔥 Options dans la zone delta (-0.20 à -0.30 approx)")
        st.dataframe(df, use_container_width=True)

        # regroupé par stock
        st.subheader("📌 Par stock")
        for ticker in df["Ticker"].unique():
            st.markdown(f"### {ticker}")
            st.dataframe(df[df["Ticker"] == ticker], use_container_width=True)

    else:
        st.error("⚠️ Aucun résultat — change la date (vendredi)")

    st.caption(f"Options trouvées: {len(df)}")

else:
    st.info("👉 Choisis une date puis clique sur Calculer")
