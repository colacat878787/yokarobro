# 🍓 Raspberry Pi Zero 2W 備援系統部署說明

## 系統概述

這是 **幽芙優(小幽)** 的備援系統，當主伺服器離線時，Raspberry Pi Zero 2W 會自動啟動備援機器人，確保服務不中斷。

### 運作流程
1. **正常情況**：主伺服器每 30 秒發送心跳到 Pi
2. **偵測離線**：Pi 超過 120 秒未收到心跳 → 自動啟動備援機器人
3. **恢復上線**：主伺服器恢復後發送心跳 → Pi 自動關閉備援機器人

---

## 📋 需求準備

### 硬體需求
- Raspberry Pi Zero 2W（已安裝 Raspberry Pi OS）
- MicroSD 卡（建議 16GB 以上）
- 電源供應器（5V/3A 建議）
- 網路連線（有線或 Wi-Fi）

### 軟體需求
- Raspberry Pi OS (Bookworm 或更新版本)
- Python 3.9+
- Git
- Discord Bot Token（備援用，可與主伺服器相同或不同）

---

## 🚀 快速部署

### 方法一：一鍵安裝腳本（推薦）

```bash
# 1. 克隆專案到 Pi
git clone https://github.com/colacat878787/yokarobro.git /opt/yokaro-backup
cd /opt/yokaro-backup

# 2. 確認檔案存在
ls -la pi_setup.sh

# 3. 加入執行權限
chmod +x pi_setup.sh

# 4. 執行安裝腳本
sudo ./pi_setup.sh
```

安裝腳本會自動：
- ✅ 安裝系統依賴（Python, pip, git, ffmpeg）
- ✅ 克隆最新程式碼
- ✅ 建立 Python 虛擬環境
- ✅ 安裝 Python 套件
- ✅ 建立 systemd 服務（開機自動啟動）
- ✅ 啟動備援監控服務

### 方法二：手動安裝

```bash
# 1. 更新系統
sudo apt-get update && sudo apt-get upgrade -y

# 2. 安裝依賴
sudo apt-get install -y python3 python3-pip python3-venv git ffmpeg

# 3. 建立工作目錄
sudo mkdir -p /opt/yokaro-backup
sudo chown $USER:$USER /opt/yokaro-backup
cd /opt/yokaro-backup

# 4. 克隆程式碼
git clone https://github.com/colacat878787/yokarobro.git .

# 5. 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 6. 安裝依賴
pip install --upgrade pip
pip install -r requirements.txt

# 7. 設定環境變數
nano .env
```

---

## ⚙️ 環境變數設定

在 Pi 的 `/opt/yokaro-backup/.env` 中設定：

```env
# Discord Bot Token（可以使用主伺服器的 token 或獨立的備援 token）
DISCORD_TOKEN=你的Discord_Bot_Token

# Gemini API（可選，用於 AI 功能）
GEMINI_API_KEY=你的Gemini_API_Key

# Genius API（可選，用於歌詞功能）
GENIUS_ACCESS_TOKEN=你的Genius_Token

# Discord Client Secret（可選）
DISCORD_CLIENT_SECRET=你的Client_Secret

# AI 模型選擇（可選）
AI_MODEL=gemini-2.5-flash
```

### 💡 建議
- **方案 A**：使用與主伺服器相同的 token（簡單，但兩個機器人會同時上線時會衝突）
- **方案 B**：建立獨立的備援 bot token（推薦，避免衝突）

---

## 🔧 主伺服器設定

### 1. 設定主伺服器的公開網址

在主伺服器的 `.env` 中加入：

```env
# 主伺服器的公開網址（讓 Pi 可以訪問）
# 格式：https://你的域名 或 http://公網IP
# 例如：MAIN_SERVER_URL=https://yokaro.wayna1015.ccwu.cc
MAIN_SERVER_URL=https://你的主伺服器網址
```

**重要提示：**
- 這個網址必須是 Pi 可以訪問的（需要是公開網址或兩台機器在同一區域網路）
- 如果使用域名，確保有正確的 DNS 解析
- 如果使用 IP，確保是公網 IP 或兩台在同一區域網路

### 2. 確認埠號 8080 對外開放

主伺服器會監聽埠 8080 提供狀態查詢，確保防火牆允許存取：

```bash
# 在 Pi 上測試連線（替換成你的主伺服器網址）
curl https://你的主伺服器網址/status
```

應該回傳：
```json
{
  "status": "ok",
  "bot_name": "幽芙優",
  "guilds": 10,
  "latency": 50,
  "timestamp": "2026-07-31 22:30:00"
}
```

---

## 🎯 系統管理

### 查看服務狀態
```bash
sudo systemctl status yokaro-failover
```

### 查看即時日誌
```bash
sudo journalctl -u yokaro-failover -f
```

### 重啟服務
```bash
sudo systemctl restart yokaro-failover
```

