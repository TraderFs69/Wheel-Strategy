import streamlit as st
import pandas as pd
import requests
from datetime import datetime

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner PRO MAX")

# -------------------------
# MODE SELECTION
# -------------------------
st.sidebar.header("🎯 Mode")

mode = st.sidebar.selectbox(
    "Choix du style",
    ["Conservateur", "Neutre", "Agressif"]
)

# -------------------------
# MODE LOGIC
# -------------------------
if mode == "Conservateur":
    min_return = 3
    min_safety = 3
    min_pop = 75
    delta_range = (-0.25, -0.10)

elif mode == "Neutre":
    min_return = 5
    min_safety = 2
    min_pop = 65
    delta_range = (-0.30, -0.10)

else:  # Agressif
    min_return = 8
    min_safety = 1
    min_pop = 55
    delta_range = (-0.40, -0.05)

min_oi = st.sidebar.slider("Min Open Interest", 0, 2000, 20)

# -------------------------
# LOAD TICKERS
# -------------------------
@st.cache_data
def load_sp500():
    try:
        df = pd.read_excel("sp500_constituents.xlsx")
        return df["Symbol"].tolist()
    except:
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
def get_options_reference(ticker):
    url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=100&apiKey={API_KEY}"
    r = requests.get(url).json()
    return r.get("results", [])


@st.cache_data(ttl=300)
def get_option_snapshot(option_ticker):
    url = f"https://api.polygon.io/v3/snapshot/options/{option_ticker}?apiKey={API_KEY}"
    r = requests.get(url).json()

    if "results" not in r:
        return None

    res = r["results"]

    try:
        greeks = res.get("greeks", {})
        last_quote = res.get("last_quote", {})

        bid = last_quote.get("bid", 0)
        ask = last_quote.get("ask", 0)
        mid = (bid + ask) / 2 if bid and ask else bid or ask or 0

        return {
            "delta": greeks.get("delta"),
            "theta": greeks.get("theta"),
            "iv": res.get("implied_volatility"),
            "mid": mid,
            "volume": res.get("day", {}).get("volume", 0)
        }

    except:
        return None


# -------------------------
# METRICS
# -------------------------
def compute_metrics(price, strike, premium, dte, oi, delta, theta, iv, volume):

    if not premium or premium == 0 or delta is None:
        return None

    annual_return = (premium / strike) * (365 / dte)
    safety = (price - strike) / price
    pop = 1 - abs(delta)
    theta_income = abs(theta) if theta else 0

    liquidity = min((oi + volume) / 2000, 1)
    iv_score = min(iv / 0.5, 1) if iv else 0

    score = (
        annual_return * 0.30 +
        safety * 0.20 +
        pop * 0.20 +
        theta_income * 0.10 +
        iv_score * 0.10 +
        liquidity * 0.10
    )

    return annual_return, safety, pop, score


# -------------------------
# MAIN SCAN
# -------------------------
results = []
progress = st.progress(0)

debug = {
    "options": 0,
    "valid_delta": 0,
    "valid_metrics": 0
}

for i, ticker in enumerate(tickers[:150]):

    price = get_price(ticker)
    if not price:
        continue

    options = get_options_reference(ticker)
    if not options:
        continue

    for opt in options:

        if opt.get("contract_type") != "put":
            continue

        strike = opt.get("strike_price")
        expiration = opt.get("expiration_date")
        option_symbol = opt.get("ticker")

        if not strike or not expiration or not option_symbol:
            continue

        expiration_dt = datetime.strptime(expiration, "%Y-%m-%d")
        dte = (expiration_dt - datetime.today()).days

        if dte < 20 or dte > 60:
            continue

        oi = opt.get("open_interest", 0)
        if oi < min_oi:
            continue

        snapshot = get_option_snapshot(option_symbol)
        if not snapshot:
            continue

        debug["options"] += 1

        delta = snapshot.get("delta")
        theta = snapshot.get("theta", 0)
        iv = snapshot.get("iv", 0.3)
        premium = snapshot.get("mid", 0)
        volume = snapshot.get("volume", 0)

        # fallback premium
        if not premium or premium == 0:
            premium = abs(price - strike) * 0.05

        if delta is None:
            continue

        if not (delta_range[0] <= delta <= delta_range[1]):
            continue

        debug["valid_delta"] += 1

        metrics = compute_metrics(price, strike, premium, dte, oi, delta, theta, iv, volume)
        if not metrics:
            continue

        annual_return, safety, pop, score = metrics

        if annual_return * 100 < min_return:
            continue

        if safety * 100 < min_safety:
            continue

        if pop * 100 < min_pop:
            continue

        debug["valid_metrics"] += 1

        results.append({
            "Ticker": ticker,
            "Price": round(price, 2),
            "Strike": strike,
            "Premium": round(premium, 2),
            "DTE": dte,
            "Annual %": round(annual_return * 100, 2),
            "Safety %": round(safety * 100, 2),
            "POP %": round(pop * 100, 2),
            "Delta": round(delta, 2),
            "Theta": round(theta, 3) if theta else None,
            "IV": round(iv, 2) if iv else None,
            "Volume": volume,
            "OI": oi,
            "Score": round(score, 3)
        })

    progress.progress((i + 1) / len(tickers[:150]))

# -------------------------
# DISPLAY
# -------------------------
df = pd.DataFrame(results)

if not df.empty:
    df = df.sort_values("Score", ascending=False)

    colA, colB = st.columns([3,1])

    with colA:
        st.subheader(f"📊 Opportunities ({mode})")
        st.dataframe(df, use_container_width=True)

    with colB:
        st.subheader("🏆 Top 5")
        st.write(df.head(5))

else:
    st.warning("⚠️ Aucun trade trouvé — normal selon le mode")

# -------------------------
# DEBUG
# -------------------------
st.write("🔍 Debug", debug)
st.caption(f"Tickers scanned: {len(tickers[:150])}")
