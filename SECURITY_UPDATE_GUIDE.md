# 🔒 遠端伺服器安全更新指南

**更新日期**: 2025-12-11  
**目的**: 修補本地發現的安全漏洞到遠端 VPS

---

## 📋 更新概要

本次安全更新已修復多個依賴套件的漏洞,需要同步到遠端伺服器。

### ✅ 本地已完成的修復
- ✅ 前端: 修復 glob 套件高危漏洞
- ✅ 後端: 更新 6 個套件,移除 2 個未使用套件

---

## 🚀 遠端更新步驟

### 方案一: 完整更新 (推薦)

#### 1️⃣ 連線到 VPS

```bash
# 使用 SSH 連線到你的 VPS
ssh root@your_vps_ip
# 或
ssh your_username@your_vps_ip
```

#### 2️⃣ 進入專案目錄

```bash
cd /var/www/myapp
```

#### 3️⃣ 備份當前環境 (重要!)

```bash
# 備份資料庫
cp appointments.db appointments_backup_$(date +%Y%m%d_%H%M%S).db

# 備份當前的依賴列表
source venv/bin/activate
pip freeze > requirements_old_$(date +%Y%m%d).txt
```

#### 4️⃣ 拉取最新代碼

```bash
# 拉取最新的代碼 (如果你有推送到 Git)
git pull origin main

# 或者手動上傳文件 (見下方「方案二」)
```

#### 5️⃣ 更新 Python 依賴

```bash
# 啟動虛擬環境
source venv/bin/activate

# 更新核心安全套件
pip install --upgrade requests urllib3 werkzeug setuptools fonttools

# 移除未使用的套件
pip uninstall python-jose ecdsa -y

# 驗證安裝
pip list | grep -E "requests|urllib3|werkzeug|setuptools|fonttools"
```

#### 6️⃣ 更新前端依賴 (如果需要)

```bash
# 進入前端目錄
cd frontend

# 更新依賴
npm audit fix

# 重新編譯前端
npm run build

# 返回專案根目錄
cd ..
```

#### 7️⃣ 重啟服務

```bash
# 重啟 systemd 服務
sudo systemctl restart mywebsite

# 檢查服務狀態
sudo systemctl status mywebsite

# 查看日誌確認無錯誤
sudo journalctl -u mywebsite -n 50 --no-pager
```

#### 8️⃣ 驗證更新

```bash
# 檢查更新後的版本
source venv/bin/activate
pip show requests urllib3 werkzeug setuptools fonttools

# 確認應用程式正常運行
curl http://localhost:5000/
```

---

### 方案二: 手動上傳文件更新

如果你沒有使用 Git,可以手動上傳更新的文件。

#### 需要上傳的文件

**不需要上傳**:
- ❌ `venv/` - 虛擬環境 (在遠端重新安裝依賴即可)
- ❌ `node_modules/` - Node.js 依賴 (在遠端重新安裝)
- ❌ `__pycache__/` - Python 緩存
- ❌ `*.db` - 資料庫 (避免覆蓋遠端數據)
- ❌ `.env` - 環境變數 (遠端已有配置)
- ❌ `audit_*.txt` - 安全檢查報告
- ❌ `app.log` - 日誌文件

**需要上傳** (如果有修改):
- ✅ `static/` - 前端編譯後的文件 (如果前端有更新)
- ✅ `app/` - 後端應用程式代碼 (如果有代碼修改)
- ✅ `templates/` - HTML 模板 (如果有修改)
- ✅ `main.py` - 主程式 (如果有修改)
- ✅ `database.py` - 資料庫模組 (如果有修改)
- ✅ 其他 `.py` 文件 (如果有修改)

**本次安全更新實際情況**:
由於本次更新**僅涉及依賴套件版本升級**,沒有修改任何應用程式代碼,因此:
- ✅ **不需要上傳任何文件**
- ✅ **只需在遠端執行依賴更新命令即可**

#### 使用 SFTP/SCP 上傳 (如果需要)

```bash
# 使用 SCP 上傳整個專案 (排除不需要的文件)
# 在本地執行:
scp -r app/ templates/ static/ main.py database.py root@your_vps_ip:/var/www/myapp/

# 或使用 SFTP 客戶端 (如 FileZilla, WinSCP)
```

然後在遠端執行步驟 5-8。

---

### 方案三: 使用部署腳本 (最簡單)

創建一個自動化部署腳本:

#### 在 VPS 上創建更新腳本

```bash
# 在 VPS 上執行
nano /var/www/myapp/update_security.sh
```

貼上以下內容:

```bash
#!/bin/bash

# 安全更新腳本
# 日期: 2025-12-11

echo "🔒 開始安全更新..."

# 進入專案目錄
cd /var/www/myapp

# 備份資料庫
echo "📦 備份資料庫..."
cp appointments.db appointments_backup_$(date +%Y%m%d_%H%M%S).db

# 啟動虛擬環境
echo "🔧 啟動虛擬環境..."
source venv/bin/activate

# 更新依賴
echo "⬆️  更新 Python 依賴..."
pip install --upgrade requests urllib3 werkzeug setuptools fonttools

# 移除未使用的套件
echo "🗑️  移除未使用的套件..."
pip uninstall python-jose ecdsa -y

# 顯示更新後的版本
echo "✅ 更新完成! 當前版本:"
pip show requests urllib3 werkzeug setuptools fonttools | grep -E "Name|Version"

# 重啟服務
echo "🔄 重啟服務..."
sudo systemctl restart mywebsite

# 檢查服務狀態
echo "📊 服務狀態:"
sudo systemctl status mywebsite --no-pager -l

echo "✅ 安全更新完成!"
```

