import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests   # ✅ Telegram ke liye

# -------------------------------
# TELEGRAM SETTINGS 👇 YAHI TOKEN DALNA
# -------------------------------

BOT_TOKEN = "7982592552:AAHebslaeHfca3dUpyPBX0_TLw_HwwGi5bk"
CHAT_ID = "1039438785"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, data=payload)

# -------------------------------
# 90 STOCK LIST
# -------------------------------

stocks = [
"RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS",
"LT.NS","SBIN.NS","AXISBANK.NS","KOTAKBANK.NS","HINDUNILVR.NS",
"ITC.NS","BAJFINANCE.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS",
"BHARTIARTL.NS","HCLTECH.NS","WIPRO.NS","ULTRACEMCO.NS","TITAN.NS",

"ADANIENT.NS","ADANIPORTS.NS","POWERGRID.NS","NTPC.NS","ONGC.NS",
"COALINDIA.NS","TATASTEEL.NS","JSWSTEEL.NS","GRASIM.NS","DIVISLAB.NS",
"EICHERMOT.NS","BAJAJFINSV.NS","TECHM.NS","DRREDDY.NS","HDFCLIFE.NS",
"SBILIFE.NS","BPCL.NS","BRITANNIA.NS","CIPLA.NS","HEROMOTOCO.NS",
"INDUSINDBK.NS","APOLLOHOSP.NS","TATAMOTORS.NS","PIDILITIND.NS","DABUR.NS",
"AMBUJACEM.NS","GODREJCP.NS","M&M.NS","SIEMENS.NS","ICICIPRULI.NS",

"PEL.NS","ABB.NS","TORNTPHARM.NS","MPHASIS.NS","LUPIN.NS",
"SAIL.NS","BANDHANBNK.NS","BANKBARODA.NS","CANBK.NS","INDIGO.NS",
"IRCTC.NS","HAVELLS.NS","BALKRISIND.NS","ASTRAL.NS","PAGEIND.NS",
"POLYCAB.NS","JUBLFOOD.NS","COLPAL.NS","VEDL.NS","NMDC.NS",
"SRF.NS","TATAPOWER.NS","ADANIGREEN.NS","ADANITRANS.NS","ADANIPOWER.NS",
"ICICIGI.NS","GLENMARK.NS","MOTHERSON.NS","ESCORTS.NS","RECLTD.NS",
"PFC.NS","LICHSGFIN.NS","IDEA.NS","ZEEL.NS","SUNTV.NS",
"CONCOR.NS","TRENT.NS","ALKEM.NS","ACC.NS","OBEROIRLTY.NS"
]

# -------------------------------
# TECHNICAL FUNCTIONS
# -------------------------------

def calculate_rsi(data, period=14):
    delta = data["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data):
    exp1 = data["Close"].ewm(span=12).mean()
    exp2 = data["Close"].ewm(span=26).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9).mean()
    return macd, signal

# -------------------------------
# SCAN FUNCTION
# -------------------------------

results = []

for stock in stocks:
    try:
        df = yf.download(stock, interval="5m", period="1d", progress=False)
        
        if len(df) < 30:
            continue

        df["RSI"] = calculate_rsi(df)
        df["MACD"], df["Signal"] = calculate_macd(df)
        df["VWAP"] = (df["Close"] * df["Volume"]).cumsum() / df["Volume"].cumsum()

        latest = df.iloc[-1]

        rsi_cond = latest["RSI"] > 55
        macd_cond = latest["MACD"] > latest["Signal"]
        vwap_cond = latest["Close"] > latest["VWAP"]
        vol_cond = latest["Volume"] > df["Volume"].rolling(20).mean().iloc[-1]
        breakout = latest["Close"] > df["High"].rolling(20).max().iloc[-2]

        score = sum([rsi_cond, macd_cond, vwap_cond, vol_cond, breakout])

        results.append((stock, score, latest["Close"]))

    except:
        pass

    time.sleep(0.3)

# -------------------------------
# TOP 4 STOCKS
# -------------------------------

results = sorted(results, key=lambda x: x[1], reverse=True)

print("\n🔥 BEST INTRADAY STOCKS TODAY:\n")

message = "🔥 BEST INTRADAY STOCKS TODAY:\n\n"

for stock, score, price in results[:4]:
    print(stock, "Score:", score, "Price:", price)
    message += f"{stock}\nScore: {score}\nPrice: {round(price,2)}\n\n"

# ✅ Telegram Alert Send
send_telegram_message(message)

print("✅ Telegram Alert Sent")
