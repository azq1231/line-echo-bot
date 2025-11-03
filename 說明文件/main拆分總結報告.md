# 專案結構模組化重構報告

## 1. 概述 (Project Overview)

本次重構將原有的 Flask 應用程式轉換為更具擴展性的**「應用程式工廠 (Application Factory)」模式，目的是提升專案的可維護性**、可讀性與職責分離，為專案的長期發展打下堅實基礎。

重構後實現了高度的「關注點分離 (Separation of Concerns)」。

## 2. 核心模組職責說明 (Core Module Responsibilities)

| 檔案/目錄 | 職責 | 說明 |
|---|---|---|
| `main.py` | 應用程式啟動點 | 唯一入口點，只包含極少的程式碼，負責導入並呼叫 `create_app` 啟動開發伺服器。 |
| `app/__init__.py` | **應用程式工廠** | 定義 `create_app` 函式，集中處理應用程式級別的初始化工作 (如：載入設定、初始化資料庫、設定日誌、註冊所有藍圖，以及根據環境決定是否啟動排程器)。 |
| `app/routes/` | **路由模組** | 存放所有路由邏輯 (`@app.route`)，按功能拆分成不同的藍圖 (Blueprints)。 |
| `app/utils/` | **工具函式** | 存放可在專案中重複使用的輔助函式，與具體的路由邏輯解耦。 |
| `app/scheduler.py` | **排程器** | 負責初始化 APScheduler，並將排程工作加入到調度器中。 |

## 3. 路由 (`app/routes/`) 拆分細節

所有路由按功能拆分，以藍圖形式註冊到應用程式工廠中：

| 檔案 | 負責路由 | 說明 |
|---|---|---|
| `auth.py` | `/login`, `/callback`, `/logout` | 處理 LINE Login 相關的認證流程。 |
| `booking.py` | `/`, `/history`, `/api/book_appointment` | 處理使用者端的預約頁面、歷史紀錄與相關 API。 |
| `webhook.py` | `/webhook` | 接收並處理來自 LINE Platform 的 Webhook 事件。 |
| `user.py` | `/users/user_avatar/...` | 處理與用戶個人資料相關的 API，例如獲取頭像。 |
| `admin/` (子目錄) | `/admin/...`, `/api/admin/...` | 組織所有管理後台的頁面與 API，是本次拆分的重點。 |

### `admin` 模組內部結構

`admin` 模組透過將頁面 (Pages) 和 API 分離，進一步提升了可讀性：

| 檔案 | 職責 |
|---|---|
| `pages.py` | 提供所有管理後台的 HTML 頁面渲染。 |
| `user_api.py` | 處理所有與「用戶管理」相關的 API。 |
| `appointment_api.py` | 處理所有與「預約簿」相關的 API。 |
| `schedule_api.py` | 處理所有與「訊息排程」相關的 API。 |
| `config_api.py` | 處理所有與「系統設定」和「休診日」相關的 API。 |

## 4. 工具函式 (`app/utils/`) 詳解

`app/utils/` 目錄存放了專案中可重用的輔助函式，讓核心業務邏輯與具體實現細節解耦，有助於程式碼的重用與維護。

### `line_api.py` - LINE API 封裝
- **職責**: 封裝所有與 LINE Platform API 互動的函式。
- **範例**: `get_line_profile` (獲取用戶資料)、`send_line_message` (發送訊息)、`validate_signature` (驗證 Webhook 簽名)。

### `decorators.py` - 自訂裝飾器
- **職責**: 存放自訂的 Python 裝飾器，用於為路由函式附加額外功能。
- **範例**: `@admin_required` (驗證使用者是否為管理員)、`@api_error_handler` (提供統一的 API 錯誤處理)。

### `helpers.py` - 通用輔助工具箱
- **職責**: 存放各種通用的輔助函式，是應用程式的「多功能工具箱」。

### `api_response()` - 統一的 API 回應格式產生器
- **用途**: 確保所有 API 回應都有一致的 JSON 格式。
- **成功時**: 回傳 `{"status": "success", "data": ...}`。
- **失敗時**: 回傳 `{"status": "error", "message": ...}`。
- **優點**: 讓前端在處理 API 回應時非常方便，因為格式是可預測的。