#### 執行更新腳本

```bash
# 賦予執行權限
chmod +x /var/www/myapp/update_security.sh

# 執行更新
/var/www/myapp/update_security.sh
```

---

## 🔍 更新後驗證

### 1. 檢查套件版本

```bash
source /var/www/myapp/venv/bin/activate
pip show requests urllib3 werkzeug setuptools fonttools
```

**預期版本**:
- `requests`: 2.32.4 或更高
- `urllib3`: 2.6.0 或更高
- `werkzeug`: 3.1.4 或更高
- `setuptools`: 78.1.1 或更高
- `fonttools`: 4.60.2 或更高

### 2. 確認套件已移除

```bash
pip show python-jose ecdsa
# 應該顯示: WARNING: Package(s) not found
```

### 3. 檢查應用程式運行狀態

```bash
# 檢查服務狀態
sudo systemctl status mywebsite

# 測試 API 端點
curl http://localhost:5000/

# 查看最近日誌
sudo journalctl -u mywebsite -n 50 --no-pager
```

### 4. 測試功能

- ✅ 訪問管理後台: `http://your_vps_ip:5000/`
- ✅ 測試 LINE Bot 功能
- ✅ 檢查預約功能是否正常
- ✅ 確認排程器正常運行

---

## 📊 更新的套件清單

| 套件 | 更新前 | 更新後 | 修復的漏洞 |
|------|--------|--------|------------|
| **requests** | 2.32.3 | 2.32.4 | CVE-2024-47081 |
| **urllib3** | 2.5.0 | 2.6.0 | CVE-2025-66418, CVE-2025-66471 |
| **werkzeug** | 3.1.3 | 3.1.4 | CVE-2025-66221 |
| **setuptools** | 65.5.0 | 78.1.1 | PYSEC-2022-43012, PYSEC-2025-49, CVE-2024-6345 |
| **fonttools** | 4.60.1 | 4.60.2 | CVE-2025-66034 |
| **python-jose** | 3.5.0 | ❌ 已移除 | N/A |
| **ecdsa** | 0.19.1 | ❌ 已移除 | CVE-2024-23342 |

---

## ⚠️ 注意事項

### 1. 備份的重要性
- ⚠️ **務必先備份資料庫**,避免意外情況導致數據丟失
- 建議保留最近 3-5 個備份

### 2. 服務中斷時間
- 更新過程中服務會短暫中斷 (約 10-30 秒)
- 建議在低峰時段執行更新

### 3. 回滾方案
如果更新後出現問題:

```bash
# 停止服務
sudo systemctl stop mywebsite

# 恢復資料庫 (如果需要)
cp appointments_backup_YYYYMMDD_HHMMSS.db appointments.db

# 降級套件 (使用舊的 requirements)
source venv/bin/activate
pip install -r requirements_old_YYYYMMDD.txt

# 重啟服務
sudo systemctl start mywebsite
```

### 4. 防火牆設定
確保防火牆已開放必要的端口:

```bash
# 檢查防火牆狀態
sudo ufw status

# 如果需要開放端口
sudo ufw allow 5000/tcp
```

---

## 🔐 安全檢查 (可選)

如果想在遠端也執行安全檢查:

```bash
# 安裝 pip-audit
source /var/www/myapp/venv/bin/activate
pip install pip-audit

# 執行安全掃描
pip-audit

# 前端安全檢查 (如果有 Node.js)
cd /var/www/myapp/frontend
npm audit
```

---

## 📞 問題排查

### 問題 1: pip 更新失敗

```bash
# 先更新 pip 本身
python -m pip install --upgrade pip

# 然後重新執行更新
pip install --upgrade requests urllib3 werkzeug setuptools fonttools
```

### 問題 2: 服務無法啟動

```bash
# 查看詳細錯誤日誌
sudo journalctl -u mywebsite -n 100 --no-pager

# 檢查 Python 語法錯誤
source venv/bin/activate
python -c "import app; print('OK')"
```

### 問題 3: 權限錯誤

```bash
# 確保文件權限正確
sudo chown -R root:root /var/www/myapp
# 或使用你的用戶名
sudo chown -R your_username:your_username /var/www/myapp
```

---

## ✅ 更新檢查清單

完成以下檢查後,更新即完成:

- [ ] 已備份資料庫
- [ ] 已更新 Python 依賴套件
- [ ] 已移除 python-jose 和 ecdsa
- [ ] 已重啟服務
- [ ] 服務狀態正常 (systemctl status)
- [ ] 應用程式可以訪問
- [ ] LINE Bot 功能正常
- [ ] 管理後台可以登入
- [ ] 預約功能正常運作
- [ ] 無錯誤日誌

---

## 📝 更新記錄範本

建議在 VPS 上記錄更新歷史:

```bash
# 創建更新日誌
nano /var/www/myapp/UPDATE_LOG.md
```

```markdown
# 更新記錄

## 2025-12-11 - 安全更新
- 更新 requests 2.32.3 → 2.32.4
- 更新 urllib3 2.5.0 → 2.6.0
- 更新 werkzeug 3.1.3 → 3.1.4
- 更新 setuptools 65.5.0 → 78.1.1
- 更新 fonttools 4.60.1 → 4.60.2
- 移除 python-jose, ecdsa (未使用)
- 修復 7 個安全漏洞
- 執行者: [你的名字]
- 狀態: ✅ 成功
```

---

**需要協助?** 如果更新過程中遇到任何問題,請參考本文檔的「問題排查」章節,或查看詳細的安全檢查報告 `security_audit_report.md`。
