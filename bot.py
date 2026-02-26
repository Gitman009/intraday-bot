import os
import yfinance as yf
import pandas as pd
import ta
from datetime import datetime, timedelta
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from niftystocks import ns
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz

warnings.filterwarnings('ignore')

# ================= TELEGRAM CONFIG =================
TELEGRAM_TOKEN = os.getenv("7982592552:AAHebslaeHfca3dUpyPBX0_TLw_HwwGi5bk")
TELEGRAM_CHAT_ID = os.getenv("1039438785")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("❌ TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables!")

IST = pytz.timezone('Asia/Kolkata')

def is_market_open():
    """Check if market is open (9:15 AM - 3:30 PM IST, Mon-Fri)"""
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_start <= now <= market_end

class NiftyIntradayScreener:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)

    def get_stock_lists(self):
        print("📥 Fetching stock lists...")
        nifty50 = ns.get_nifty50_with_ns()
        nifty500 = ns.get_nifty500_with_ns()
        print(f"✅ Nifty50: {len(nifty50)} stocks")
        print(f"✅ Nifty500: {len(nifty500)} stocks")
        return nifty50, nifty500

    def analyze_stock(self, symbol):
        try:
            end = datetime.now()
            start = end - timedelta(days=7)

            data_5m = yf.download(symbol, start=start, end=end, interval="5m", progress=False)
            data_15m = yf.download(symbol, start=start, end=end, interval="15m", progress=False)

            if data_5m.empty or data_15m.empty:
                return None

            # Indicators
            data_5m['EMA_9'] = ta.trend.ema_indicator(data_5m['Close'], window=9)
            data_5m['EMA_21'] = ta.trend.ema_indicator(data_5m['Close'], window=21)
            data_5m['EMA_50'] = ta.trend.ema_indicator(data_5m['Close'], window=50)
            data_5m['RSI'] = ta.momentum.rsi(data_5m['Close'], window=14)

            macd = ta.trend.MACD(data_5m['Close'])
            data_5m['MACD'] = macd.macd()
            data_5m['MACD_Signal'] = macd.macd_signal()

            data_5m['Volume_SMA'] = data_5m['Volume'].rolling(window=20).mean()
            data_5m['Volume_Ratio'] = data_5m['Volume'] / data_5m['Volume_SMA']

            # 15m confirmation
            data_15m['EMA_9'] = ta.trend.ema_indicator(data_15m['Close'], window=9)
            data_15m['EMA_21'] = ta.trend.ema_indicator(data_15m['Close'], window=21)

            latest = data_5m.iloc[-1]
            prev = data_5m.iloc[-2]
            latest_15m = data_15m.iloc[-1]

            score = 0
            reasons = []

            # Trend
            if latest['Close'] > latest['EMA_9'] > latest['EMA_21'] > latest['EMA_50']:
                score += 3
                reasons.append("🔥 Strong Uptrend")

            # RSI
            if 55 < latest['RSI'] < 70:
                score += 2
                reasons.append(f"📊 RSI Momentum ({latest['RSI']:.1f})")
            elif latest['RSI'] < 30 and latest['RSI'] > prev['RSI']:
                score += 2
                reasons.append(f"🔄 RSI Reversal ({latest['RSI']:.1f})")

            # Volume
            if latest['Volume_Ratio'] > 1.5:
                score += 2
                reasons.append(f"📈 Volume Spike ({latest['Volume_Ratio']:.1f}x)")

            # MACD
            if latest['MACD'] > latest['MACD_Signal']:
                score += 1
                reasons.append("💹 MACD Bullish")

            # 15m confirmation
            if latest_15m['Close'] > latest_15m['EMA_9'] > latest_15m['EMA_21']:
                score += 2
                reasons.append("✅ 15-min Trend Up")

            if score >= 5:
                return {
                    "Symbol": symbol.replace(".NS", ""),
                    "Score": score,
                    "Price": round(latest['Close'], 2),
                    "RSI": round(latest['RSI'], 2),
                    "Volume_Ratio": round(latest['Volume_Ratio'], 2),
                    "Reasons": " | ".join(reasons[:3]),
                    "Time": datetime.now(IST).strftime("%I:%M %p")
                }

            return None
        except Exception as e:
            # For debugging, you can print error: print(f"Error analyzing {symbol}: {e}")
            return None

    def scan_stocks(self, symbols, workers=10):
        results = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(self.analyze_stock, sym) for sym in symbols]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        results.sort(key=lambda x: x["Score"], reverse=True)
        return results

    async def send_telegram(self, picks):
        if not picks:
            message = "🤖 **Intraday Scan**\n\n❌ No strong setups found today."
        else:
            header = f"🚀 **TOP {len(picks[:4])} INTRADAY PICKS**\n"
            header += f"📅 {datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')}\n\n"
            body = ""
            for i, stock in enumerate(picks[:4], 1):
                body += (
                    f"**{i}. {stock['Symbol']}**\n"
                    f"💰 Price: ₹{stock['Price']}\n"
                    f"📊 RSI: {stock['RSI']} | Volume: {stock['Volume_Ratio']}x\n"
                    f"🎯 Signals: {stock['Reasons']}\n\n"
                )
            message = header + body + "⚠️ *Educational purpose only*"

        try:
            await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
            print("✅ Telegram message sent")
        except TelegramError as e:
            print(f"❌ Telegram error: {e}")

    def run(self):
        # Optional market hours check – uncomment if you want to restrict to market hours
        # if not is_market_open():
        #     print("⏰ Market closed. Exiting.")
        #     return

        print("🚀 Running Intraday Scanner...")
        nifty50, nifty500 = self.get_stock_lists()

        # Scan first 20 from Nifty50 and first 100 from Nifty500
        results_50 = self.scan_stocks(nifty50[:20], workers=8)
        results_500 = self.scan_stocks(nifty500[:100], workers=10)

        all_results = results_50 + results_500
        all_results.sort(key=lambda x: x["Score"], reverse=True)

        if all_results:
            print(f"✅ Found {len(all_results)} stocks. Sending top picks...")
        else:
            print("❌ No stocks found.")

        asyncio.run(self.send_telegram(all_results))

