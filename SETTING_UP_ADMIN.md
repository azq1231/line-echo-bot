# 設定第一位管理員

當您首次部署此系統時，會遇到一個「雞生蛋，蛋生雞」的問題：由於資料庫中沒有任何管理員，您將無法登入後台來指定第一位管理員。

本文件提供兩種方法來解決這個問題並設定您的第一位管理員帳號。

---

## 方法一：手動操作資料庫 (快速直接)

此方法直接修改資料庫檔案，適合緊急情況或熟悉 SQL 的使用者。

1.  **登入以建立您的使用者資料**
    *   前往您的線上預約頁面 (例如 `http://<您的IP>:5000/`)。
    *   使用您自己的 LINE 帳號完成一次登入。此步驟會將您的 LINE User ID 和個人資料寫入資料庫。

2.  **進入伺服器並開啟資料庫**
    *   透過 SSH 連線到您的伺服器。
    *   進入專案目錄：
        ```bash
        cd /var/www/myapp
        ```
    *   使用 `sqlite3` 指令開啟資料庫檔案：
        ```bash
        sqlite3 appointments.db
        ```

3.  **更新您的管理員權限**
    *   在 `sqlite>` 提示符後，執行以下 SQL 指令。請將 `'Your_Line_User_ID'` 替換成您自己的 LINE User ID (通常是 `U` 開頭的一長串字元)。
        > **提示**：如果您不確定自己的 User ID，可以先執行 `SELECT user_id, name FROM users;` 來查看所有使用者。
        ```sql
        UPDATE users SET is_admin = 1 WHERE user_id = 'Your_Line_User_ID';
        ```
    *   執行後，輸入 `.quit` 並按下 Enter 即可退出。

完成後，您的帳號即擁有管理員權限。

---

## 方法二：使用自訂指令 (推薦)

此方法更為安全和標準，透過應用程式提供的指令來設定管理員，無需直接操作資料庫。

1.  **登入以建立您的使用者資料**
    *   與方法一相同，請先確保您想設為管理員的 LINE 帳號已在系統中登入過一次。

2.  **進入伺服器並執行指令**
    *   透過 SSH 連線到您的伺服器。
    *   進入專案目錄：
        ```bash
        cd /var/www/myapp
        ```
    *   **啟動虛擬環境**，這是關鍵步驟：
        ```bash
        source venv/bin/activate
        ```
        成功後，您的命令提示符前會出現 `(venv)`。

    *   **執行設定指令**：
        ```bash
        FLASK_APP=main.py flask set-admin
        ```
        系統會列出所有已存在的使用者，並提示您輸入編號。

        > **Windows (PowerShell) 使用者請注意：**
        > PowerShell 不支援上述語法。請分兩步驟執行：
        > ```powershell
        > # 1. 設定環境變數
        > $env:FLASK_APP = "main.py"
        >
        > # 2. 執行指令
        > flask set-admin
        > ```

    *   根據提示，輸入您自己帳號對應的數字編號，然後按下 Enter。

3.  **常見指令錯誤排解**
    *   `flask: command not found`: 您忘記執行 `source venv/bin/activate` 來啟動虛擬環境。
    *   `Permission denied`: `flask` 檔案缺少執行權限。請執行 `chmod +x venv/bin/flask`，此操作只需執行一次。
    *   `Could not locate a Flask application`: 您忘記在指令前加上 `FLASK_APP=main.py`。

---

## 完成設定

一旦第一位管理員設定成功，您就可以使用該 LINE 帳號登入後台，並在「用戶管理」頁面中，透過圖形化介面方便地指定或移除其他使用者的管理員權限。