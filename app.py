def get_option_premium(symbol, price, strike, T):

    try:
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}?apiKey={API_KEY}"
        r = requests.get(url).json()

        res = r.get("results", {})

        last = res.get("last_trade", {}) or {}
        quote = res.get("last_quote", {}) or {}

        bid = quote.get("bid")
        ask = quote.get("ask")
        last_price = last.get("price")

        # 1️⃣ MID PRICE
        if bid and ask and bid > 0 and ask > 0:
            return (bid + ask) / 2

        # 2️⃣ LAST
        if last_price and last_price > 0:
            return last_price

    except:
        pass

    # 💣 3️⃣ FALLBACK PRO (TRÈS IMPORTANT)
    intrinsic = max(0, strike - price)
    extrinsic = price * 0.02 * math.sqrt(T)

    return intrinsic + extrinsic
