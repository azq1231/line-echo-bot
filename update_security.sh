#!/bin/bash

# ============================================
# 安全更新腳本 - LINE Bot 預約系統
# 日期: 2025-12-11
# 用途: 修補安全漏洞
# ============================================

set -e  # 遇到錯誤立即停止

echo "🔒 =========================================="
echo "   LINE Bot 安全更新腳本"
echo "   日期: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 顏色定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 檢查是否在正確的目錄
if [ ! -f "main.py" ]; then
    echo -e "${RED}❌ 錯誤: 請在專案根目錄執行此腳本${NC}"
    exit 1
fi

# 1. 備份資料庫
echo -e "${YELLOW}📦 步驟 1/6: 備份資料庫...${NC}"
if [ -f "appointments.db" ]; then
    BACKUP_NAME="appointments_backup_$(date +%Y%m%d_%H%M%S).db"
    cp appointments.db "$BACKUP_NAME"
    echo -e "${GREEN}✅ 資料庫已備份: $BACKUP_NAME${NC}"
else
    echo -e "${YELLOW}⚠️  未找到資料庫文件,跳過備份${NC}"
fi
echo ""

# 2. 備份當前依賴列表
echo -e "${YELLOW}📋 步驟 2/6: 備份當前依賴列表...${NC}"
source venv/bin/activate
pip freeze > "requirements_backup_$(date +%Y%m%d_%H%M%S).txt"
echo -e "${GREEN}✅ 依賴列表已備份${NC}"
echo ""

# 3. 更新 Python 依賴
echo -e "${YELLOW}⬆️  步驟 3/6: 更新 Python 依賴套件...${NC}"
echo "正在更新: requests, urllib3, werkzeug, setuptools, fonttools"
pip install --upgrade requests urllib3 werkzeug setuptools fonttools --quiet
echo -e "${GREEN}✅ Python 依賴已更新${NC}"
echo ""

# 4. 移除未使用的套件
echo -e "${YELLOW}🗑️  步驟 4/6: 移除未使用的套件...${NC}"
if pip show python-jose &> /dev/null; then
    pip uninstall python-jose -y --quiet
    echo -e "${GREEN}✅ 已移除 python-jose${NC}"
else
    echo "   python-jose 未安裝,跳過"
fi

if pip show ecdsa &> /dev/null; then
    pip uninstall ecdsa -y --quiet
    echo -e "${GREEN}✅ 已移除 ecdsa${NC}"
else
    echo "   ecdsa 未安裝,跳過"
fi
echo ""

# 5. 顯示更新後的版本
echo -e "${YELLOW}📊 步驟 5/6: 驗證更新...${NC}"
echo "更新後的套件版本:"
echo "-----------------------------------"
pip show requests urllib3 werkzeug setuptools fonttools 2>/dev/null | grep -E "^Name:|^Version:" | paste - - | sed 's/Name: /  • /' | sed 's/Version: / → /'
echo "-----------------------------------"
echo ""

# 6. 重啟服務
echo -e "${YELLOW}🔄 步驟 6/6: 重啟服務...${NC}"
if systemctl is-active --quiet mywebsite; then
    echo "正在重啟 mywebsite 服務..."
    sudo systemctl restart mywebsite
    sleep 2
    
    if systemctl is-active --quiet mywebsite; then
        echo -e "${GREEN}✅ 服務已成功重啟${NC}"
    else
        echo -e "${RED}❌ 服務重啟失敗,請檢查日誌${NC}"
        echo "執行以下命令查看錯誤: sudo journalctl -u mywebsite -n 50"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  mywebsite 服務未運行,跳過重啟${NC}"
    echo "請手動啟動服務: sudo systemctl start mywebsite"
fi
echo ""

# 完成
echo -e "${GREEN}=========================================="
echo "✅ 安全更新完成!"
echo "==========================================${NC}"
echo ""
echo "📝 後續步驟:"
echo "   1. 檢查服務狀態: sudo systemctl status mywebsite"
echo "   2. 查看日誌: sudo journalctl -u mywebsite -n 50 --no-pager"
echo "   3. 測試應用: curl http://localhost:5000/"
echo ""
echo "📦 備份文件位置:"
ls -lh appointments_backup_*.db 2>/dev/null | tail -1 | awk '{print "   資料庫: " $9 " (" $5 ")"}'
ls -lh requirements_backup_*.txt 2>/dev/null | tail -1 | awk '{print "   依賴: " $9 " (" $5 ")"}'
echo ""
echo "🔍 如需安全檢查,執行: pip install pip-audit && pip-audit"
echo ""
