# 部署到其他平台教程

本教程將指導您如何將 LINE Bot 預約系統部署到其他 Python 主機平台。

## 系統需求

### Python 環境
- Python 3.8 或更高版本
- pip（Python 套件管理工具）

### 必要的環境變數
- `LINE_CHANNEL_TOKEN` - LINE Messaging API 存取權杖
- `LINE_CHANNEL_SECRET` - LINE Channel 密鑰（用於 webhook 驗證）
- `GEMINI_API_KEY` - Google Gemini AI API 金鑰

## 部署步驟

### 1. 下載專案檔案

確保您有以下檔案：

```
project/
├── main.py                    # 主程式
├── database.py               # 資料庫管理
├── gemini_ai.py             # AI 排程建議
├── line_flex_messages.py    # LINE 訊息模板
├── templates/               # HTML 模板
│   ├── admin.html
│   ├── schedule.html
│   ├── appointments.html
│   └── closed_days.html
├── requirements.txt         # Python 依賴套件
└── appointments.db          # SQLite 資料庫（會自動創建）
```

### 2. 創建 requirements.txt

創建 `requirements.txt` 檔案，內容如下：

```txt
Flask==3.0.0
APScheduler==3.10.4
google-genai==1.0.0
pytz==2024.1
requests==2.31.0
```

### 3. 安裝依賴套件

在專案目錄執行：

```bash
pip install -r requirements.txt
```

或手動安裝：

```bash
pip install Flask APScheduler google-genai pytz requests
```

### 4. 設定環境變數

#### 方法 A：使用 .env 檔案（開發環境）

創建 `.env` 檔案：

```env
LINE_CHANNEL_TOKEN=你的LINE_CHANNEL_TOKEN
LINE_CHANNEL_SECRET=你的LINE_CHANNEL_SECRET
GEMINI_API_KEY=你的GEMINI_API_KEY
```

安裝 python-dotenv：

```bash
pip install python-dotenv
```

在 `main.py` 開頭添加：

```python
from dotenv import load_dotenv
load_dotenv()
```

#### 方法 B：直接設定系統環境變數（生產環境）

**Linux / macOS:**
```bash
export LINE_CHANNEL_TOKEN="你的TOKEN"
export LINE_CHANNEL_SECRET="你的SECRET"
export GEMINI_API_KEY="你的API_KEY"
```

**Windows:**
```cmd
set LINE_CHANNEL_TOKEN=你的TOKEN
set LINE_CHANNEL_SECRET=你的SECRET
set GEMINI_API_KEY=你的API_KEY
```

### 5. 初始化資料庫

首次執行時，資料庫會自動初始化：

```bash
python main.py
```

您應該看到：
```
✅ 数据库初始化完成
🚀 排程檢查器已啟動，每30秒檢查一次待發送訊息
 * Running on http://0.0.0.0:5000
```

## 平台特定部署指南

### Heroku 部署

1. **安裝 Heroku CLI**
   ```bash
   # macOS
   brew install heroku/brew/heroku
   
   # Windows
   # 下載安裝器：https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **創建 Heroku 應用**
   ```bash
   heroku create 你的應用名稱
   ```

3. **創建 Procfile**
   ```
   web: gunicorn main:app
   ```

4. **添加 Gunicorn 到 requirements.txt**
   ```
   gunicorn==21.2.0
   ```

5. **設定環境變數**
   ```bash
   heroku config:set LINE_CHANNEL_TOKEN=你的TOKEN
   heroku config:set LINE_CHANNEL_SECRET=你的SECRET
   heroku config:set GEMINI_API_KEY=你的API_KEY
   ```

6. **部署**
   ```bash
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

7. **設定 LINE Webhook**
   ```
   https://你的應用名稱.herokuapp.com/webhook
   ```

### PythonAnywhere 部署

1. **上傳檔案**
   - 使用 FTP 或 Git 上傳所有檔案到 `/home/你的用戶名/mysite/`

2. **安裝依賴**
   ```bash
   pip3 install --user -r requirements.txt
   ```

3. **創建 WSGI 設定**
   
   在 Web 標籤中設定 WSGI configuration file：
   
   ```python
   import sys
   import os
   
   # 添加專案路徑
   path = '/home/你的用戶名/mysite'
   if path not in sys.path:
       sys.path.append(path)
   
   # 設定環境變數
   os.environ['LINE_CHANNEL_TOKEN'] = '你的TOKEN'
   os.environ['LINE_CHANNEL_SECRET'] = '你的SECRET'
   os.environ['GEMINI_API_KEY'] = '你的API_KEY'
   
   from main import app as application
   ```