### `get_vue_assets()` - 前端與後端的關鍵橋樑
- **用途**: 讀取前端 Vite 打包後產生的 `manifest.json` 檔案。
- **目的**: 從 `manifest.json` 中找出最新版本的 JavaScript (`.js`) 和 CSS (`.css`) 檔案的正確路徑，解決因檔名雜湊值變化導致的 404 錯誤。
- **結果**: 讓 Flask 樣板 (`.html`) 永遠都能載入到正確的前端資源。

### `get_week_dates()` - 週曆日期計算機
- **用途**: 處理預約簿頁面上「週曆」的日期計算邏輯。
- **功能**: 根據傳入的週次偏移量，計算出該週從週二到週六的日期與星期資訊。
- **特殊規則**: 包含商業邏輯，例如在週日訪問時，會自動顯示下一週的預約，優化使用者體驗。

### `generate_time_slots()` & `get_available_slots()` - 可預約時段產生器
- **用途**: 處理預約系統的核心業務邏輯。
- **`generate_time_slots`**: 根據後台設定的「可用時段」，產生出一天中所有可能的 15 分鐘預約時段列表。
- **`get_available_slots`**: 過濾掉「已預約」、「已過去」及「休診日」的時段，最終回傳一個**真正可供使用者預約**的時段列表。

## 5. 排程器 (`app/scheduler/`) 詳解

- **職責**: 負責在背景定時執行重複性任務，例如發送預約提醒。
- **核心元件**: 使用 `APScheduler` 的 `BackgroundScheduler`。
- **模組結構**:
  - `__init__.py`: 包含 `init_scheduler(app)` 函式，負責初始化 `BackgroundScheduler`，並將 `jobs.py` 中定義的任務加入排程。
  - `jobs.py`: 存放所有實際執行的排程工作函式，例如 `_do_send_reminders`。
  - `utils.py`: 存放專屬於排程器的輔助函式。這些函式被設計成不依賴 Flask 的應用程式上下文 (`current_app`)，確保它們可以在背景執行緒中安全地被呼叫。
- **初始化**:
  - `init_scheduler(app)` 函式會在 `create_app` 工廠中被呼叫。
  - 透過 `start_scheduler` 參數和 `WERKZEUG_RUN_MAIN` 環境變數，確保排程器只在 Flask 的主進程中啟動一次，避免在開發模式的重載過程中重複執行。
- **主要任務**:
  - **每日提醒**: 根據後台設定的時間，自動發送隔天的預約提醒。
  - **每週提醒**: 根據後台設定的時間，自動發送下週的預約提醒。
  - **自訂排程**: 執行在管理後台設定的自訂訊息排程。

## 6. 開發與部署指令

| 目的 | 指令 | 說明 |
|---|---|---|
| **本地啟動後端 (Flask)** | `venv\Scripts\activate`<br>`python main.py` | 啟動 Flask 開發伺服器。 |
| **本地啟動前端 (Vue)** | `cd frontend`<br>`npm run dev` | 在新的終端機中啟動 Vue.js 開發伺服器，提供熱重載功能。 |
| **打包前端專案** | `cd frontend`<br>`npm run build` | 將 Vue.js 專案編譯並輸出到後端的 `static` 目錄。 |
| **遠端伺服器重新啟動服務** | `sudo systemctl restart mywebsite` | 使用 Systemd 重新啟動 Gunicorn 網站服務。 |
| **遠端伺服器查看狀態** | `sudo systemctl status mywebsite` | 查看網站服務的運行狀態與日誌。 |

## 7. 總結

透過本次重構，專案的結構更加清晰，實現了高度的「關注點分離」。主要優點包括：

- **可維護性提升**: 每個模組職責單一，修改或新增功能時，能快速定位到相關檔案，降低了程式碼的耦合度。
- **可讀性增強**: 清晰的目錄結構和檔案命名，讓開發人員能輕易理解專案的整體架構。
- **易於擴展**: 未來若要新增功能（例如新的 API 或管理頁面），只需在對應的目錄下建立新的檔案或藍圖即可，不會影響到現有功能。
- **團隊協作**: 不同的開發人員可以同時在不同的模組上工作，減少衝突。

總體而言，這次重構為專案的長期發展和第二階段的開發打下了堅實、專業的基礎。
