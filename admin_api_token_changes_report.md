# Admin API Token 實作報告

## 目的
為了解決之前使用 Session Cookie 進行 API 驗證時，因 Cookie 過期或處理問題導致的驗證失敗，並提供更符合 API 設計原則、更安全且易於維護的驗證方式，我們實作了基於 `X-Admin-Token` 標頭的 API Token 驗證機制。

## 變更內容

### 1. 新增 `ADMIN_API_TOKEN` 配置
- **檔案**: `app/__init__.py`
- **說明**: 在 Flask 應用程式的初始化階段，從環境變數中讀取 `ADMIN_API_TOKEN` 的值，並將其儲存到 `app.config` 中。這確保了 Token 可以被應用程式全局訪問，並且可以透過環境變數進行安全管理。

  **修改前 (部分)**:
  ```python
      app.config['LINE_LOGIN_CHANNEL_SECRET'] = os.getenv("LINE_LOGIN_CHANNEL_SECRET")
      app.config['TAIPEI_TZ'] = pytz.timezone('Asia/Taipei')
  ```

  **修改後 (部分)**:
  ```python
      app.config['LINE_LOGIN_CHANNEL_SECRET'] = os.getenv("LINE_LOGIN_CHANNEL_SECRET")
      app.config['TAIPEI_TZ'] = pytz.timezone('Asia/Taipei')
      app.config['ADMIN_API_TOKEN'] = os.getenv("ADMIN_API_TOKEN") # 新增
  ```

### 2. 修改 `admin_required` 裝飾器以支援 API Token 驗證
- **檔案**: `app/utils/decorators.py`
- **說明**: `admin_required` 裝飾器現在會優先檢查傳入請求的 `X-Admin-Token` 標頭。
  - 如果請求是 API 請求 (`request.path.startswith('/api/')`) 並且提供了 `X-Admin-Token`：
    - 如果 Token 與 `app.config['ADMIN_API_TOKEN']` 匹配，則請求被視為已授權，並直接執行被裝飾的函數。
    - 如果 Token 不匹配，則返回 `401 Unauthorized` 錯誤。
  - 如果請求是 API 請求但未提供 `X-Admin-Token`，或者是非 API 請求，則回退到原有的基於 Session 的管理員驗證邏輯。

  **修改前 (部分)**:
  ```python
  def admin_required(f):
      @wraps(f)
      def decorated_function(*args, **kwargs):
          is_api_request = request.path.startswith('/api/')

          if 'user' not in session or 'user_id' not in session['user']:
              if is_api_request:
                  return api_response(error="未授權或登入逾時，請重新整理頁面並登入。", status_code=401)
              # ... (Session 驗證邏輯)
  ```

  **修改後 (部分)**:
  ```python
  from flask import request, session, redirect, url_for, flash, current_app # 導入 current_app

  def admin_required(f):
      @wraps(f)
      def decorated_function(*args, **kwargs):
          is_api_request = request.path.startswith('/api/')

          # --- API Token 驗證 (優先於 Session 驗證) ---
          if is_api_request:
              admin_token = request.headers.get("X-Admin-Token")
              if admin_token:
                  if admin_token == current_app.config.get("ADMIN_API_TOKEN"):
                      return f(*args, **kwargs)
                  else:
                      return api_response(error="API Token 無效。", status_code=401)
              # 如果沒有提供 API Token，則繼續執行 Session 驗證

          # --- Session 驗證 (針對網頁請求或未提供 API Token 的 API 請求) ---
          if 'user' not in session or 'user_id' not in session['user']:
              if is_api_request:
                  return api_response(error="未授權或登入逾時，請重新整理頁面並登入。", status_code=401)
              # ... (Session 驗證邏輯)
  ```

## 使用方式
1.  **設定 `ADMIN_API_TOKEN`**：
    如果您的 Flask 應用程式使用 `python-dotenv` (例如在 `app/__init__.py` 中有 `load_dotenv()`)，您應該將 `ADMIN_API_TOKEN` 寫入您的 `.env` 檔案中，例如：
    ```
    ADMIN_API_TOKEN="MySuperSecretToken123"
    ```
    請確保這個 token 是安全的隨機字串。
    **重要提示**：對於由 `systemd` 服務管理的應用程式，直接在 shell 中使用 `export` 設定的環境變數不會被服務載入。必須將其寫入 `.env` 檔案或在 `systemd` 服務檔案中明確設定。
2.  **重新啟動您的 Flask 應用程式**：
    例如，如果您的服務名稱是 `mywebsite.service`，請執行 `sudo systemctl restart mywebsite`。這樣新的配置（`ADMIN_API_TOKEN`）和修改後的驗證邏輯才能生效。
3.  **使用更新後的 PowerShell 命令觸發任務**：
    請參考 `test_daily_reminder_instructions.md` 檔案中的最新命令，並將 `X-Admin-Token` 替換為您在 `.env` 檔案中設定的實際 token。

這個新的驗證機制將提供更穩定和安全的 API 呼叫方式，特別適用於自動化腳本和 CLI 工具。
