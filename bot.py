import os
import pandas as pd
from datetime import datetime
import time
import requests
from alpha_vantage.timeseries import TimeSeries

# -------------------- API KEYS (APNI DALO) --------------------
ALPHA_VANTAGE_KEY = "R973R3LZRAUSA5W0"  # ✅ Tumhari Alpha Vantage key

# 🔴 Telegram Bot Token aur Chat ID (YEH APNI DALNI HOGE)
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN_HERE"  # @BotFather se lo
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"  # Apna chat ID dalo

# Test stocks
TEST_STOCKS = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK']  # 4 stocks test ke liye

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
        print(f"📤 Sending to Telegram: {url}")
        response = requests.post(url, json=payload, timeout=15)
        print(f"📨 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Telegram message sent successfully!")
            return True
        else:
            print(f"❌ Telegram error: {response.text[:200]}")
            # Agar error aaye to details print karo
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
            print(f"⚠️ {symbol} returned empty data")
            return None
        except Exception as e:
            print(f"❌ Error for {symbol}: {e}")
            return None

# -------------------- STOCK ANALYSIS --------------------
def analyze_stock(symbol, data):
    """Basic analysis of stock data"""
    try:
        latest = data.iloc[-1]
        prev = data.iloc[-2] if len(data) > 1 else latest
        
        change = latest['close'] - prev['close']
        change_percent = (change / prev['close']) * 100 if prev['close'] != 0 else 0
        
        result = {
            'Symbol': symbol,
            'Price': round(latest['close'], 2),
            'Change': round(change, 2),
            'Change%': round(change_percent, 2),
            'Volume': int(latest['volume']),
            'Status': '✅ Success'
        }
        return result
    except Exception as e:
        print(f"❌ Analysis error for {symbol}: {e}")
        return {
            'Symbol': symbol,
            'Status': '❌ Failed',
            'Error': str(e)[:50]
        }

# -------------------- MAIN FUNCTION --------------------
def main():
    print("="*70)
    print("🚀 STOCK CAPTURE WITH TELEGRAM FALLBACK")
    print("="*70)
    print(f"🔑 Alpha Vantage Key: {ALPHA_VANTAGE_KEY[:5]}...{ALPHA_VANTAGE_KEY[-5:]}")
    print(f"🤖 Telegram Token: {'✅ Set' if TELEGRAM_TOKEN != 'YOUR_BOT_TOKEN_HERE' else '❌ Not Set'}")
    print(f"📊 Testing Stocks: {TEST_STOCKS}")
    print("-"*70)
    
    client = AlphaVantageClient(ALPHA_VANTAGE_KEY)
    results = []
    
    for i, stock in enumerate(TEST_STOCKS):
        print(f"\n🔍 Testing {i+1}/{len(TEST_STOCKS)}: {stock}")
        
        data = client.get_intraday(stock, '5min')
        
        if data is not None:
            analysis = analyze_stock(stock, data)
        else:
            analysis = {
                'Symbol': stock,
                'Status': '❌ Failed',
                'Error': 'No data from API'
            }
        
        results.append(analysis)
        
        # Agar fail hua to bhi print karo
        if analysis['Status'] == '✅ Success':
            print(f"✅ {stock} analysis complete")
        else:
            print(f"❌ {stock} failed: {analysis.get('Error', 'Unknown error')}")
        
        # Rate limit avoid karne ke liye wait
        if i < len(TEST_STOCKS) - 1:
            wait_time = 15  # Free API ke liye safe wait
            print(f"⏳ Waiting {wait_time} seconds before next API call...")
            time.sleep(wait_time)
    
    # -------------------- TELEGRAM MESSAGE BANANA --------------------
    print("\n" + "="*70)
    print("📊 PREPARING TELEGRAM MESSAGE")
    print("="*70)
    
    # Success aur fail count
    success_count = sum(1 for r in results if r['Status'] == '✅ Success')
    fail_count = len(results) - success_count
    
    # Header
    header = f"🚀 *Stock Update Report*\n"
    header += f"📅 {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
    header += f"📊 Total: {len(results)} | ✅ {success_count} | ❌ {fail_count}\n\n"
    
    # Body - har stock ka result
    body = ""
    for r in results:
        if r['Status'] == '✅ Success':
            arrow = "📈" if r['Change'] >= 0 else "📉"
            body += (
                f"*{r['Symbol']}* {r['Status']}\n"
                f"💰 Price: ₹{r['Price']} {arrow}\n"
                f"📊 Change: ₹{r['Change']} ({r['Change%']}%)\n"
                f"📈 Volume: {r['Volume']:,}\n\n"
            )
        else:
            body += (
                f"*{r['Symbol']}* {r['Status']}\n"
                f"⚠️ Error: {r.get('Error', 'Unknown')}\n\n"
            )
    
    # Agar sab fail ho jaye
    if success_count == 0:
        special_message = "❌ *No stocks data received!*\n"
        special_message += "Possible reasons:\n"
        special_message += "• API rate limit hit\n"
        special_message += "• Invalid stock symbols\n"
        special_message += "• Network issue\n"
        body = special_message + "\n" + body
    
    # Agar sab success ho jaye
    elif fail_count == 0:
        body = "🎉 *All stocks captured successfully!*\n\n" + body
    
    # Footer
    footer = "⚡ *Powered by Alpha Vantage*\n#StockUpdate #TelegramBot"
    
    full_message = header + body + footer
    
    # Message length check (Telegram max 4096 chars)
    if len(full_message) > 4000:
        full_message = full_message[:4000] + "\n\n... (truncated)"
    
    # Print to console for debugging
    print("\n📋 FINAL MESSAGE TO SEND:")
    print("-"*50)
    print(full_message)
    print("-"*50)
    
    # -------------------- SEND TO TELEGRAM --------------------
    print("\n📱 SENDING TO TELEGRAM...")
    success = send_telegram_message(full_message)
    
    if success:
        print("✅ Telegram update sent successfully!")
    else:
        print("❌ Failed to send Telegram message.")
        print("\n💡 Troubleshooting tips:")
        print("1. Check if TELEGRAM_TOKEN is correct")
        print("2. Check if TELEGRAM_CHAT_ID is correct")
        print("3. Make sure you have started the bot (send /start)")
        print("4. Check if bot is added to the chat")
        print("5. Try sending a test message manually:")
        print(f"   curl -X POST https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage -d 'chat_id={TELEGRAM_CHAT_ID}&text=Test'")
    
    print("="*70)

if __name__ == "__main__":
    main()
