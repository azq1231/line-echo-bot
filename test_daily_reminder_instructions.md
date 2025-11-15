# 測試每日自動提醒任務

要測試 2025 年 11 月 25 日的每日自動提醒，您需要將 `fake_date` 設定為 2025 年 11 月 24 日。這是因為每日提醒任務會發送「明天」的預約提醒。

**重要：** 您需要在部署應用程式的伺服器上設定 `ADMIN_API_TOKEN`。
如果您的 Flask 應用程式使用 `python-dotenv` (例如在 `app/__init__.py` 中有 `load_dotenv()`)，您應該將 `ADMIN_API_TOKEN` 寫入您的 `.env` 檔案中，例如：
```
ADMIN_API_TOKEN="MySuperSecretToken123"
```
請將 `"MySuperSecretToken123"` 替換為您實際設定的 token。
**重要提示**：對於由 `systemd` 服務管理的應用程式，直接在 shell 中使用 `export` 設定的環境變數不會被服務載入。必須將其寫入 `.env` 檔案或在 `systemd` 服務檔案中明確設定。

請使用以下命令，並確保替換為您實際設定的 `ADMIN_API_TOKEN`：

```powershell
Invoke-RestMethod -Uri "https://app.monyangood.com/api/admin/trigger_job/daily_reminder_job" `
    -Method POST `
    -Headers @{
        "Content-Type"="application/json"
        "X-Admin-Token"="MySuperSecretToken123" # 請替換為您實際設定的 token
    } `
    -Body '{"fake_date": "2025-11-24"}'
```

**執行環境說明：**

這個 `Invoke-RestMethod` 命令是 PowerShell 的語法，因此您應該在 **Windows 作業系統**的 PowerShell 終端機中執行它。

雖然命令是在您的本地電腦上執行，但它會向遠端的 `https://app.monyangood.com` 伺服器發送請求，觸發伺服器上的提醒任務。

執行此命令後，如果一切設定正確，您應該會收到針對 2025 年 11 月 25 日預約的每日提醒。