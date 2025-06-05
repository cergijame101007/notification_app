from fastapi import FastAPI, HTTPException, Depends, Request
import uvicorn
from pydantic import BaseModel
import json
from pathlib import Path
import requests
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import logging
import smtplib
from email.mime.text import MIMEText
from fastapi_utils.tasks import repeat_every
from collections import defaultdict

from fastapi.middleware.cors import CORSMiddleware

import os
from dotenv import load_dotenv

from models import Base, engine, SessionLocal, Temperature
from sqlalchemy.orm import Session

from fastapi.staticfiles import StaticFiles

app = FastAPI()

load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "temperature_log.txt")

NOTIFY_FLAG_FILE = Path("notified.flag")
if not NOTIFY_FLAG_FILE.exists():
    NOTIFY_FLAG_FILE.write_text("0")  

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

"""
テスト環境下では255℃ (任意の温度)
本番環境では900℃
"""
THRESHOLD = 255

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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

logging.basicConfig(
    filename=LOG_FILE,
    level=LEVEL_MAP.get(LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_message(level, message):
    """
    指定されたログレベルでメッセージを記録し、同時にターミナル出力にも表示する

    Args:
        level (str): ログレベル("info"または"error")
        message (str): ログメッセージ
    """
    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)
    print(message)

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
    subject = "Accumulative temperature alert"
    body = f"""The accumulative temperature has exceeded thershold: {THRESHOLD}\n
    Current accumulative temperature: {accumulative_temperature}℃"""

    msg = MIMEText(body)
    msg["subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, app_password)
            server.send_message(msg)
        log_message("info", "\u2705 email sent succesfully")
        NOTIFY_FLAG_FILE.write_text("1")
    except Exception as e:
        log_message("error",f"\u274C email sending error: {e}")

def calculate_accumulative_temperature(db: Session):
    """
    データベース上の温度データから積算温度を計算する

    Returns:
        dict: 現在の積算温度と最大温度リスト(タイムスタンプ付き) 
    """
    records = db.query(Temperature).order_by(Temperature.timestamp).all()
    
    if not records:
        log_message("info", "No valid data:")
        return {"accumulative_temperature": 0, "max_points": []}

    accumulative_temperature = 0
    max_points = []

    start_time = datetime.strptime(records[0].timestamp, "%Y-%m-%d %H:%M:%S")
    interval_end = start_time + timedelta(minutes=5)

    interval_temperature_max = float("-inf")

    max_temperature_time = None

    for record_i in records:
        record_time = datetime.strptime(record_i.timestamp, "%Y-%m-%d %H:%M:%S")

        if record_time <= interval_end:
            if record_i.temperature > interval_temperature_max:
                interval_temperature_max = record_i.temperature
                max_temperature_time = record_time
        else:
            if interval_temperature_max != float("-inf"):
                accumulative_temperature += interval_temperature_max
                max_points.append((
                    max_temperature_time.strftime("%Y-%m-%d %H:%M:%S"), 
                    interval_temperature_max
                ))
            
            while record_time > interval_end:
                interval_end += timedelta(minutes=5)      

            interval_temperature_max = record_i.temperature
            max_temperature_time = record_time
        
    if interval_temperature_max != float("-inf"):
        accumulative_temperature += interval_temperature_max
        max_points.append((
            max_temperature_time.strftime("%Y-%m-%d %H:%M:%S"), 
            interval_temperature_max
    ))

    log_message("info", f"current accumulative temperature: {accumulative_temperature}℃")
    is_notified = NOTIFY_FLAG_FILE.read_text().strip() == "1"
    if accumulative_temperature > THRESHOLD and not is_notified:
        log_message("info", "threshold exceeded, send Gmail notification")
        gmail_notification(accumulative_temperature)

    return {
        "accumulative_temperature": accumulative_temperature, 
        "max_points": max_points
    }

def calculate_accumulative_temperature_production_env(db: Session):
    records = db.query(Temperature).order_by(Temperature.timestamp).all()

    if not records:
        log_message("info", "No valid data:")
        return {"accumulative_temperature": 0, "max_points": []}

    daily_max = defaultdict(lambda: float("-inf"))
    """上の行と同じ意味
    if date_str not in daily_max:
    daily_max[date_str] = float("-inf")
    daily_max[date_str] = max(daily_max[date_str], record_1.temperature)
    """

    for record_i in records:
    # あとで" "を""T"に直す(他の部分＋ラズパイサイド)
        date_str = record_i.timestamp.split(" ")[0]
        daily_max[date_str] = max(daily_max[date_str], record_i.temperature)

    daily_max_points = sorted(daily_max.items())  # 日付順に並べる
    accumulative_temperature = sum(temp for _, temp in daily_max_points)

    log_message("info", f"accumulative temperature: {accumulative_temperature}℃")
    is_notified = NOTIFY_FLAG_FILE.read_text().strip() == "1"
    if accumulative_temperature > THRESHOLD and not is_notified:
        log_message("info", "threshold exceeded, send Gmail notification")
        gmail_notification(accumulative_temperature)

    return {
        "accumulative_temperature": accumulative_temperature, 
        "max_points": daily_max_points
    }

@app.post("/temperature/")
async def save_temperature(data: TemperatureData, db: Session = Depends(get_db)):
    """
    温度データを受け取り、ファイルに保存

    Args:
        data (TemperatureData): タイムスタンプと温度データ

    Returns:
        dict: 保存成功メッセージ
    """

    try:
        new_temp = Temperature(
            timestamp=data.timestamp,
            temperature=data.temperature
        )
        db.add(new_temp)
        db.commit()
        db.refresh(new_temp)

        return {
            "message": "Data saved successfully",
            "id": new_temp.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/temperature/")
async def get_temperature(db: Session = Depends(get_db)):
    """
    保存されているすべての温度データを返します。

    Returns:
        list: 温度データのリスト
    """

    try:
        temperatures = db.query(Temperature).all()
        return [
            {
                "timestamp": table_i.timestamp,
                "temperature": table_i.temperature
            }
            for table_i in temperatures
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/accumulative_temperature/")
async def get_accumulative_temperature(db: Session = Depends(get_db)):
    """
    現在の積算温度とその構成要素を返します。

    Returns:
        dict: 積算温度と最大点のリスト
    """
    try:
        return calculate_accumulative_temperature(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/temperature/reset/")
async def reset_temperature(db: Session = Depends(get_db)):
    """
    保存されている温度データと通知状態を初期化します。

    Returns:
        dict: リセット成功メッセージ
    """
    try:
        db.query(Temperature).delete()
        db.commit()
        NOTIFY_FLAG_FILE.write_text("0")
        return {"message": "Data has been reset successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.on_event("startup")
@repeat_every(seconds=300)  
async def accumulative_temperature_check(db: Session = Depends(get_db)):
    """
    アプリ起動時から300秒ごとに積算温度を自動でチェックします。

    Returns:
        None
    """
    log_message("info", "check accumulative temperature")
    calculate_accumulative_temperature(db)

@app.get("/view")
async def render_view(request: Request):
    return templates.TemplateResponse("view.html", {"request": request})
 
Base.metadata.create_all(bind=engine)
