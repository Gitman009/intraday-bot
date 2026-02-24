import requests
from datetime import datetime

TOKEN = "7982592552:AAHebslaeHfca3dUpyPBX0_TLw_HwwGi5bk"
CHAT_ID = "7982592552"

message = f""" 📈 Bot Capture A Intraday Stock
📅 {datetime.now().strftime('%d-%m-%Y')}

📈 Tomorrow Intraday Pick
Stock: RELIANCE
Signal: BUY
Strategy:Basic Test Signal
VWAP Support + RSI Strength
MACD Bullish Cross
Volume Expansion Seen
Momentum Intact"""

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {"chat_id": CHAT_ID, "text": message}
requests.post(url, data=data)
