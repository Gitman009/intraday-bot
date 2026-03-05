import os
import pandas as pd
from datetime import datetime
import asyncio
import time
import requests
from alpha_vantage.timeseries import TimeSeries

# -------------------- API KEYS (APNI DALO) --------------------
ALPHA_VANTAGE_KEY = "R973R3LZRAUSA5W0"  # ✅ Tumhari Alpha Vantage key

# 🔴 Telegram Bot Token aur Chat ID (YEH APNI DALNI HOGE)
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN_HERE"  # @BotFather se lo
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"  # Apna chat ID dalo

# Do test stocks
TEST_STOCKS = ['RELIANCE', 'TCS']  # Bina .NS ke, Alpha Vantage format

# -------------------- TELEGRAM FUNCTION --------------------
def send_telegram_message(message):
    """Telegram par message bhejne ka function"""
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Telegram token set nahi hai. Message bhejna skip kiya.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram message sent")
            return True
        else:
            print(f"❌ Telegram error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram exception: {e}")
        return False

# -------------------- ALPHA VANTAGE CLIENT --------------------
class AlphaVantageClient:
    def __init__(self, api_key):
        self.ts = TimeSeries(key=api_key, output_format='pandas')
    
    def get_intraday(self, symbol, interval='5min'):
        """Fetch intraday data from Alpha Vantage"""
        try:
            print(f"📡 Fetching {symbol}...")
            data, meta = self.ts.get_intraday(symbol=symbol, interval=interval, outputsize='compact')
            if data is not None and not data.empty:
                data.columns = ['open', 'high', 'low', 'close', 'volume']
                data = data.iloc[::-1]  # Reverse to make latest last
                print(f"✅ {symbol} data received: {len(data)} rows")
                return data
            return None
        except Exception as e:
            print(f"❌ Error for {symbol}: {e}")
            return None

# -------------------- SIMPLE ANALYSIS --------------------
def analyze_stock(symbol, data):
    """Basic analysis of stock data"""
    try:
        latest = data.iloc[-1]
        prev = data.iloc[-2] if len(data) > 1 else latest
        
        # Calculate basic change
        change = latest['close'] - prev['close']
        change_percent = (change / prev['close']) * 100 if prev['close'] != 0 else 0
        
        result = {
            'Symbol': symbol,
            'Price': round(latest['close'], 2),
            'Change': round(change, 2),
            'Change%': round(change_percent, 2),
            'Volume': int(latest['volume']),
            'Time': datetime.now().strftime("%H:%M:%S")
        }
        return result
    except Exception as e:
        print(f"❌ Analysis error for {symbol}: {e}")
        return None

# -------------------- MAIN FUNCTION --------------------
def main():
    print("="*60)
    print("🚀 TEST MODE: Sirf 2 Stocks Capture + Telegram")
    print("="*60)
    print(f"🔑 Alpha Vantage Key: {ALPHA_VANTAGE_KEY[:5]}...{ALPHA_VANTAGE_KEY[-5:]}")
    print(f"🤖 Telegram Token: {'✅ Set' if TELEGRAM_TOKEN != 'YOUR_BOT_TOKEN_HERE' else '❌ Not Set'}")
    print(f"📊 Testing Stocks: {TEST_STOCKS}")
    print("-"*60)
    
    # Create client
    client = AlphaVantageClient(ALPHA_VANTAGE_KEY)
    
    results = []
    
    for i, stock in enumerate(TEST_STOCKS):
        print(f"\n🔍 Testing {i+1}/{len(TEST_STOCKS)}: {stock}")
        
        # Get data
        data = client.get_intraday(stock, '5min')
        
        if data is not None:
            # Analyze
            analysis = analyze_stock(stock, data)
            if analysis:
                results.append(analysis)
                print(f"✅ Analysis complete for {stock}")
            else:
                print(f"❌ Analysis failed for {stock}")
        else:
            print(f"❌ No data for {stock}")
        
        # Rate limit avoid karne ke liye (12 sec wait free API ke liye)
        if i < len(TEST_STOCKS) - 1:
            print("⏳ Waiting 12 seconds before next API call...")
            time.sleep(12)
    
    # Print results to console
    print("\n" + "="*60)
    print("📊 CONSOLE RESULTS")
    print("="*60)
    
    if results:
        for r in results:
            arrow = "📈" if r['Change'] >= 0 else "📉"
            print(f"""
🔹 {r['Symbol']}:
   Price: ₹{r['Price']} {arrow}
   Change: ₹{r['Change']} ({r['Change%']}%)
   Volume: {r['Volume']:,}
   Time: {r['Time']}
""")
        
        print(f"\n✅ Successfully captured {len(results)}/{len(TEST_STOCKS)} stocks")
        
        # -------------------- TELEGRAM MESSAGE --------------------
        print("\n" + "-"*60)
        print("📱 Sending to Telegram...")
        
        # Telegram message banate hain
        header = f"🚀 *Stock Update* - {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n\n"
        body = ""
        
        for r in results:
            arrow = "📈" if r['Change'] >= 0 else "📉"
            body += (
                f"*{r['Symbol']}*\n"
                f"💰 Price: ₹{r['Price']} {arrow}\n"
                f"📊 Change: ₹{r['Change']} ({r['Change%']}%)\n"
                f"📈 Volume: {r['Volume']:,}\n\n"
            )
        
        footer = "⚡ *Powered by Alpha Vantage*\n#StockUpdate #TestMode"
        
        full_message = header + body + footer
        
        # Send to Telegram
        send_telegram_message(full_message)
        
    else:
        print("❌ Koi bhi stock capture nahi hua")
        send_telegram_message("❌ *Stock Update Failed*\nKoi data capture nahi hua.")
    
    print("="*60)

if __name__ == "__main__":
    main()