### 停止服務
```bash
sudo systemctl stop yokaro-failover
```

### 開機自動啟動
```bash
# 啟用開機啟動
sudo systemctl enable yokaro-failover

# 停用開機啟動
sudo systemctl disable yokaro-failover
```

---

## 📊 狀態監控

### Pi 端狀態頁面
```
http://<Pi_IP>:8888/status
```

回傳範例：
```json
{
  "main_server_online": true,
  "backup_running": false,
  "last_heartbeat": "2026-07-31 22:30:00",
  "uptime": 15,
  "timestamp": "2026-07-31 22:30:15"
}
```

### 手動觸發備援（測試用）

**方法 1：停止 Pi 服務（模擬主伺服器離線）**
```bash
# 停止 Pi 的監控服務
sudo systemctl stop yokaro-failover

# 等待 120 秒後，備援會自動啟動
# 手動啟動備援機器人測試
cd /opt/yokaro-backup
source venv/bin/activate
python3 yokaro.py
```

**方法 2：阻擋主伺服器連線（更真實的測試）**
```bash
# 在 Pi 上臨時阻擋對主伺服器的連線
sudo iptables -A OUTPUT -d 主伺服器IP -j DROP

# 等待 120 秒後，備援會啟動
# 測試完成後恢復連線
sudo iptables -D OUTPUT -d 主伺服器IP -j DROP
```

---

## 🔍 故障排除

### 問題 1：執行安裝腳本時出現 "command not found"

**解決方法：**
```bash
# 1. 確認你已經克隆了專案
ls -la /opt/yokaro-backup/

# 2. 如果沒有，先克隆
sudo git clone https://github.com/colacat878787/yokarobro.git /opt/yokaro-backup

# 3. 進入目錄
cd /opt/yokaro-backup

# 4. 確認腳本存在
ls -la pi_setup.sh

# 5. 加入執行權限
chmod +x pi_setup.sh

# 6. 執行腳本
sudo ./pi_setup.sh
```

**或者使用 bash 執行（不需要 chmod）：**
```bash
cd /opt/yokaro-backup
sudo bash pi_setup.sh
```

### 問題 2：備援機器人沒有啟動

**檢查清單：**
```bash
# 1. 檢查 .env 是否存在
ls -la /opt/yokaro-backup/.env

# 2. 檢查 DISCORD_TOKEN 是否正確
grep DISCORD_TOKEN /opt/yokaro-backup/.env

# 3. 檢查日誌
sudo journalctl -u yokaro-failover -n 100

# 4. 檢查網路連線
ping 8.8.8.8

# 5. 測試 Discord API 連線
cd /opt/yokaro-backup
source venv/bin/activate
python3 -c "import discord; print('Discord.py OK')"
```

### 問題 2：Pi 無法連接主伺服器

**檢查清單：**
```bash
# 1. 確認主伺服器網址正確
grep MAIN_SERVER_URL /opt/yokaro-backup/.env

# 2. 測試連線到主伺服器
curl https://你的主伺服器網址/status

# 3. 檢查 DNS 解析（如果使用域名）
nslookup 你的域名

# 4. 檢查 Pi 的網路連線
ping 8.8.8.8

# 5. 檢查防火牆
sudo ufw status
```

### 問題 3：主伺服器狀態查詢失敗

**檢查清單：**
```bash
# 1. 確認主伺服器正在運行
# 在主伺服器執行
python3 yokaro.py

# 2. 測試狀態端點
curl https://你的主伺服器網址/status

# 3. 檢查主伺服器的埠號 8080 是否開啟
sudo netstat -tlnp | grep 8080

# 4. 檢查主伺服器的防火牆設定
```

### 問題 4：Git pull 失敗

```bash
# 手動更新
cd /opt/yokaro-backup
git pull origin main

# 如果遇到權限問題
sudo chown -R $USER:$USER /opt/yokaro-backup
```

---

## 📝 進階設定

### 調整輪詢參數

編輯 `pi_failover.py` 的設定區域：

```python
# ===== 設定 =====
POLL_INTERVAL = 30              # 輪詢主伺服器的間隔（秒）
FAILOVER_THRESHOLD = 4          # 連續失敗次數後啟動備援（30秒 * 4 = 120秒）
BOT_STARTUP_DELAY = 5           # 啟動備援前的延遲（秒）
```

**建議值：**
- `POLL_INTERVAL`：30 秒（不要太頻繁，避免對主伺服器造成負擔）
- `FAILOVER_THRESHOLD`：4 次（30秒 * 4 = 120秒，避免短暫網路波動觸發）
- `BOT_STARTUP_DELAY`：5-10 秒，避免短暫波動誤觸發

### 修改後重新載入
```bash
sudo systemctl restart yokaro-failover
```

---

## 🛡️ 安全建議

1. **使用獨立 Bot Token**
   - 在 Discord Developer Portal 建立第二個 bot
   - 避免兩個實體同時上線導致衝突

