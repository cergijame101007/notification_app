from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
import json
from pathlib import Path
import requests
from datetime import datetime, timedelta

import smtplib
from email.mime.text import MIMEText
from fastapi_utils.tasks import repeat_every

from fastapi.middleware.cors import CORSMiddleware

import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
DATA_FILE = Path("temperature_data.json")
NOTIFY_FLAG_FILE = Path("notified.flag")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not DATA_FILE.exists():
    DATA_FILE.write_text("[]")  
if not NOTIFY_FLAG_FILE.exists():
    NOTIFY_FLAG_FILE.write_text("0")  

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TemperatureData(BaseModel):
    """
    温度データのモデル

    Attributes:
        timestamp (str): 測定時刻 ("YYYY-MM-DD HH:MM:SS")
        temperature (float): 測定温度 (℃)
    """
    timestamp: str  
    temperature: float  

def gmail_notification(accumulative_temperature):
    """
    積算温度が基準値を超えた場合に、Gmailを使って通知を送信

    Args:
        accumulative_temperature (float): 現在の積算温度(℃)
    Returns:
        None
    """
    sender = EMAIL_ADDRESS
    app_password = EMAIL_PASSWORD
    receiver = EMAIL_ADDRESS
    subject = "積算温度アラート"
    body = f"積算温度が基準値に到達しました！\n現在の積算温度：{accumulative_temperature}℃"

    msg = MIMEText(body)
    msg["subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.send_message(msg)
        print("\u2705 メール送信に成功しました")
        NOTIFY_FLAG_FILE.write_text("1")
    except Exception as e:
        print(f"\u274C メール送信エラー: {e}")

def process_data():
    """_summary_
    保存されている温度データを読み取り、時刻と温度を分離して返す

    Returns:
        tuple: floatリストのタプル(timestamps, temperatures)
    """
    try:
        data = json.loads(DATA_FILE.read_text())
        timestamps, temperatures = [], []
        
        for entry in data:
            try:
                timestamps.append(datetime.strptime(entry['timestamp'].strip(), "%Y-%m-%d %H:%M:%S"))
                temperatures.append(entry['temperature'])
            except (KeyError, ValueError) as e:
                print(f"データ処理エラー: {entry} → {e}")
        return timestamps, temperatures
    except Exception as e:
        print(f"データ読み込みエラー: {e}")
        return [], []

def calculate_accumulative_temperature():
    """
    5分ごとの最大温度を積算し、条件を満たす場合に通知を行います。

    Returns:
        dict: 現在の積算温度と最大温度リスト(タイムスタンプ付き) 
    """
    timestamps, temperatures = process_data()
    interval = 5
    
    if not timestamps or not temperatures:
        print("有効なデータがありません")
        return {"accumulative_temperature": 0, "max_points": []}

    accumulative_temperature = 0
    max_points = []

    start_time = timestamps[0]
    interval_end = start_time + timedelta(minutes=interval)
    temp_max = float('-inf')
    max_time = None

    for time, temp in zip(timestamps, temperatures):
        if time <= interval_end:
            if temp > temp_max:
                temp_max = temp
                max_time = time
        else:
            if temp_max != float('-inf'):
                accumulative_temperature += temp_max
                max_points.append((max_time, temp_max))
            interval_end += timedelta(minutes=interval)
            temp_max = temp
            max_time = time

    if temp_max != float('-inf'):
        accumulative_temperature += temp_max
        max_points.append((max_time, temp_max))

    print(f"現在の積算温度: {accumulative_temperature}℃")
    is_notified = NOTIFY_FLAG_FILE.read_text().strip() == "1"
    if accumulative_temperature > 255 and not is_notified:
        print("\u26a0 基準値を超えたため、Gmail通知を送信")
        gmail_notification(accumulative_temperature)

    return {"accumulative_temperature": accumulative_temperature, "max_points": max_points}

"""データをサーバーに保存"""
@app.post("/temperature/")
async def save_temperature(data: TemperatureData):
    """
    温度データを受け取り、ファイルに保存

    Args:
        data (TemperatureData): タイムスタンプと温度データ

    Returns:
        dict: 保存成功メッセージ
    """
    try:
        existing_data = json.loads(DATA_FILE.read_text())
        existing_data.append(data.dict())
        DATA_FILE.write_text(json.dumps(existing_data, indent=4))
        return {"message": "Data saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""サーバーからデータを取得"""
@app.get("/temperature/")
async def get_temperature():
    """
    保存されているすべての温度データを返します。

    Returns:
        list: 温度データのリスト
    """
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""サーバーから積算温度データを取得"""
@app.get("/accumulative_temperature/")
async def get_accumulative_temperature():
    """
    現在の積算温度とその構成要素を返します。

    Returns:
        dict: 積算温度と最大点のリスト
    """
    try:
        return calculate_accumulative_temperature()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""サーバーに保存されているデータのリセット"""
@app.delete("/temperature/reset/")
async def reset_temperature():
    """
    保存されている温度データと通知状態を初期化します。

    Returns:
        dict: リセット成功メッセージ
    """
    try:
        DATA_FILE.write_text("[]")
        global accumulative_temperature
        accumulative_temperature = 0
        NOTIFY_FLAG_FILE.write_text("0")
        return {"message": "Data has been reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.on_event("startup")
@repeat_every(seconds=300)  
async def accumulative_temperature_check():
    """
    アプリ起動時から300秒ごとに積算温度を自動でチェックします。

    Returns:
        None
    """
    print("自動で積算温度をチェック中")
    calculate_accumulative_temperature()
    print("アドレス:", EMAIL_ADDRESS)
    print("パスワード:", EMAIL_PASSWORD)
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)