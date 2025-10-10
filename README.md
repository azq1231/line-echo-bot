# LINE Bot 排程管理系統

一個基於 Flask 的 LINE Bot 用戶管理和訊息排程系統，提供網頁管理介面和自動發送功能。

## 功能特色

### 📱 自動用戶管理
- 當用戶加 Bot 為好友時自動記錄
- 當用戶發送訊息時自動記錄
- 自動獲取用戶的 LINE 顯示名稱
- 只有允許清單中的用戶會收到 Bot 回覆

### 📅 訊息排程
- 選擇用戶並設定發送時間
- 自定義訊息內容
- 自動在指定時間發送訊息
- 支援失敗重試機制（最多 3 次）
- 即時狀態追蹤（待發送/已發送/發送失敗）

### 💻 網頁管理介面
- 用戶管理頁面：查看和管理允許清單
- 排程管理頁面：創建和查看訊息排程
- 完全響應式設計，支援手機和電腦訪問

## 技術架構

- **後端框架**: Flask
- **排程系統**: APScheduler（每 30 秒檢查一次）
- **數據存儲**: JSON 文件（users.json, schedules.json）
- **外部 API**: LINE Messaging API

## 環境變數

需要設定以下環境變數：
- `LINE_CHANNEL_TOKEN`: LINE Bot 的 Channel Access Token

## 文件結構

```
├── main.py              # 主應用程式
├── templates/           # HTML 模板
│   ├── admin.html       # 用戶管理頁面
│   └── schedule.html    # 排程管理頁面
├── users.json           # 用戶數據
├── schedules.json       # 排程數據
└── replit.md           # 專案技術文檔
```

## 訪問方式

### 網頁管理介面
- 用戶管理：`/`
- 排程管理：`/schedule`

### Webhook
- LINE Webhook：`/webhook`
- 支援事件：follow（加好友）、message（訊息）

## 使用說明

1. 在 LINE Developers 設定 Webhook URL
2. 用戶加 Bot 為好友或發送訊息後會自動加入允許清單
3. 使用網頁介面管理用戶和創建排程
4. 系統會自動在指定時間發送訊息

## 手機支援

網站完全支援手機瀏覽器訪問，所有功能都經過手機優化，可直接在手機上管理用戶和排程。
