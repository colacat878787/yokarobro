# 🍓 Pi 備援系統 - 5分鐘快速開始

這是最簡化的部署指南，適合已經有經驗的用戶。

---

## ⚡ 超快速部署

### 在 Raspberry Pi 上執行：

```bash
# 1. 克隆專案
sudo git clone https://github.com/colacat878787/yokarobro.git /opt/yokaro-backup
cd /opt/yokaro-backup

# 2. 執行安裝（需要 sudo）
sudo bash pi_setup.sh

# 3. 設定環境變數
sudo nano /opt/yokaro-backup/.env
# 填入你的 DISCORD_TOKEN

# 4. 重啟服務
sudo systemctl restart yokaro-failover

# 5. 檢查狀態
sudo systemctl status yokaro-failover
```

---

## 📝 主伺服器設定

在你的主伺服器 `.env` 中加入：

```env
MAIN_SERVER_URL=https://你的主伺服器網址
```

**注意：**
- 這個網址必須是 Pi 可以訪問的（公開網址或同一區域網路）
- 例如：`MAIN_SERVER_URL=https://yokaro.wayna1015.ccwu.cc`

重啟主機器人即可。

---

## ✅ 驗證安裝

```bash
# 檢查服務運行
sudo systemctl status yokaro-failover

# 查看日誌
sudo journalctl -u yokaro-failover -f

# 測試狀態頁面
curl http://localhost:8888/status
```

---

## 🎯 完成！

系統會自動：
- ✅ 主伺服器在線時，Pi 待機
- ✅ 主伺服器離線 120 秒後，Pi 自動啟動備援
- ✅ 主伺服器恢復後，Pi 自動關閉備援

---

## 🔧 常用指令

```bash
# 查看狀態
sudo systemctl status yokaro-failover

# 查看日誌
sudo journalctl -u yokaro-failover -f

# 重啟服務
sudo systemctl restart yokaro-failover

# 停止服務
sudo systemctl stop yokaro-failover
```

---

## 📚 詳細說明

遇到問題？請參考 [PI_DEPLOYMENT.md](PI_DEPLOYMENT.md) 取得完整說明。

---

**🍓 搞定！你的備援系統已經上線了！**