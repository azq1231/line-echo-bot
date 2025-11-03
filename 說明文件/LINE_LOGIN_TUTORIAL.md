# 線上預約功能設定教學 (LINE Login)

為了讓使用者能透過 LINE 帳號登入並使用您的線上預約網站，您需要先在 LINE Developers 後台建立一個「LINE Login」頻道，並取得相關的金鑰。

以下是詳細的設定步驟：

### 步驟一：登入 LINE Developers Console

前往 [LINE Developers Console](https://developers.line.biz/console/) 並使用您的 LINE 帳號登入。

### 步驟二：建立或選擇一個 Provider

如果您還沒有 Provider（供應商），請點擊「Create a new provider」建立一個，輸入您想要的名稱（例如：您的診所或公司名稱）。

如果您已經有 Provider，請直接點選它。

### 步驟三：建立一個新的「LINE Login」頻道

1.  在您的 Provider 頁面中，點擊「Create a new channel」。
2.  在頻道類型中，選擇 **「LINE Login」**。
3.  填寫頻道的必要資訊：
    *   **Channel type**: LINE Login (已選)
    *   **Provider**: (已選)
    *   **Region**: Taiwan
    *   **Channel icon**: 上傳您的 Logo。
    *   **Channel name**: 輸入您的網站或服務名稱（例如：XX 診所線上預約）。
    *   **Channel description**: 簡單描述您的網站。
    *   **App types**: 勾選 **Web app**。
    *   **Email address**: 輸入您的聯絡信箱。

4.  閱讀並同意使用條款，然後點擊「Create」建立頻道。

### 步驟四：取得 Channel ID 和 Channel Secret

建立頻道後，您會被導向到新頻道的管理頁面。

1.  點擊 **「Basic settings」** 分頁。
2.  您會在這裡找到 **`Channel ID`** 和 **`Channel secret`**。這兩個值非常重要，請先將它們複製下來。

### 步驟五：設定 Callback URL

Callback URL 是使用者在 LINE 登入成功後，要被重新導向回您網站的網址。

1.  點擊 **「LINE Login」** 分頁。
2.  在 **Callback URL** 欄位中，點擊「Edit」。
3.  輸入您網站的 Callback 網址。格式為：`https://<您的網站網域>/callback`
    *   **正式環境範例**：如果您的網域是 `myclinic.com`，就輸入 `https://myclinic.com/callback`。
    *   **本地測試範例**：如果您在本機使用 `ngrok` 測試，就輸入 `ngrok` 產生的 HTTPS 網址，例如 `https://xxxx-xxxx.ngrok-free.app/callback`。
4.  點擊「Update」儲存。

### 步驟六：設定環境變數

最後，將您在步驟四取得的 `Channel ID` 和 `Channel secret` 設定到您伺服器的環境變數中。

```bash
LINE_LOGIN_CHANNEL_ID=（貼上您的 Channel ID）
LINE_LOGIN_CHANNEL_SECRET=（貼上您的 Channel secret）
```

設定完成後，請務必**重新啟動您的網站服務** (`sudo systemctl restart mywebsite`)，新的設定才會生效。

完成以上所有步驟後，您的線上預約頁面就可以正常使用 LINE 登入功能了！