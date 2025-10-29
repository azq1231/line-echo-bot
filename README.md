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

## 🚀 安裝與啟動

### 環境準備
- Python 3.8+
- Node.js 16+ 和 npm

### 1. 複製專案
```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

### 2. 後端設定

```bash
# 建立並啟用虛擬環境
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

# 安裝 Python 依賴套件
pip install -r requirements.txt
```

#### 環境變數
複製 `.env.example` 為 `.env`，並填入您的 LINE Channel 和 Flask 的金鑰。
```.env
FLASK_SECRET_KEY='一個超級安全的隨機字串'
LINE_CHANNEL_TOKEN='您的 Channel access token'
LINE_CHANNEL_SECRET='您的 Channel secret'
LINE_LOGIN_CHANNEL_ID='您的 LINE Login Channel ID'
LINE_LOGIN_CHANNEL_SECRET='您的 LINE Login Channel Secret'
```

### 3. 前端設定

```bash
# 進入前端目錄
cd frontend

# 安裝 Node.js 依賴套件
npm install

# 編譯前端專案，產生靜態檔案到 /static 目錄
npm run build

# 返回專案根目錄
cd ..
```

### 4. 資料庫與管理員設定

```bash
# 首次執行時，程式會自動建立 appointments.db 資料庫檔案
python main.py

# (請先讓至少一個 LINE 帳號加入您的機器人好友，並登入一次網頁)

# 開啟另一個終端機，設定第一位管理員
venv\Scripts\activate
flask set-admin
```
按照提示選擇一位使用者設為管理員。

### 5. 啟動應用程式

#### 開發模式
1.  **啟動後端 (Flask)**：
    ```bash
    # 確保虛擬環境已啟用
    python main.py
    ```
2.  **啟動前端 (Vite Dev Server)**：
    ```bash
    # 開啟新終端機
    cd frontend
    npm run dev
    ```
    在開發模式下，請訪問 Vite 提供的網址 (例如 `http://localhost:5173`) 來查看前端頁面。

#### 生產模式
在生產環境中，請將 `.env` 中的 `FLASK_DEBUG` 設為 `false` 或移除。
```bash
# 直接執行 main.py 會以生產模式啟動，並啟用排程器
python main.py
```
建議使用 Gunicorn + Nginx 進行部署以獲得更好的效能和穩定性。

---

## 📜 部署範例 (使用 systemd)

您可以建立一個 systemd 服務檔案來管理您的應用程式。

`/etc/systemd/system/mywebsite.service`:
```ini
[Unit]
Description=Gunicorn instance for LINE Appointment Bot
After=network.target

[Service]
User=your_user
Group=www-data
WorkingDirectory=/path/to/your/project
Environment="PATH=/path/to/your/project/venv/bin"
# --preload 參數是關鍵，它會讓 Gunicorn 在主進程中預先載入應用，
# 確保排程器 (APScheduler) 只會被初始化一次，避免重複執行排程任務。
ExecStart=/path/to/your/project/venv/bin/gunicorn --workers 3 --bind unix:mywebsite.sock -m 007 --preload main:app

[Install]
WantedBy=multi-user.target
```

**管理服務**
```bash
sudo systemctl start mywebsite
sudo systemctl enable mywebsite
sudo systemctl status mywebsite
sudo systemctl restart mywebsite
```