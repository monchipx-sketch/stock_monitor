import os
import json
import urllib.request

WEBHOOK_URL = os.environ.get(
    "WEBHOOK_URL",
    "https://discord.com/api/webhooks/1575388626278158470/DOrenALrKACFr0ZeoYUw-zxXog3e_H4sVbdnhyorYj5xGmveQ3x9gQr8k0VOH8Yk0CVa"
)

TICKER = "1570.T"

def fetch_data():
    """Yahoo Finance APIから日足データを直接取得（ライブラリ不要）"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}?range=6mo&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode())
    
    result = data["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    return [c for c in closes if c is not None]

def calculate_rsi(prices, period=14):
    """Wilder法によるRSI計算"""
    if len(prices) <= period:
        return 50.0
    
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def analyze():
    closes = fetch_data()
    if len(closes) < 75:
        print("株価データの件数が不足しています。")
        return

    current_price = closes[-1]
    ma25 = sum(closes[-25:]) / 25
    ma75 = sum(closes[-75:]) / 75
    rsi14 = calculate_rsi(closes, 14)
    ma25_bias = ((current_price - ma25) / ma25) * 100

    signals = []
    if rsi14 <= 35.0:
        signals.append(f"RSI売られすぎ圏 ({rsi14:.1f})")
    if -2.5 <= ma25_bias <= 1.0:
        signals.append(f"25日移動平均線付近に接近 ({ma25_bias:+.1f}%)")
    if current_price <= ma75 * 1.01:
        signals.append("75日移動平均線サポート圏に到達")

    support_line = ma75 if abs(current_price - ma75) < abs(current_price - ma25) else ma25
    buy_target = round(min(current_price, support_line))
    stop_loss = round(buy_target * 0.985)
    take_profit = round(buy_target * 1.03)

    title = "🔔 **【日経レバ(1570) 昼休みテクニカル速報】**"
    reasons_text = "\n".join([f"・{s}" for s in signals]) if signals else "・定期モニタリング（特段シグナルなし）"

    message = (
        f"{title}\n"
        f"現在の株価: **{current_price:,.0f}円**\n"
        f"【指標状況】\n"
        f"{reasons_text}\n"
        f"・RSI(14): {rsi14:.1f} / 25日線乖離率: {ma25_bias:+.1f}%\n"
        f"・25日線: {ma25:,.0f}円 / 75日線: {ma75:,.0f}円\n\n"
        f"🎯 **後場のIFD-OCO目安プラン**\n"
        f"・買い指値目安: **{buy_target:,.0f}円** 付近\n"
        f"・損切り逆指値: **{stop_loss:,.0f}円** (-1.5%目安)\n"
        f"・利確目標指値: **{take_profit:,.0f}円** (+3.0%目安)\n"
    )

    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        print("通知送信完了:", res.status)

if __name__ == "__main__":
    analyze()