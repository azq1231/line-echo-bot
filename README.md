﻿# LINE 預約管理機器人 (LINE Appointment Booking Bot)

這是一個圍繞 LINE 平台建立的綜合性預約及後台管理系統。它為客戶提供了一個方便的 LINE 機器人來進行預約、查詢和取消，同時為管理員提供了一個功能強大的網頁後台來管理預約、使用者和系統設定。

後台管理介面採用了現代化的前後端分離架構，前端由 Vue.js 驅動，後端由 Python Flask 提供 API 服務。

 <!-- 建議替換成您的預約簿截圖 -->

---

## ✨ 主要功能

### 👤 使用者端 (透過 LINE 機器人)
- **互動式預約流程**：透過 Flex Message 進行視覺化的日期與時間選擇。
- **查詢我的預約**：使用者可以隨時查詢未來的預約記錄。
- **一鍵取消預約**：透過簡單的指令或按鈕快速取消預約。
- **智慧預約提醒**：自動合併使用者在同一天的多個預約，並發送單一則提醒訊息，提供最佳體驗。

### ⚙️ 管理員端 (網頁後台)
- **Vue.js 預約簿**：動態、響應式的週曆格線，清晰展示所有預約時段。
- **拖曳操作**：可將「備取名單」中的使用者直接拖曳到空的預約時段中。
- **使用者管理**：
  - 瀏覽所有與機器人互動過的使用者。
  - 授予或移除管理員權限。
  - 手動新增臨時用戶（用於電話預約等場景）。
  - 合併重複的使用者帳號。
- **排程設定**：
  - 自訂每週各天的可用預約時段區間。
  - 設定休診日，自動取消當天所有預約並防止新的預約。
- **系統設定**：
  - 功能開關：動態啟用或停用特定功能模組。
  - 設定自動提醒的排程時間（每日提醒、每週提醒）。
- **手動發送提醒**：可針對特定一天或一整週手動觸發預約提醒。
- **訊息統計**：追蹤不同類型訊息（提醒、預約成功等）的發送狀況。

---

## 🛠️ 技術棧

- **後端**: Python, Flask, APScheduler
- **前端**: Vue.js 3 (Composition API), Vite, Tailwind CSS, Axios
- **資料庫**: SQLite
- **平台**: LINE Messaging API, LINE Login
- **部署**: Gunicorn (建議), Nginx (建議)

---
## 📂 專案結構

本專案採用「應用程式工廠」模式，實現了高度的模組化與關注點分離。

```
line-echo-bot/
├── main.py                # 應用程式啟動檔 (保持輕量)
├── app/
│   ├── __init__.py        # Flask App 工廠函式 (create_app)
│   ├── routes/            # 路由模組 (Blueprints)
│   │   ├── admin/         # Admin 相關路由
│   │   ├── auth.py        # 登入、登出、Callback
│   │   └── ...
│   ├── utils/             # 工具函式模組
│   │   ├── decorators.py  # 裝飾器
│   │   ├── helpers.py     # 通用輔助函式
│   │   └── line_api.py    # LINE API 相關函式
│   └── scheduler/         # APScheduler 排程器模組
│       ├── __init__.py
│       ├── jobs.py
│       └── utils.py
├── frontend/              # 前端 Vue.js 專案源碼
├── static/                # Vue.js 打包後的靜態檔案
├── templates/             # Flask/Jinja2 模板
└── ... (其他設定檔如 .env, database.py)
```

---

## 🚀 快速啟動

### 1. 環境準備
- Python 3.8+
- Node.js 18+ 和 npm

### 2. 後端設定

```bash
# 1. 複製專案
git clone https://github.com/your-username/line-echo-bot.git
cd line-echo-bot

# 2. 建立並啟用虛擬環境 (Windows)
python -m venv venv
venv\Scripts\activate

# 3. 安裝 Python 依賴套件
pip install -r requirements.txt

# 4. 設定環境變數
# 在專案根目錄建立一個名為 .env 的檔案，並填入以下內容：
```

