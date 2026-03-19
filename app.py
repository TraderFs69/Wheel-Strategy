import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner SMART")

# -------------------------
# USER INPUT
# -------------------------
st.sidebar.header("🎯 Paramètres")

target_delta = st.sidebar.slider("Delta cible", 0.10, 0.40, 0.20, 0.05)

week_choice = st.sidebar.selectbox(
    "Expiration",
    ["Prochain vendredi", "2e vendredi", "3e vendredi"]
)

min_oi = st.sidebar.slider("Min Open Interest", 0, 2000, 0)

# -------------------------
# DATE
# -------------------------
def get_target_friday(n):
    today = datetime.today()
    friday = today + timedelta((4 - today.weekday()) % 7)
    return friday + timedelta(weeks=n)

week_map = {
    "Prochain vendredi": 0,
    "2e vendredi": 1,
    "3e vendredi": 2
}

target_date = get_target_friday(week_map[week_choice]).date()

# -------------------------
# DATA
# -------------------------
@st.cache_data
def load_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    return pd.read_csv(url)["Symbol"].tolist()

tickers = load_sp500()


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


@st.cache_data(ttl=300)
def get_snapshot(symbol):
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()

        if "results" not in r or not isinstance(r["results"], dict):
            return None

        res = r["results"]

        greeks = res.get("greeks", {}) if isinstance(res.get("greeks"), dict) else {}
        quote = res.get("last_quote", {}) if isinstance(res.get("last_quote"), dict) else {}

        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)

        return {
            "delta": greeks.get("delta"),
            "iv": res.get("implied_volatility"),
            "bid": bid,
            "ask": ask,
            "volume": res.get("day", {}).get("volume", 0) if isinstance(res.get("day"), dict) else 0
        }
    except:
        return None


# -------------------------
# SCAN
# -------------------------
results = []

for ticker in tickers[:100]:

    price = get_price(ticker)
    if not price:
        continue

    options = get_options(ticker)

    for opt in options[:80]:

        if opt.get("contract_type") != "put":
            continue

        strike = opt.get("strike_price")
        expiration = opt.get("expiration_date")

        if not strike or not expiration:
            continue

        exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()

        # 🔥 expiration flexible
        if abs((exp_date - target_date).days) > 5:
            continue

        # 🔥 zone wheel élargie
        distance = (price - strike) / price
        if distance < 0.005 or distance > 0.20:
            continue

        snapshot = get_snapshot(opt.get("ticker"))

        if not snapshot:
            continue

        delta = snapshot.get("delta")
        bid = snapshot.get("bid", 0)
        ask = snapshot.get("ask", 0)
        volume = snapshot.get("volume", 0)
        iv = snapshot.get("iv", 0.30)

        if delta is None:
            continue

        # 🔥 EXECUTION SCORE (pas filtre)
        quality = 0

        if bid > 0:
            quality += 1
        if volume > 0:
            quality += 1
        if ask > 0:
            quality += 1

        # premium réaliste
        premium = (bid + ask) / 2 if bid and ask else bid or 0.01

        oi = opt.get("open_interest", 0)
        if oi < min_oi:
            continue

        dte = (exp_date - datetime.today().date()).days

        annual_return = (premium / strike) * (365 / max(dte, 1))
        pop = 1 - abs(delta)

        # 🔥 SCORE FINAL (intelligent)
        score = (
            annual_return * 0.3 +
            pop * 0.2 +
            iv * 0.2 +
            quality * 0.3
        )

        results.append({
            "Ticker": ticker,
            "Price": round(price,2),
            "Strike": strike,
            "Premium": round(premium,2),
            "Bid": bid,
            "Ask": ask,
            "Delta": round(delta,2),
            "POP": round(pop*100,1),
            "Volume": volume,
            "OI": oi,
            "Quality": quality,
            "Score": round(score,3)
        })


# -------------------------
# DISPLAY
# -------------------------
df = pd.DataFrame(results)

if not df.empty:
    df = df.sort_values("Score", ascending=False)

    st.subheader("🔥 Opportunités Wheel (SMART)")
    st.dataframe(df, use_container_width=True)

    st.subheader("🏆 Top 10")
    st.write(df.head(10))

else:
    st.warning("⚠️ Aucun résultat — improbable (vérifie API)")

st.caption(f"Trades trouvés: {len(results)}")
