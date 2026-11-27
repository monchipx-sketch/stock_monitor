import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, time
import pytz

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def get_data():
    ticker = yf.Ticker("1570.T")
    df = ticker.history(period="3mo", interval="1d")
    return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def send_discord(message):
    if not DISCORD_WEBHOOK_URL:
        print("Webhook URLが設定されていません")
        return
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def job_lunch():
    """昼休み通知 (11:31)"""
    df = get_data()
    if df.empty:
        return

    current_price = int(df['Close'].iloc[-1])
    df['SMA25'] = df['Close'].rolling(window=25).mean()
    df['SMA75'] = df['Close'].rolling(window=75).mean()
    df['RSI'] = calculate_rsi(df['Close'])

    rsi_val = round(df['RSI'].iloc[-1], 1)
    sma25_val = int(df['SMA25'].iloc[-1])
    sma75_val = int(df['SMA75'].iloc[-1])
    sma25_diff = round(((current_price - sma25_val) / sma25_val) * 100, 1)

    # 目安ライン計算
    buy_price = current_price
    take_profit = int(buy_price * 1.03)
    stop_loss = int(buy_price * 0.985)

    msg = f"""🔔 **【日経レバ(1570) 昼休みテクニカル速報】**
現在の株価: **{current_price:,}円**

**【指標状況】**
・RSI(14): **{rsi_val}** / 25日線乖離率: **{sma25_diff}%**
・25日線: {sma25_val:,}円 / 75日線: {sma75_val:,}円

🎯 **後場のIFD-OCO目安プラン**
・買い指値目安: **{buy_price:,}円** 付近
・損切り逆指値: **{stop_loss:,}円** (-1.5%目安)
・利確目標指値: **{take_profit:,}円** (+3.0%目安)
"""
    send_discord(msg)

def job_after_market():
    """大引け後のシミュレーション結果通知 (15:45)"""
    ticker = yf.Ticker("1570.T")
    # 当日の日中足を取得
    df_day = ticker.history(period="1d", interval="5m")
    if df_day.empty:
        return

    # 前場終値（11:30時点の価格）を基準買値とする
    # 12:30以降の後場データを抽出
    df_day.index = df_day.index.tz_convert('Asia/Tokyo')
    afternoon_data = df_day[df_day.index.time >= time(12, 30)]

    if afternoon_data.empty:
        return

    # 前場引け時点の終値（12:30直前の足）
    morning_data = df_day[df_day.index.time < time(12, 30)]
    entry_price = int(morning_data['Close'].iloc[-1]) if not morning_data.empty else int(afternoon_data['Open'].iloc[0])

    take_profit = int(entry_price * 1.03)
    stop_loss = int(entry_price * 0.985)

    low_p = int(afternoon_data['Low'].min())
    high_p = int(afternoon_data['High'].max())
    close_p = int(afternoon_data['Close'].iloc[-1])

    # 検証ロジック
    if low_p > entry_price:
        result_title = "⚪ **未約定（ノーエントリー）**"
        result_desc = f"後場の最安値（{low_p:,}円）が買い指値（{entry_price:,}円）に届きませんでした。\n資金の変動・リスクは発生していません。"
    else:
        # 約定した場合
        if high_p >= take_profit:
            result_title = "🟢 **利確達成（勝ち）**"
            profit = take_profit - entry_price
            result_desc = f"買い約定後、目標高値（{take_profit:,}円）に到達しました！\n想定利益: **+{profit:,}円 (+3.0%)** （1口あたり）"
        elif low_p <= stop_loss:
            result_title = "🔴 **損切り執行（負け）**"
            loss = entry_price - stop_loss
            result_desc = f"買い約定後、損切りライン（{stop_loss:,}円）に到達し自動撤退しました。\n想定損失: **-{loss:,}円 (-1.5%)** （1口あたり）"
        else:
            diff = close_p - entry_price
            pct = round((diff / entry_price) * 100, 2)
            result_title = "🟡 **当日決済つかず（引け持ち越し）**"
            result_desc = f"後場中に利確・損切りラインのどちらにも達しませんでした。\n大引け終値: {close_p:,}円（含み損益: {pct}%）"

    msg = f"""📊 **【日経レバ(1570) 後場シミュレーション結果】**
昼の買い目安: {entry_price:,}円
後場レンジ: 安値 {low_p:,}円 〜 高値 {high_p:,}円

{result_title}
{result_desc}
"""
    send_discord(msg)

if __name__ == "__main__":
    jst = pytz.timezone('Asia/Tokyo')
    now = datetime.now(jst)
    
    # 昼（11時〜13時台）は昼速報、夕方（15時以降）は結果検証
    if now.hour < 14:
        job_lunch()
    else:
        job_after_market()
