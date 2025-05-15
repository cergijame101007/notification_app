# 積算温度通知アプリケーション - notificationApp

このアプリケーションは、太陽熱養生中の積算温度を自動で測定・記録・可視化し、閾値に到達した際に通知を行うシステムです。  
沖縄県で深刻化している赤土流出問題への対策として地被植物の植栽が進められており、その養生管理を支援する目的で開発されました。

## 使用技術
- Frontend: JavaScript
- Backend: Python, FastAPI
- Deploy: Render (Web Service)

## 構成

### RaspberryPi側
- DS18B20(温度センサ)から温度を取得
- main.py: 温度取得・送信

### サーバー側（Render上）
- server.py: 温度データの保存・取得・積算温度計算
- APIエンドポイント
  - `POST /temperature/`：データ登録
  - `GET /temperature/`：全データ取得
  - `GET /accumulative_temperature/`：積算温度取得
  - `DELETE /temperature/reset/`：記録リセット

### WEBフロントエンド
- Chart.js + JavaScript による温度グラフ可視化