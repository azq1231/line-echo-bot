# LINE Rich Menu 設定教程

## 什麼是 Rich Menu？

Rich Menu 是 LINE 對話視窗下方的固定選單，可以讓用戶快速訪問常用功能，無需手動輸入文字。

## 設定步驟

### 1. 登入 LINE Developers Console

1. 前往 [LINE Developers Console](https://developers.line.biz/console/)
2. 使用您的 LINE 帳號登入
3. 選擇您的 Provider（如果沒有，需要先創建）
4. 選擇您的 Messaging API Channel

### 2. 創建 Rich Menu

1. 在左側選單中點擊 **"Messaging API"** 標籤
2. 向下滾動找到 **"Rich menus"** 區域
3. 點擊 **"Create"** 按鈕

### 3. 設計 Rich Menu

#### 基本設定

- **Title（選單標題）**：輸入描述性名稱，例如「預約選單」
- **Chat bar text（聊天欄文字）**：顯示在選單上的文字，例如「預約功能」
- **Display period（顯示期間）**：選擇「Always」（始終顯示）

#### 版面設計

推薦使用以下佈局：

**選項 A：3 按鈕橫向排列**
```
Template: A (3 buttons)
Size: 2500 x 1686 pixels
Areas: 3 equal sections
```

**選項 B：6 按鈕網格**
```
Template: B (6 buttons)
Size: 2500 x 1686 pixels  
Areas: 6 equal sections (2行3列)
```

#### 按鈕設定

為每個區域設定操作：

| 按鈕 | 標籤 | 動作類型 | 內容 |
|------|------|----------|------|
| 1 | 📅 我要預約 | Send message | 預約 |
| 2 | 🔍 查詢預約 | Send message | 查詢 |
| 3 | ❌ 取消預約 | Send message | 取消 |

### 4. 上傳背景圖片

#### 圖片規格

- **尺寸**：2500 x 1686 pixels（PNG 格式）
- **檔案大小**：最大 1MB
- **顏色**：建議使用品牌色或白色背景

#### 設計建議

使用 Canva 或 Photoshop 創建：

1. 新建 2500 x 1686 像素畫布
2. 根據選擇的模板添加文字和圖標
3. 確保按鈕區域文字清晰可讀
4. 匯出為 PNG 格式
5. 上傳到 Rich Menu 設定

### 5. 啟用 Rich Menu

1. 點擊 **"Save"** 儲存設定
2. 在 Rich Menu 列表中找到剛創建的選單
3. 點擊 **"⋮"** (三個點) > **"Set as default"** 設為預設選單

### 6. 測試 Rich Menu

1. 用手機打開 LINE
2. 進入您的 Bot 聊天室
3. 應該會看到底部出現 Rich Menu
4. 點擊各按鈕測試功能

## 進階設定

### 多語言 Rich Menu

如果需要支援多語言：

1. 創建多個 Rich Menu（每種語言一個）
2. 使用 LINE Messaging API 的 `linkRichMenuToUser` 根據用戶語言設定不同選單

### 時段限定 Rich Menu

可以設定不同時段顯示不同選單：

1. 創建多個 Rich Menu
2. 在「Display period」設定不同的顯示時間
3. 系統會自動在指定時間切換

## 常見問題

### Q: Rich Menu 沒有顯示？

**解決方法：**
1. 確認已設為預設選單
2. 檢查是否有設定顯示期間限制
3. 嘗試封鎖後重新加入 Bot

### Q: 按鈕無法點擊？

**解決方法：**
1. 確認區域設定正確對應按鈕位置
2. 檢查動作設定是否正確
3. 確認 Bot 已啟用 webhook

### Q: 圖片顯示模糊？

**解決方法：**
1. 確保使用正確尺寸（2500 x 1686）
2. 使用 PNG 格式而非 JPG
3. 避免過度壓縮圖片

## 參考資源

- [LINE Rich Menu 官方文件](https://developers.line.biz/en/docs/messaging-api/using-rich-menus/)
- [Rich Menu 設計範本](https://developers.line.biz/en/docs/messaging-api/rich-menu-images/)
- [Canva 設計工具](https://www.canva.com/)

## 相關指令

本系統支援以下指令（無論是否使用 Rich Menu）：

- **預約** / **预约** / **訂位** / **订位** → 開始預約流程
- **查詢** / **查询** / **我的預約** / **我的预约** → 查看我的預約
- **取消** / **取消預約** / **取消预约** → 取消最近的預約
