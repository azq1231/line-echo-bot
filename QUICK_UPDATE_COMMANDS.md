# 🚀 快速更新命令 - 複製貼上即可執行

## 方法一: 使用自動化腳本 (最簡單) ⭐

### 1. 上傳腳本到 VPS
```bash
# 在本地,使用 SCP 上傳腳本
scp update_security.sh root@your_vps_ip:/var/www/myapp/

# 或手動複製 update_security.sh 的內容到 VPS
```

### 2. 在 VPS 上執行
```bash
# SSH 連線到 VPS
ssh root@your_vps_ip

# 進入專案目錄
cd /var/www/myapp

# 賦予執行權限
chmod +x update_security.sh

# 執行更新
./update_security.sh
```

---

## 方法二: 手動執行命令 (逐步執行)

### 完整命令 (一次性複製貼上)
```bash
# 進入專案目錄
cd /var/www/myapp

# 備份資料庫
cp appointments.db appointments_backup_$(date +%Y%m%d_%H%M%S).db

# 啟動虛擬環境
source venv/bin/activate

# 備份當前依賴
pip freeze > requirements_backup_$(date +%Y%m%d).txt

# 更新依賴套件
pip install --upgrade requests urllib3 werkzeug setuptools fonttools

# 移除未使用的套件
pip uninstall python-jose ecdsa -y

# 驗證更新
echo "=== 更新後的版本 ==="
pip show requests urllib3 werkzeug setuptools fonttools | grep -E "Name|Version"

# 重啟服務
sudo systemctl restart mywebsite

# 檢查服務狀態
sudo systemctl status mywebsite --no-pager

# 查看日誌
sudo journalctl -u mywebsite -n 30 --no-pager
```

---

## 方法三: 分步執行 (謹慎操作)

### 步驟 1: 連線並備份
```bash
ssh root@your_vps_ip
cd /var/www/myapp
cp appointments.db appointments_backup_$(date +%Y%m%d_%H%M%S).db
```

### 步驟 2: 更新 Python 依賴
```bash
source venv/bin/activate
pip install --upgrade requests urllib3 werkzeug setuptools fonttools
```

### 步驟 3: 移除未使用套件
```bash
pip uninstall python-jose ecdsa -y
```

### 步驟 4: 重啟服務
```bash
sudo systemctl restart mywebsite
sudo systemctl status mywebsite
```

---

## 驗證命令

### 檢查套件版本
```bash
source /var/www/myapp/venv/bin/activate
pip show requests urllib3 werkzeug setuptools fonttools | grep -E "Name|Version"
```

### 預期結果
```
Name: requests
Version: 2.32.4
Name: urllib3
Version: 2.6.0
Name: werkzeug
Version: 3.1.4
Name: setuptools
Version: 78.1.1
Name: fonttools
Version: 4.60.2
```

### 確認套件已移除
```bash
pip show python-jose ecdsa
# 應該顯示: WARNING: Package(s) not found
```

### 測試應用程式
```bash
# 測試本地端點
curl http://localhost:5000/

# 檢查服務日誌
sudo journalctl -u mywebsite -n 50 --no-pager
```

---

## 回滾命令 (如果出現問題)

```bash
# 停止服務
sudo systemctl stop mywebsite

# 恢復資料庫 (替換為實際的備份文件名)
cp appointments_backup_YYYYMMDD_HHMMSS.db appointments.db

# 恢復依賴 (替換為實際的備份文件名)
source venv/bin/activate
pip install -r requirements_backup_YYYYMMDD.txt

# 重啟服務
sudo systemctl start mywebsite
sudo systemctl status mywebsite
```

---

## 常用維護命令

### 查看服務狀態
```bash
sudo systemctl status mywebsite
```

### 查看實時日誌
```bash
sudo journalctl -u mywebsite -f
```

### 查看最近 50 條日誌
```bash
sudo journalctl -u mywebsite -n 50 --no-pager
```

### 重啟服務
```bash
sudo systemctl restart mywebsite
```

### 停止服務
```bash
sudo systemctl stop mywebsite
```

### 啟動服務
```bash
sudo systemctl start mywebsite
```

---

## 安全檢查命令 (可選)

```bash
# 安裝安全檢查工具
source /var/www/myapp/venv/bin/activate
pip install pip-audit

# 執行安全掃描
pip-audit

# 預期結果: 應該只剩 3 個低風險漏洞 (pip, uv)
```

---

## 📋 更新檢查清單

完成後請確認:
- [ ] 資料庫已備份
- [ ] Python 依賴已更新
- [ ] python-jose 和 ecdsa 已移除
- [ ] 服務已重啟且狀態正常
- [ ] 應用程式可以訪問
- [ ] 無錯誤日誌

---

## 💡 提示

1. **備份很重要**: 每次更新前都要備份資料庫
2. **低峰時段**: 建議在使用者較少的時段執行更新
3. **測試功能**: 更新後測試主要功能是否正常
4. **保留日誌**: 記錄更新時間和結果

---

## ❓ 需要幫助?

如果遇到問題,請參考:
- 📖 詳細指南: `SECURITY_UPDATE_GUIDE.md`
- 📊 安全報告: `security_audit_report.md`
- 📝 部署文檔: `說明文件/DEPLOYMENT_TUTORIAL.md`
