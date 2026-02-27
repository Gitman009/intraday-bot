import os
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
from alpha_vantage.timeseries import TimeSeries
import time
from tenacity import retry, stop_after_attempt, wait_exponential

warnings.filterwarnings('ignore')

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("❌ TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set!")
if not ALPHA_VANTAGE_KEY:
    raise ValueError("❌ ALPHA_VANTAGE_API_KEY must be set in secrets!")

IST = pytz.timezone('Asia/Kolkata')

# ================= ALPHA VANTAGE CLIENT =================
class AlphaVantageClient:
    def __init__(self, api_key):
        self.ts = TimeSeries(key=api_key, output_format='pandas')
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def get_intraday(self, symbol, interval='5min'):
        try:
            clean_symbol = symbol.replace('.NS', '')
            data, meta = self.ts.get_intraday(symbol=clean_symbol, interval=interval, outputsize='compact')
            if data is not None and not data.empty:
                data.columns = ['open', 'high', 'low', 'close', 'volume']
                return data
            return None
        except Exception as e:
            print(f"⚠️ Alpha Vantage error for {symbol}: {e}")
            return None

av_client = AlphaVantageClient(ALPHA_VANTAGE_KEY)

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

    # ================= STEP 1: QUICK SCAN (5-min data) =================
    def quick_scan(self, symbol):
        """10 stocks ka quick scan - sirf 5-min data se basic score"""
        try:
            print(f"⚡ Quick scan: {symbol}")
            data_5m = av_client.get_intraday(symbol, '5min')
            if data_5m is None or data_5m.empty:
                return None
            
            data_5m = data_5m.iloc[::-1]  # reverse
            data_5m['EMA_9'] = ta.trend.ema_indicator(data_5m['close'], window=9)
            data_5m['EMA_21'] = ta.trend.ema_indicator(data_5m['close'], window=21)
            data_5m['RSI'] = ta.momentum.rsi(data_5m['close'], window=14)
            data_5m['Volume_Ratio'] = data_5m['volume'] / data_5m['volume'].rolling(20).mean()
            
            latest = data_5m.iloc[-1]
            score = 0
            
            if latest['close'] > latest['EMA_9'] > latest['EMA_21']:
                score += 2
            if 55 < latest['RSI'] < 70:
                score += 2
            if latest['Volume_Ratio'] > 1.5:
                score += 1
            
            if score >= 2:
                return {
                    "symbol": symbol,
                    "score": score,
                    "data_5m": data_5m
                }
            return None
        except Exception as e:
            print(f"⚠️ Quick scan error {symbol}: {e}")
            return None

    # ================= STEP 2: DEEP ANALYSIS (15-min data) =================
    def deep_analyze(self, symbol, data_5m):
        """Top 5 stocks ka 15-min data se deep analysis"""
        try:
            print(f"🔍 Deep analysis: {symbol}")
            # 15-min data लो
            data_15m = av_client.get_intraday(symbol, '15min')
            if data_15m is None or data_15m.empty:
                return None
            
            data_15m = data_15m.iloc[::-1]
            data_15m['EMA_9'] = ta.trend.ema_indicator(data_15m['close'], window=9)
            data_15m['EMA_21'] = ta.trend.ema_indicator(data_15m['close'], window=21)
            
            # 5-min data में और indicators
            data_5m['EMA_50'] = ta.trend.ema_indicator(data_5m['close'], window=50)
            macd = ta.trend.MACD(data_5m['close'])
            data_5m['MACD'] = macd.macd()
            data_5m['MACD_Signal'] = macd.macd_signal()
            
            latest = data_5m.iloc[-1]
            prev = data_5m.iloc[-2]
            latest_15m = data_15m.iloc[-1]
            
            score = 0
            reasons = []
            
            # 1. Trend (50 EMA भी check)
            if latest['close'] > latest['EMA_9'] > latest['EMA_21'] > latest['EMA_50']:
                score += 3
                reasons.append("🔥 Strong Uptrend")
            
            # 2. RSI
            if 55 < latest['RSI'] < 70:
                score += 2
                reasons.append(f"📊 RSI Momentum ({latest['RSI']:.1f})")
            elif latest['RSI'] < 30 and latest['RSI'] > prev['RSI']:
                score += 2
                reasons.append(f"🔄 RSI Reversal ({latest['RSI']:.1f})")
            
            # 3. Volume
            if latest['Volume_Ratio'] > 1.5:
                score += 2
                reasons.append(f"📈 Volume Spike ({latest['Volume_Ratio']:.1f}x)")
            
            # 4. MACD
            if latest['MACD'] > latest['MACD_Signal']:
                score += 1
                reasons.append("💹 MACD Bullish")
            
            # 5. 15-min confirmation
            if latest_15m['close'] > latest_15m['EMA_9'] > latest_15m['EMA_21']:
                score += 2
                reasons.append("✅ 15-min Trend Up")
            
            if score >= 4:
                return {
                    "Symbol": symbol.replace(".NS", ""),
                    "Score": score,
                    "Price": round(latest['close'], 2),
                    "RSI": round(latest['RSI'], 2),
                    "Volume_Ratio": round(latest['Volume_Ratio'], 2),
                    "Reasons": " | ".join(reasons[:3]),
                    "Time": datetime.now(IST).strftime("%I:%M %p")
                }
            return None
        except Exception as e:
            print(f"❌ Deep analysis error {symbol}: {e}")
            return None

    # ================= STEP 3: TELEGRAM SEND =================
    async def send_telegram(self, picks):
        if not picks:
            message = "🤖 **Intraday Scan**\n\n❌ Aaj koi strong stock setup nahi mila.\n⏰ Try again next scan!"
        else:
            header = f"🚀 **TOP {len(picks)} INTRADAY PICKS**\n"
            header += f"📅 {datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')}\n\n"
            body = ""
            for i, stock in enumerate(picks, 1):
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

    # ================= MAIN RUN =================
    def run(self):
        print("="*50)
        print("🚀 3-STEP INTRADAY SCREENER")
        print("="*50)
        
        # Stock lists लो
        nifty50, nifty500 = self.get_stock_lists()
        
        # STEP 1: 10 stocks का quick scan (5 Nifty50 + 5 Nifty500)
        symbols_to_scan = nifty50[:5] + nifty500[:5]
        print(f"\n🔰 STEP 1: Quick scanning {len(symbols_to_scan)} stocks...")
        
        quick_results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self.quick_scan, sym) for sym in symbols_to_scan]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    quick_results.append(result)
                time.sleep(1)  # थोड़ा delay
        
        if not quick_results:
            print("❌ No stocks found in quick scan.")
            asyncio.run(self.send_telegram([]))
            return
        
        # STEP 2: Top 5 stocks का deep analysis
        quick_results.sort(key=lambda x: x['score'], reverse=True)
        top_5 = quick_results[:5]
        print(f"\n🔰 STEP 2: Deep analyzing top {len(top_5)} stocks with 15-min data...")
        
        final_results = []
        for item in top_5:
            result = self.deep_analyze(item['symbol'], item['data_5m'])
            if result:
                final_results.append(result)
            time.sleep(12)  # Alpha Vantage rate limit
        
        # STEP 3: Top 4 picks Telegram भेजो
        final_results.sort(key=lambda x: x['Score'], reverse=True)
        top_4 = final_results[:4]
        
        print(f"\n🔰 STEP 3: Sending top {len(top_4)} picks to Telegram...")
        asyncio.run(self.send_telegram(top_4))
        
        # Summary
        print("\n" + "="*50)
        print(f"✅ Scan complete!")
        print(f"📊 Quick scan: {len(quick_results)} stocks qualified")
        print(f"🎯 Deep analysis: {len(final_results)} strong setups found")
        print(f"📨 Sent: {len(top_4)} picks to Telegram")
        print("="*50)

# ================= RUN =================
if __name__ == "__main__":
    screener = NiftyIntradayScreener()
    screener.run()