4. **重新載入應用**
   - 點擊 "Reload" 按鈕

5. **設定 LINE Webhook**
   ```
   https://你的用戶名.pythonanywhere.com/webhook
   ```

### AWS EC2 / VPS 部署

1. **更新系統並安裝 Python**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv
   ```

2. **創建虛擬環境**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **安裝依賴**
   ```bash
   pip install -r requirements.txt
   pip install gunicorn
   ```

4. **創建 systemd 服務**
   
   創建 `/etc/systemd/system/linebot.service`：
   
   ```ini
   [Unit]
   Description=LINE Bot Appointment System
   After=network.target
   
   [Service]
   User=你的用戶名
   WorkingDirectory=/home/你的用戶名/linebot
   Environment="LINE_CHANNEL_TOKEN=你的TOKEN"
   Environment="LINE_CHANNEL_SECRET=你的SECRET"
   Environment="GEMINI_API_KEY=你的API_KEY"
   ExecStart=/home/你的用戶名/linebot/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 main:app
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```

5. **啟動服務**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start linebot
   sudo systemctl enable linebot
   ```

6. **設定 Nginx 反向代理**
   
   創建 `/etc/nginx/sites-available/linebot`：
   
   ```nginx
   server {
       listen 80;
       server_name 你的域名.com;
       
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```
   
   啟用設定：
   ```bash
   sudo ln -s /etc/nginx/sites-available/linebot /etc/nginx/sites-enabled/
   sudo systemctl restart nginx
   ```

7. **設定 SSL（Let's Encrypt）**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d 你的域名.com
   ```

8. **設定 LINE Webhook**
   ```
   https://你的域名.com/webhook
   ```

## 開啟前台管理介面

部署完成後，您可以通過以下 URL 訪問各個管理頁面：

```
https://你的域名/              # 用戶管理
https://你的域名/schedule      # 排程管理
https://你的域名/appointments  # 預約管理
https://你的域名/closed_days   # 休診管理
```

## 設定 LINE Webhook

1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 選擇您的 Channel
3. 在 "Messaging API" 標籤中：
   - **Webhook URL**: 輸入您的 webhook URL
   - **Use webhook**: 啟用
   - **Verify**: 點擊驗證（應該顯示成功）

## 監控與維護

### 查看日誌

```bash
# systemd 服務日誌
sudo journalctl -u linebot -f

# Nginx 日誌
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 備份資料庫

**手動備份：**
```bash
cp appointments.db appointments_backup_$(date +%Y%m%d).db
```

**自動備份（使用 crontab）：**

編輯 crontab：
```bash
crontab -e
```

添加以下行（每天凌晨2點自動備份）：
```cron
0 2 * * * cp /path/to/appointments.db /path/to/backup/appointments_$(date +\%Y\%m\%d).db
```

### 更新代碼

```bash
git pull origin main
sudo systemctl restart linebot
```

## 常見問題

### Q: Webhook 驗證失敗？

**解決方法：**
1. 確認 `LINE_CHANNEL_SECRET` 設定正確
2. 檢查 HTTPS 是否正確設定
3. 確認防火牆允許外部訪問

### Q: 資料庫檔案在哪裡？

**答：** `appointments.db` 會在專案根目錄自動創建。

### Q: 如何重置資料庫？

**答：** 刪除 `appointments.db` 並重啟應用，系統會自動重新初始化。

### Q: 排程器沒有運行？

**解決方法：**
1. 確認 APScheduler 已正確安裝
2. 檢查系統日誌查看錯誤訊息
3. 確認應用持續運行（不是短時間執行的腳本）

## 效能優化建議

1. **使用 Gunicorn 多 worker**
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 main:app
   ```

2. **啟用 Nginx 快取**
3. **定期清理舊預約記錄**
4. **使用 Redis 快取（進階）**

## 安全建議

1. ✅ 使用 HTTPS（必須）
2. ✅ 不要將密鑰寫入代碼
3. ✅ 定期更新依賴套件
4. ✅ 限制管理介面訪問（設定認證）
5. ✅ 定期備份資料庫

## 參考資源

- [Flask 部署指南](https://flask.palletsprojects.com/en/3.0.x/deploying/)
- [Gunicorn 文件](https://docs.gunicorn.org/)
- [LINE Webhook 設定](https://developers.line.biz/en/docs/messaging-api/building-bot/#page-title)