`.env`:
```ini
FLASK_SECRET_KEY='一個超級安全的隨機字串'
LINE_CHANNEL_TOKEN='您的 Channel access token'
LINE_CHANNEL_SECRET='您的 Channel secret'
LINE_LOGIN_CHANNEL_ID='您的 LINE Login Channel ID'
LINE_LOGIN_CHANNEL_SECRET='您的 LINE Login Channel Secret'
GEMINI_API_KEY='您的 Gemini API Key (如果使用)'
```

### 3. 前端設定

```bash
# 1. 進入前端目錄
cd frontend

# 2. 安裝 Node.js 依賴套件
npm install

# 3. (可選) 編譯前端專案
# 在生產模式或本地測試打包版本時執行。開發時可跳過此步。
npm run build
```

### 4. 啟動應用程式

#### 開發模式 (建議)

1.  **啟動後端 (Flask)**：
    ```bash
    # 在專案根目錄
    venv\Scripts\activate
    python main.py
    ```
2.  **啟動前端 (Vite)**：
    ```bash
    # 開啟一個新的終端機
    cd frontend
    npm run dev
    ```
    在開發模式下，請訪問 Vite 提供的網址 (例如 `http://localhost:5173/admin/appointments`) 來查看前端頁面，它會自動代理 API 請求到後端。

### 5. 設定第一位管理員

首次設定時，您需要透過指令列來指定第一位管理員。

1.  **建立您的使用者資料**：
    *   啟動後端與前端開發伺服器。
    *   使用您自己的 LINE 帳號加入機器人好友。
    *   訪問任一需要登入的頁面 (例如 `http://localhost:5000/`) 並使用 LINE 登入。此步驟會將您的 LINE User ID 寫入資料庫。

2.  **執行設定指令**：
    *   開啟一個**新的終端機**。
    *   進入專案根目錄並啟用虛擬環境：
        ```bash
        # Windows
        venv\Scripts\activate
        ```
    *   執行以下指令來設定管理員：
        > **注意**：在 Windows 中，您需要分兩步執行：先設定環境變數，再執行指令。
        ```powershell
        # 如果您使用傳統的命令提示字元 (cmd.exe)，請用 'set'
        set FLASK_APP=main.py
        flask set-admin

        # 如果您使用 PowerShell (建議)，請用 '$env:'
        $env:FLASK_APP = "main.py"
        flask set-admin
        ```
    *   程式會列出所有已存在的使用者。根據提示，輸入您自己帳號對應的數字編號，然後按下 Enter。

3.  **完成設定**：
    *   完成後，您就可以使用該 LINE 帳號登入後台管理頁面 (例如 `http://localhost:5173/admin/users_vue`)，並擁有管理員權限。

---

## 📜 部署範例 (使用 systemd)

您可以建立一個 systemd 服務檔案來管理您的應用程式。

`sudo nano /etc/systemd/system/mywebsite.service`:
```ini
[Unit]
Description=Gunicorn instance for LINE Appointment Bot
After=network.target

[Service]
User=root # 或者您指定的非 root 使用者
WorkingDirectory=/var/www/myapp # 您的專案路徑

# 直接指定 .env 檔案的路徑，systemd 會自動載入所有變數
EnvironmentFile=/var/www/myapp/.env

# 確保 gunicorn 從虛擬環境中執行。
# --preload 參數是關鍵，它會讓 Gunicorn 在主進程中預先載入應用，
# 確保排程器 (APScheduler) 只會被初始化一次，避免重複執行排程任務。
ExecStart=/var/www/myapp/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:8000 --preload main:app

[Install]
WantedBy=multi-user.target
```

**管理服務**
```bash
# 首次設定或修改後執行
sudo systemctl daemon-reload

sudo systemctl start mywebsite
sudo systemctl enable mywebsite
sudo systemctl status mywebsite
```