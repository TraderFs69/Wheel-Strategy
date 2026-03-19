import streamlit as st
import pandas as pd
import requests

API_KEY = st.secrets["POLYGON_API_KEY"]

st.title("TEST OPTIONS")

url = f"https://api.polygon.io/v3/snapshot/options/AAPL?apiKey={API_KEY}"
data = requests.get(url).json()

results = data.get("results", [])

rows = []

for opt in results[:50]:

    details = opt.get("details", {})
    greeks = opt.get("greeks", {}) or {}
    last_trade = opt.get("last_trade", {}) or {}

    rows.append({
        "Strike": details.get("strike_price"),
        "Expiration": details.get("expiration_date"),
        "Delta": greeks.get("delta"),
        "Theta": greeks.get("theta"),
        "Vega": greeks.get("vega"),
        "Last": last_trade.get("price")
    })

df = pd.DataFrame(rows)
st.dataframe(df)