2. **限制網路存取**
   ```bash
   # 只允許主伺服器 IP 存取心跳埠
   sudo ufw allow from <主伺服器IP> to any port 8888
   ```

3. **定期更新**
   ```bash
   # 設定每日自動更新
   crontab -e
   # 加入：0 3 * * * cd /opt/yokaro-backup && git pull origin main
   ```

4. **監控備援狀態**
   - 設定外部監控（如 UptimeRobot）監控 Pi 的 `/status` 頁面
   - 當 `backup_running: true` 時發送通知

---

## 📈 效能優化

### Raspberry Pi Zero 2W 最佳化

1. **關閉不必要的服務**
   ```bash
   sudo systemctl disable bluetooth
   sudo systemctl disable hciuart
   ```

2. **設定 Swap（可選）**
   ```bash
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile
   # 修改 CONF_SWAPSIZE=2048
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

3. **使用 systemd 資源限制**
   ```bash
   sudo nano /etc/systemd/system/yokaro-failover.service
   # 加入：
   # [Service]
   # MemoryLimit=512M
   # CPUQuota=80%
   ```

---

## 🎮 測試流程

### 完整測試步驟

1. **測試 1：正常心跳**
   ```bash
   # 在主伺服器啟動後，檢查 Pi 日誌
   sudo journalctl -u yokaro-failover -f
   # 應該看到：📡 收到主伺服器心跳
   ```

2. **測試 2：模擬離線**
   ```bash
   # 停止主伺服器心跳發送
   # 在 Pi 上等待 120 秒
   # 應該看到：🚨 主伺服器離線！正在啟動備援機器人...
   ```

3. **測試 3：恢復上線**
   ```bash
   # 重新啟動主伺服器
   # 應該看到：📡 收到主伺服器心跳，正在停止備援...
   ```

4. **測試 4：開機自動啟動**
   ```bash
   sudo reboot
   # 開機後檢查
   sudo systemctl status yokaro-failover
   ```

---

## 📞 常見問題

### Q: 兩個機器人會同時上線嗎？
**A:** 不會。Pi 收到心跳後會立即停止備援機器人。但如果網路延遲嚴重，可能會有短暫的同時上線時間（約 10-30 秒）。

### Q: 可以使用同一個 Discord Bot Token 嗎？
**A:** 可以，但不推薦。Discord 不允許同一個 bot 實體同時在多個地方上線，可能會導致其中一個被強制下線。

### Q: Pi 斷網後會怎樣？
**A:** Pi 會持續嘗試啟動備援機器人，但機器人無法連線到 Discord。網路恢復後，機器人會自動連線。

### Q: 如何更新 Pi 上的程式碼？
**A:** 
```bash
cd /opt/yokaro-backup
git pull origin main
sudo systemctl restart yokaro-failover
```

### Q: 可以同時運行多個 Pi 嗎？
**A:** 可以，但需要修改程式碼讓它們協調，避免同時啟動多個備援實體。

---

## 🎯 快速指令參考

```bash
# 查看狀態
sudo systemctl status yokaro-failover

# 查看日誌
sudo journalctl -u yokaro-failover -f

# 重啟服務
sudo systemctl restart yokaro-failover

# 手動更新
cd /opt/yokaro-backup && git pull origin main

# 測試主伺服器連線
curl https://你的主伺服器網址/status

# 查看 Pi IP
hostname -I
```

---

## 🎉 部署完成！

完成以上步驟後，你的備援系統就上線了！

### 運作流程確認：
1. ✅ 主伺服器啟動 → 在埠 8080 提供狀態查詢
2. ✅ Pi 每 30 秒檢查主伺服器狀態
3. ✅ 主伺服器離線（連續 4 次失敗 = 120 秒）→ Pi 啟動備援機器人
4. ✅ 主伺服器恢復 → Pi 檢測到後停止備援機器人

### 下一步：
- 設定外部監控（如 UptimeRobot）監控主伺服器
- 在 Discord 設定通知頻道，當備援啟動時發送提醒
- 定期檢查 Pi 的系統日誌和備援狀態

---

## 📚 相關檔案

- `pi_failover.py` - Pi 端備援監控程式（主動輪詢模式）
- `pi_setup.sh` - 一鍵安裝腳本
- `yokaro.py` - 主機器人程式（包含狀態查詢伺服器）
- `.env` - 環境變數設定

---

## 🐛 回報問題

如果遇到問題，請提供：
1. Pi 型號和 OS 版本：`cat /etc/os-release`
2. 服務狀態：`sudo systemctl status yokaro-failover`
3. 最近日誌：`sudo journalctl -u yokaro-failover -n 50`
4. 網路設定：`hostname -I` 和 `ping -c 3 8.8.8.8`

---

**🍓 祝你的幽芙優(小幽)永不離線！**