import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

API_KEY = st.secrets["POLYGON_API_KEY"]

st.set_page_config(layout="wide")
st.title("🔥 TEA - Wheel Scanner EXECUTION READY")

# -------------------------
# USER INPUT
# -------------------------
st.sidebar.header("🎯 Paramètres")

target_delta = st.sidebar.slider("Delta cible", 0.10, 0.40, 0.20, 0.05)

week_choice = st.sidebar.selectbox(
    "Expiration",
    ["Prochain vendredi", "2e vendredi", "3e vendredi"]
)

min_oi = st.sidebar.slider("Min Open Interest", 0, 2000, 10)
min_volume = st.sidebar.slider("Min Volume", 0, 500, 5)

# -------------------------
# CALCUL VENDREDI
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
# LOAD TICKERS
# -------------------------
@st.cache_data
def load_sp500():
    url = "https://datahub.io/core/s-and-p-500-companies/r/constituents.csv"
    df = pd.read_csv(url)
    return df["Symbol"].tolist()

tickers = load_sp500()

# -------------------------
# DATA FUNCTIONS
# -------------------------
@st.cache_data(ttl=300)
def get_price(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={API_KEY}"
        r = requests.get(url).json()
        return r["results"][0]["c"]
    except:
        return None


@st.cache_data(ttl=300)
def get_history(ticker):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/200/{datetime.today().strftime('%Y-%m-%d')}?apiKey={API_KEY}"
        r = requests.get(url).json()
        return pd.DataFrame(r["results"])
    except:
        return None


@st.cache_data(ttl=300)
def get_options(ticker):
    try:
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&limit=500&apiKey={API_KEY}"
        r = requests.get(url).json()
        return r.get("results", [])
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
        mid = (bid + ask) / 2 if bid and ask else bid or ask or 0

        return {
            "delta": greeks.get("delta"),
            "theta": greeks.get("theta"),
            "iv": res.get("implied_volatility"),
            "mid": mid,
            "bid": bid,
            "ask": ask,
            "volume": res.get("day", {}).get("volume", 0) if isinstance(res.get("day"), dict) else 0
        }
    except:
        return None


# -------------------------
# STOCK SCORE
# -------------------------
def stock_score(df):
    if df is None or len(df) < 200:
        return 0

    df["ema50"] = df["c"].ewm(span=50).mean()
    df["ema200"] = df["c"].ewm(span=200).mean()

    price = df["c"].iloc[-1]
    ema50 = df["ema50"].iloc[-1]
    ema200 = df["ema200"].iloc[-1]

    score = 0

    if price > ema50:
        score += 0.5
    if ema50 > ema200:
        score += 0.5

    return score


# -------------------------
# SCAN
# -------------------------
results = []

for ticker in tickers[:100]:

    price = get_price(ticker)
    if not price:
        continue

    hist = get_history(ticker)
    s_score = stock_score(hist)

    options = get_options(ticker)

    for opt in options[:80]:

        if opt.get("contract_type") != "put":
            continue

        strike = opt.get("strike_price")
        expiration = opt.get("expiration_date")

        if not strike or not expiration:
            continue

        exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()

        if abs((exp_date - target_date).days) > 2:
            continue

        distance = (price - strike) / price
        if distance < 0.01 or distance > 0.12:
            continue

        snapshot = get_snapshot(opt.get("ticker"))
        if not snapshot:
            continue

        delta = snapshot.get("delta")
        bid = snapshot.get("bid", 0)
        ask = snapshot.get("ask", 0)
        volume = snapshot.get("volume", 0)
        iv = snapshot.get("iv", 0.30)

        # 🔥 EXECUTION FILTER
        if bid <= 0:
            continue

        if volume < min_volume:
            continue

        spread = ask - bid
        if spread > bid * 0.5:
            continue

        premium = (bid + ask) / 2

        if delta is None:
            continue

        if not (target_delta - 0.10 <= abs(delta) <= target_delta + 0.10):
            continue

        oi = opt.get("open_interest", 0)
        if oi < min_oi:
            continue

        dte = (exp_date - datetime.today().date()).days

        annual_return = (premium / strike) * (365 / max(dte, 1))
        pop = 1 - abs(delta)

        score = (
            annual_return * 0.3 +
            pop * 0.2 +
            s_score * 0.3 +
            iv * 0.2
        )

        results.append({
            "Ticker": ticker,
            "Price": round(price,2),
            "Strike": strike,
            "Premium": round(premium,2),
            "Bid": bid,
            "Ask": ask,
            "Spread": round(spread,2),
            "Delta": round(delta,2),
            "POP": round(pop*100,1),
            "Volume": volume,
            "OI": oi,
            "Score": round(score,3)
        })


# -------------------------
# DISPLAY
# -------------------------
df = pd.DataFrame(results)

if not df.empty:
    df = df.sort_values("Score", ascending=False)

    st.subheader("🔥 Trades réellement exécutables")
    st.dataframe(df, use_container_width=True)

else:
    st.warning("⚠️ Aucun trade valide (liquidité stricte)")

st.caption(f"Trades trouvés: {len(results)}")
