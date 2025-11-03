LINE Bot 預約系統部署指南（簡化版）

本指南適合本地測試與VPS 部署，不需要域名、反向代理或 SSL，也不包含雲端平台。

系統需求
Python 環境

Python 3.8 或以上

pip

必要環境變數

LINE_CHANNEL_TOKEN

LINE_CHANNEL_SECRET
LINE_LOGIN_CHANNEL_ID
LINE_LOGIN_CHANNEL_SECRET
FLASK_SECRET_KEY

GEMINI_API_KEY

專案結構範例
project/
├── main.py
├── database.py
├── gemini_ai.py
├── line_flex_messages.py
├── templates/
│   ├── admin.html
│   ├── schedule.html
│   ├── appointments.html
│   └── closed_days.html
├── requirements.txt
└── appointments.db

建議 requirements.txt
Flask==3.0.0
APScheduler==3.10.4
google-genai==1.0.0
pytz==2024.1
requests==2.31.0
gunicorn==23.0.0
python-dotenv==1.0.0

一、本地測試
1. 安裝依賴
pip install -r requirements.txt

2. 設定環境變數

**建議方法：使用 .env 檔案**

在您的專案根目錄（`/var/www/myapp`）建立一個名為 `.env` 的檔案，內容如下：

LINE_CHANNEL_TOKEN=你的TOKEN
LINE_CHANNEL_SECRET=你的SECRET
LINE_LOGIN_CHANNEL_ID=你的LINE登入頻道ID
LINE_LOGIN_CHANNEL_SECRET=你的LINE登入頻道密鑰
FLASK_SECRET_KEY=你的Flask應用密鑰(一個隨機的長字串)
GEMINI_API_KEY=你的API_KEY

在 main.py 開頭加：

from dotenv import load_dotenv
load_dotenv()


**替代方法：設定系統環境變數**

export LINE_CHANNEL_TOKEN="你的TOKEN"
export LINE_CHANNEL_SECRET="你的SECRET"
export LINE_LOGIN_CHANNEL_ID="你的LINE登入頻道ID"
export LINE_LOGIN_CHANNEL_SECRET="你的LINE登入頻道密鑰"
export FLASK_SECRET_KEY="你的Flask應用密鑰(一個隨機的長字串)"
export GEMINI_API_KEY="你的API_KEY"

3. 啟動 Flask
python main.py


預設監聽 5000 連接埠

可用 curl http://127.0.0.1:5000 測試服務

4. (可選) ngrok 本地測試 LINE Webhook
ngrok http 5000


將生成的 HTTPS 網址填入 LINE Webhook URL

二、VPS 部署（不含域名與 SSL）
1. 系統準備
apt update
apt install -y git python3-venv

2. 下載專案
mkdir -p /var/www/myapp
cd /var/www/
git clone https://github.com/azq1231/line-echo-bot.git myapp

3. 建立虛擬環境
cd /var/www/myapp
python3 -m venv venv
source venv/bin/activate

4. 安裝依賴
pip install -r requirements.txt

5. 建立並編輯 .env 檔案
nano .env
# 將您在本地測試用的 .env 內容貼上

6. 啟動服務
source venv/bin/activate
python main.py


預設監聽 5000

可用 curl http://127.0.0.1:5000 測試

7. Gunicorn + systemd（建議生產環境使用）

建立 /etc/systemd/system/mywebsite.service：

[Unit]
Description=Gunicorn instance for my website
After=network.target

[Service]
User=root # 或者您指定的非 root 使用者
WorkingDirectory=/var/www/myapp
# 直接指定 .env 檔案的路徑，systemd 會自動載入所有變數
EnvironmentFile=/var/www/myapp/.env

# 確保 gunicorn 從虛擬環境中執行。
# --preload 參數是關鍵，它會讓 Gunicorn 在主進程中預先載入應用，
# 確保排程器 (APScheduler) 只會被初始化一次，避免重複執行排程任務。
ExecStart=/var/www/myapp/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 --preload main:app
Restart=always

[Install]
WantedBy=multi-user.target
```

啟動服務：
```bash
sudo systemctl daemon-reload
sudo systemctl start mywebsite
sudo systemctl enable mywebsite
```

## 三、前台管理介面

*   `http://VPS_IP:5000/` - 用戶管理
*   `http://VPS_IP:5000/schedule` - 排程管理
*   `http://VPS_IP:5000/appointments` - 預約簿
*   `http://VPS_IP:5000/closed_days` - 休診管理
*   `http://VPS_IP:5000/stats` - 訊息統計
*   `http://VPS_IP:5000/configs` - 系統設定

## 四、日常維護

*   **查看日誌**: `sudo journalctl -u mywebsite -f`
*   **只顯示50條**: `sudo journalctl -u mywebsite -n 50 --no-pager`
*   **備份資料庫**: `cp /var/www/myapp/appointments.db /var/www/myapp/appointments_backup_$(date +%Y%m%d).db`
*   **更新代碼**:
    ```bash
    cd /var/www/myapp
    git pull origin main
    sudo systemctl restart mywebsite
    ```

## 五、常見問題

*   **Webhook 驗證失敗**: 確認 `LINE_CHANNEL_SECRET` 正確，且伺服器的防火牆已開放 5000 連接埠。
*   **資料庫檔案位置**: `appointments.db` 預設會建立在專案的根目錄 (`/var/www/myapp`)。
*   **重置資料庫**: 刪除 `appointments.db` 檔案並重啟應用程式，系統會自動重新建立一個空的資料庫。
*   **排程器未運行**: 確認 `APScheduler` 已正確安裝，並透過 `sudo journalctl -u mywebsite` 檢查服務啟動日誌是否有錯誤。