# ================= ENTRY POINT =================
if __name__ == "__main__":
    screener = NiftyIntradayScreener()
    screener.run()    # ================= TELEGRAM SEND =================
    async def send_telegram(self, picks):

        if not picks:
            message = "❌ No strong intraday setup found."
            await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            return

        header = f"🚀 TOP INTRADAY PICKS\n📅 {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}\n\n"
        body = ""

        for i, stock in enumerate(picks[:4], 1):
            body += (
                f"{i}. {stock['Symbol']}\n"
                f"Price: ₹{stock['Price']}\n"
                f"RSI: {stock['RSI']} | Vol: {stock['Volume_Ratio']}x\n"
                f"Signals: {stock['Reasons']}\n\n"
            )

        message = header + body + "⚠️ Educational Purpose Only"

        try:
            await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            print("✅ Telegram message sent")
        except TelegramError as e:
            print("❌ Telegram Error:", e)

    # ================= MAIN RUN =================
    def run(self):

        print("🚀 Running Intraday Scanner...")

        nifty50, nifty500 = self.get_stock_lists()

        results_50 = self.scan_stocks(nifty50[:20], workers=8)
        results_500 = self.scan_stocks(nifty500[:100], workers=10)

        all_results = results_50 + results_500
        all_results.sort(key=lambda x: x["Score"], reverse=True)

        asyncio.run(self.send_telegram(all_results))


# ================= ENTRY POINT =================
if __name__ == "__main__":

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing in GitHub Secrets")
        exit()

    screener = NiftyIntradayScreener()
    screener.run()
message = "🔥 BEST INTRADAY STOCKS TODAY:\n\n"

for stock, score, price in results[:4]:
    print(stock, "Score:", score, "Price:", price)
    message += f"{stock}\nScore: {score}\nPrice: {round(price,2)}\n\n"

# ✅ Telegram Alert Send
send_telegram_message(message)

print("✅ Telegram Alert Sent")
