# LINE Bot 智慧預約管理系統

一個功能強大的 LINE Bot 預約與會員管理系統，基於 Flask 和 SQLite 打造。系統不僅提供使用者透過 LINE 進行互動式預約，還包含一個功能完善的網頁後台，讓管理者可以輕鬆進行排程、會員、休診日與系統設定的管理。

## 主要功能

### 👤 使用者端 (LINE & 網頁)

1.  **LINE 互動預約**
    *   **關鍵字觸發**：輸入「預約」、「查詢」、「取消」等關鍵字，即可啟動對應功能。
    *   **互動式卡片**：透過 Flex Message 卡片進行日期與時段的選擇，操作直觀。
    *   **智慧過濾**：系統會自動隱藏已額滿或已過去的時段。
    *   **預約管理**：可查詢未來預約，或一鍵取消最近的預約。

2.  **網頁預約與查詢**
    *   **LINE 登入**：整合 LINE Login，確保使用者身份安全。
    *   **視覺化預約 (`/booking/`)**：以週曆形式呈現可預約時段，點擊即可快速預約。
    *   **預約紀錄 (`/booking/history`)**：登入後可查看所有「進行中」與「歷史」預約，並可直接在網頁上取消未來的預約。

### ⚙️ 管理後台 (Web Admin Panel)

1.  **總覽儀表板 (`/schedule`)**
    *   以週曆表格呈現所有預約狀況，一目了然。
    *   可直接在表格中為指定用戶手動新增或取消預約。
    *   支援手動觸發「本日」或「本週」的預約提醒訊息。

2.  **用戶管理 (`/`)**
    *   自動記錄所有互動過的使用者，並顯示其頭像、姓名、注音、電話。
    *   支援**即時搜尋**功能，可依姓名或注音快速找到用戶。
    *   可手動新增、編輯用戶資料，或從 LINE 重新同步。

3.  **休診管理 (`/closed_days`)**
    *   可設定特定日期為休診日。
    *   設定後，系統會**自動取消**該日所有已確認的預約，避免衝突。

4.  **訊息統計 (`/stats`)**
    *   記錄所有系統發送的訊息（如預約提醒、成功/失敗通知）。
    *   提供圖表與數據，分析各類型訊息的發送成功率。

5.  **系統設定 (`/configs`)**
    *   **功能開關**：可自由啟用或停用「排程管理」、「休診管理」等功能模組，自訂導覽列。
    *   **自動提醒**：可開啟自動提醒功能，並自訂「本日提醒」與「本週提醒」的發送時間。**時間設定即時生效，無需重啟**。
    *   **預約窗口**：可設定使用者能預約未來幾週（2週或4週）的時段。

## 技術架構

*   **後端框架**: Flask
*   **資料庫**: SQLite
*   **背景排程**: APScheduler (用於自動提醒)
*   **AI 整合**: Gemini AI (用於智慧排程建議)
*   **外部 API**: LINE Messaging API, LINE Login API
*   **安全性**: Webhook 簽名驗證 (HMAC-SHA256)

## 安裝與部署

詳細步驟請參考 `DEPLOYMENT_TUTORIAL.md` 文件。

### 環境變數

執行前需設定以下環境變數：
*   `LINE_CHANNEL_TOKEN`: Messaging API 的 Channel Access Token
*   `LINE_CHANNEL_SECRET`: Messaging API 的 Channel Secret
*   `LINE_LOGIN_CHANNEL_ID`: LINE Login 的 Channel ID
*   `LINE_LOGIN_CHANNEL_SECRET`: LINE Login 的 Channel Secret
*   `FLASK_SECRET_KEY`: Flask 應用程式的密鑰 (用於 Session)
*   `GEMINI_API_KEY`: Google Gemini 的 API 金鑰

### 本地啟動

1.  安裝依賴：
    ```bash
    pip install -r requirements.txt
    ```
2.  設定 `.env` 檔案。
3.  啟動應用：
    ```bash
    python main.py
    ```

## 專案結構

```plaintext
├── main.py                 # 主應用程式
├── database.py             # 資料庫操作模組
├── gemini_ai.py            # Gemini AI 整合模組
├── line_flex_messages.py   # LINE Flex Message 模板
├── templates/              # HTML 網頁模板
├── appointments.db         # SQLite 資料庫檔案
├── requirements.txt        # Python 依賴列表
├── DEPLOYMENT_TUTORIAL.md  # 部署指南
└── README.md               # 本文件
```
