from w1thermsensor import W1ThermSensor
import time
import json
import requests
import socket
import logging
import argparse
from pathlib import Path

SERVER_URL = "http://10.200.234.152:8000/temperature/"
LOCAL_BACKUP_FILE = Path("unsent_data.json")
INTERVAL = 30 

"""ログの記録"""
logging.basicConfig(filename="temperature_log.txt", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def log_message(level, message):
    """
    指定されたログレベルでメッセージを記録し、同時にターミナル出力にも表示する
    
    Args:
        level (str):ログレベル("info"`または"error")
        message (str):ログメッセージ
    """
    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)
    print(message)

def valid_temperature(temp):
    """
    測定値が異常範囲外かどうかを判定する。

    Args:
        temp (float): 測定温度(℃)

    Returns:
        bool: 正常な範囲(-10〜100℃)であれば True
    """
    return -10 <= temp <= 100

def connected():
    """
    インターネット接続が有効かを確認する。

    Returns:
        bool: 接続できれば True、できなければ False
    """
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

def save_unsent_data(data):
    """
    送信に失敗したデータをローカルファイルに保存する。

    Args:
        data (dict): 保存する温度データ（timestamp, temperature）
    """
    try:
        if not LOCAL_BACKUP_FILE.exists():
            LOCAL_BACKUP_FILE.write_text("[]")
        existing_data = json.loads(LOCAL_BACKUP_FILE.read_text())
        existing_data.append(data)
        LOCAL_BACKUP_FILE.write_text(json.dumps(existing_data, indent=4))
    except Exception as e:
        log_message("error", f"Error saving unsent data: {e}")

def load_unsent_data():
    """
    保存されている未送信データを読み込む。

    Returns:
        list: 未送信の温度データリスト
    """
    if not LOCAL_BACKUP_FILE.exists():
        return []
    return json.loads(LOCAL_BACKUP_FILE.read_text())

def clear_unsent_data():
    try:
        if LOCAL_BACKUP_FILE.exists():
            LOCAL_BACKUP_FILE.unlink()
    except Exception as e:
        log_message("error", f"Error clearing unsent data: {e}")

def send_to_server(data):
    """
    データをHTTP POSTリクエストでサーバーに送信する。

    Args:
        data (dict): 送信する温度データ

    Returns:
        bool: 成功すれば True、失敗すれば False
    """
    try:
        response = requests.post(SERVER_URL, json=data)
        response.raise_for_status()
        log_message("info", f"Data sent succesfully: {data}")
        return True
    except requests.exceptions.RequestException as e:
        log_message("error", f"Failed to send data to server: {e}")
        return False

def handle_arguments():
    """
    コマンドライン引数を処理する。

    Returns:
        argparse.Namespace: 引数オブジェクト
    """
    parser = argparse.ArgumentParser(description="Temperature monitoring script")
    parser.add_argument("--reset", action="store_true", help="Clear unsent data")
    return parser.parse_args()

def main():
    """
    温度センサーからのデータを定期的に取得し、サーバーに送信するメイン関数。
    送信失敗時はローカルに保存し、次回接続時に再送信を試みる。
    """
    args = handle_arguments()
    if args.reset:
        clear_unsent_data()
        print("Unsent data cleared.")
        exit()
    
    sensor = W1ThermSensor()
    log_message("info", "Starting temperature monitoring and data transmission...")
    
    while True:
        timestamp = time.strftime("%Y-%m-%d  %H:%M:%S", time.localtime())
        temperature = sensor.get_temperature()
        
        """異常値の検出"""
        if not valid_temperature(temperature):
            log_message("error", f"Invalid temperature detected: {temperature}")
            time.sleep(INTERVAL)
            continue
        
        data = {"timestamp": timestamp, "temperature": temperature}

        unsent_data = load_unsent_data()
        
        if connected(): #ネット接続がある場合
            for item in unsent_data:
                if send_to_server(item):
                    unsent_data.remove(item)

            if unsent_data:
                LOCAL_BACKUP_FILE.write_text(json.dumps(unsent_data, indent=4))
            else:
                clear_unsent_data()

            if not send_to_server(data):
                save_unsent_data(data)
        else: #ネット接続がない場合
            log_message("error", "No Internet connection.Saving data locally.")
            save_unsent_data(data)

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
