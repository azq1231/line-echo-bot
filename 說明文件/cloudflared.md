Cloudflare Tunnel — 完整設置說明（含全部命令列步驟，針對你：本機服務在 5000）

下面把之前討論的完整流程與 可直接貼上執行的命令 一次整理好。
請在執行前把 <YOUR_TUNNEL_ID>、app.monyangood.com（或你要用的子域）等替換成你實際值。

一、前提確認

你已安裝 cloudflared（若未安裝，見步驟 2）。

你的本機服務正在 localhost:5000（可用 curl http://localhost:5000 測試）。

你有 Cloudflare 帳號，並且該帳號下管理 monyangood.com（或你的網域）。

二、（可選）安裝 cloudflared（Debian/Ubuntu 範例）
# 下載並安裝最新版 .deb
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# 檢查版本
cloudflared --version

三、登入 Cloudflare（若已登入可跳過）
cloudflared tunnel login


會開瀏覽器讓你登入並生成 /root/.cloudflared/cert.pem。

四、建立 Tunnel（若已建立可跳過）
cloudflared tunnel create myapp


執行後會顯示 Tunnel ID（例如 b780c871-f02d-4538-acfc-5e2ca702a9e8），請記下它。

五、將子域綁定到 Tunnel（建立 DNS CNAME）

範例把 app.monyangood.com 綁到 myapp tunnel：

cloudflared tunnel route dns myapp app.monyangood.com


說明：這會在 Cloudflare DNS 建立一個 CNAME 指向 ...cfargotunnel.com（自動建立），之後 https://app.monyangood.com 就會指向這個 tunnel。

注意：如果你嘗試使用 *.trycloudflare.com 但你的帳號已有管理其他網域，
cloudflared 會自動把 hostname 加上你的網域（導致 azq.trycloudflare.com.monyangood.com），
這會造成 SSL/協定錯誤。若你要用 trycloudflare.com，必須在一個沒有任何自有網域的 Cloudflare 帳號操作。

六、建立 /root/.cloudflared/config.yml（命令列寫入）

先確保資料夾存在並切換至該資料夾（非必要，但好管理）：

sudo mkdir -p /root/.cloudflared
cd /root/.cloudflared


用一條命令直接寫入 config.yml（把下面的 <YOUR_TUNNEL_ID> 與 hostname 換成你的值）：

sudo tee /root/.cloudflared/config.yml > /dev/null <<'EOF'
tunnel: b780c871-f02d-4538-acfc-5e2ca702a9e8     # <- 換成你的 tunnel ID
credentials-file: /root/.cloudflared/b780c871-f02d-4538-acfc-5e2ca702a9e8.json

ingress:
  - hostname: app.monyangood.com                 # <- 換成你要的子域
    service: http://localhost:5000               # <- 你的本機服務端口 5000
  - service: http_status:404
EOF


檢查內容：

sudo cat /root/.cloudflared/config.yml

七、確認本機服務（非常重要）

確定服務在 5000 可被 localhost 存取：

curl -I http://localhost:5000       # 只看 header
curl http://localhost:5000          # 要看完整回應


若 curl 無回應或錯誤，請先修正本機服務（Tunnel 只是代理，必須本機服務運作）。

八、啟動 Tunnel（測試方式）

直接在終端啟動（會在 foreground）：

cloudflared tunnel run myapp


你應看到類似 Registered tunnel connection ... 的多條註冊訊息，表示已連線到 Cloudflare edge。

若要中斷：Ctrl+C。

九、設定為系統服務（開機自動啟動）

建議把 cloudflared 安裝為 systemd 服務，讓它在系統啟動時自動運行：

# 安裝為 service（cloudflared 會自動建立 systemd 服務檔）
sudo cloudflared service install

# 啟用並啟動 service
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

# 檢查狀態
sudo systemctl status cloudflared


如果你想查看實時 log：

sudo journalctl -u cloudflared -f

十、確認與測試（在本機與外部）

檢查 tunnel 資訊：

cloudflared tunnel list
cloudflared tunnel info myapp


在 Cloudflare DNS（或 Cloudflare Dashboard）確認 app.monyangood.com 的 CNAME 已建立並指向 ...cfargotunnel.com。

在外部瀏覽器訪問（用 HTTPS）：

https://app.monyangood.com


Cloudflare 會自動管理 SSL。若看到頁面，代表成功。

十一、常見問題與檢查項目

ERR_SSL_VERSION_OR_CIPHER_MISMATCH：通常因為你用的 host 並非官方 trycloudflare.com，
或 DNS CNAME 指向錯誤。用本機網域 app.monyangood.com 並用 cloudflared tunnel route dns 建立 CNAME，可避免此錯誤。

Tunnel 啟動但外部無法訪問：

檢查 config.yml 的 hostname 是否正確。

確認本機 localhost:5000 可回應（curl 測試）。

確認 Cloudflare DNS 的 CNAME 是否存在（在 Cloudflare 網頁
或執行 cloudflared tunnel route dns myapp app.monyangood.com 再次確認）。

不想每次都在 foreground 執行：請用 systemd（見步驟九）。

若想取消 / 移除 DNS route：可在 Cloudflare Dashboard 的 DNS 管理頁面
移除該 CNAME（建議用 Dashboard 操作以避免語法差異）。