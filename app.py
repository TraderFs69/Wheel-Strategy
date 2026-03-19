import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🎯 TEA - Wheel Scanner (Delta Finder)")

# -------------------------
# SIDEBAR
# -------------------------
st.sidebar.header("📅 Paramètres")

selected_date = st.sidebar.date_input(
    "Choisir une date d'expiration",
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
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=1000&apiKey={API_KEY}"
        return requests.get(url).json().get("results", [])
    except:
        return []


@st.cache_data(ttl=300)
def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()

        if "results" not in r or not isinstance(r["results"], dict):
            return None

        res = r["results"]

        greeks = res.get("greeks", {}) or {}
        quote = res.get("last_quote", {}) or {}

        return {
            "delta": greeks.get("delta"),
            "bid": quote.get("bid", 0),
            "ask": quote.get("ask", 0),
            "volume": res.get("day", {}).get("volume", 0)
        }
    except:
        return None


# -------------------------
# SCAN
# -------------------------
if run_scan:

    results = []
    progress = st.progress(0)

    selected_date_str = selected_date.strftime("%Y-%m-%d")

    st.write(f"🔎 Scan pour expiration: {selected_date_str}")

    all_found_dates = set()

    for i, ticker in enumerate(tickers[:100]):

        price = get_price(ticker)
        if not price:
            continue

        options = get_options(ticker)

        for opt in options:

            exp = opt.get("expiration_date")
            if exp:
                all_found_dates.add(exp)

            if opt.get("contract_type") != "put":
                continue

            # 🎯 tolérance date (important)
            try:
                opt_date = datetime.strptime(exp, "%Y-%m-%d").date()
            except:
                continue

            if abs((opt_date - selected_date).days) > 2:
                continue

            snapshot = get_snapshot(opt.get("ticker"))
            if not snapshot:
                continue

            delta = snapshot.get("delta")

            if delta is None:
                continue

            # 🎯 filtre delta
            if not (-0.30 <= delta <= -0.20):
                continue

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Strike": opt.get("strike_price"),
                "Delta": round(delta, 2),
                "Bid": snapshot.get("bid", 0),
                "Ask": snapshot.get("ask", 0),
                "Volume": snapshot.get("volume", 0),
                "Expiration": exp
            })

        progress.progress((i + 1) / len(tickers[:100]))

    # -------------------------
    # DEBUG EXPIRATIONS
    # -------------------------
    st.subheader("📅 Expirations disponibles (debug)")
    st.write(sorted(list(all_found_dates))[:20])

    # -------------------------
    # DISPLAY
    # -------------------------
    df = pd.DataFrame(results)

    if not df.empty:

        df = df.sort_values(["Ticker", "Delta"])

        st.subheader("📊 Options trouvées (-0.20 à -0.30 delta)")
        st.dataframe(df, use_container_width=True)

        st.subheader("📌 Par stock")

        for ticker in df["Ticker"].unique():
            st.markdown(f"### {ticker}")
            st.dataframe(df[df["Ticker"] == ticker], use_container_width=True)

    else:
        st.warning("⚠️ Aucune option trouvée — vérifier debug expirations")

    st.caption(f"Options trouvées: {len(df)}")

else:
    st.info("👉 Choisis une date puis clique sur Calculer")
