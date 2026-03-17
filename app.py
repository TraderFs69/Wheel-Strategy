import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner PRO")

# -------------------------
# HEADER
# -------------------------
col1, col2, col3 = st.columns(3)
col1.metric("Market", "OPEN")
col2.metric("Scanner", "ACTIVE")
col3.metric("Mode", "Wheel Strategy")

# -------------------------
# SIDEBAR FILTERS
# -------------------------
st.sidebar.header("⚙️ Filters")

min_return = st.sidebar.slider("Min Annual Return %", 5, 50, 15)
min_safety = st.sidebar.slider("Min Distance OTM %", 2, 15, 5)
min_oi = st.sidebar.slider("Min Open Interest", 0, 2000, 200)

# -------------------------
# LOAD TICKERS (FIXED)
# -------------------------
@st.cache_data
def load_sp500():
    try:
        # 🔥 TON FICHIER XLSX
        df = pd.read_excel("sp500_constituents.xlsx")

        # Ajuste si colonne différente
        if "Symbol" in df.columns:
            return df["Symbol"].tolist()
        elif "symbol" in df.columns:
            return df["symbol"].tolist()
        else:
            st.error("Colonne 'Symbol' non trouvée dans le fichier")
            return []

    except:
        # 🔥 FALLBACK ONLINE
        url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
        df = pd.read_csv(url)
        return df["Symbol"].tolist()

tickers = load_sp500()

# -------------------------
# DATA FUNCTIONS
# -------------------------
@st.cache_data(ttl=300)
def get_price(ticker):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
    r = requests.get(url).json()
    return r["results"][0]["c"] if "results" in r else None

@st.cache_data(ttl=300)
def get_options(ticker):
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?apiKey={API_KEY}"
    r = requests.get(url).json()
    return r.get("results", [])

def approx_delta(price, strike):
    dist = (price - strike) / price
    if dist < 0.03:
        return -0.35
    elif dist < 0.06:
        return -0.25
    elif dist < 0.10:
        return -0.15
    else:
        return -0.10

def compute_metrics(price, strike, premium, dte, oi):
    annual_return = (premium / strike) * (365 / dte)
    safety = (price - strike) / price
    liquidity = min(oi / 1000, 1)

    score = (
        annual_return * 0.4 +
        safety * 0.3 +
        liquidity * 0.2 +
        0.1
    )

    return annual_return, safety, score

# -------------------------
# MAIN SCAN
# -------------------------
results = []

progress = st.progress(0)

for i, ticker in enumerate(tickers):

    price = get_price(ticker)
    if not price:
        continue

    options = get_options(ticker)

    for opt in options:
        if opt["details"]["contract_type"] != "put":
            continue

        strike = opt["details"]["strike_price"]
        expiration = datetime.strptime(opt["details"]["expiration_date"], "%Y-%m-%d")
        dte = (expiration - datetime.today()).days

        if dte < 20 or dte > 60:
            continue

        bid = opt["last_quote"]["bid"]
        ask = opt["last_quote"]["ask"]

        if bid is None or ask is None:
            continue

        premium = (bid + ask) / 2
        oi = opt.get("open_interest", 0)

        if oi < min_oi:
            continue

        delta = approx_delta(price, strike)

        if not (-0.35 <= delta <= -0.15):
            continue

        annual_return, safety, score = compute_metrics(price, strike, premium, dte, oi)

        if annual_return * 100 < min_return:
            continue

        if safety * 100 < min_safety:
            continue

        results.append({
            "Ticker": ticker,
            "Price": round(price, 2),
            "Strike": strike,
            "Premium": round(premium, 2),
            "DTE": dte,
            "Annual %": round(annual_return * 100, 2),
            "Safety %": round(safety * 100, 2),
            "Score": round(score, 2)
        })

    progress.progress((i + 1) / len(tickers))

# -------------------------
# DISPLAY
# -------------------------
df = pd.DataFrame(results)

if not df.empty:
    df = df.sort_values("Score", ascending=False)

    colA, colB = st.columns([3,1])

    with colA:
        st.subheader("📊 Wheel Opportunities")
        st.dataframe(df, use_container_width=True)

    with colB:
        st.subheader("🏆 Top 5")
        st.write(df.head(5))

else:
    st.warning("No trades found")
