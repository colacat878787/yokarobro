#!/bin/bash
# 🍓 Raspberry Pi Zero 2W 備援系統安裝腳本
# 使用方式: chmod +x pi_setup.sh && ./pi_setup.sh

echo "🍓 幽芙優(小幽) Raspberry Pi 備援系統安裝程式"
echo "================================================"

# 檢查是否為 root
if [ "$EUID" -ne 0 ]; then
    echo "❌ 請使用 sudo 執行此腳本: sudo ./pi_setup.sh"
    exit 1
fi

# 檢查系統
echo "📡 系統資訊:"
uname -a
echo ""

# 安裝必要套件
echo "📦 正在安裝系統依賴..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git ffmpeg

# 建立工作目錄
BOT_DIR="/opt/yokaro-backup"
echo "📁 建立工作目錄: $BOT_DIR"
mkdir -p "$BOT_DIR"
cd "$BOT_DIR"

# 如果目錄已經有程式碼就更新，否則克隆
if [ -d ".git" ]; then
    echo "📥 更新現有程式碼..."
    git pull origin main
else
    echo "📥 克隆程式碼..."
    git clone https://github.com/colacat878787/yokarobro.git .
fi

# 建立虛擬環境
echo "🐍 建立 Python 虛擬環境..."
python3 -m venv venv
source venv/bin/activate

# 安裝 Python 依賴
echo "📦 安裝 Python 依賴..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# 檢查 .env 檔案
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️ 找不到 .env 檔案！"
    echo "請建立 .env 並設定以下內容："
    echo "  DISCORD_TOKEN=你的備援機器人token"
    echo "  GEMINI_API_KEY=你的gemini_key"
    echo "  GENIUS_ACCESS_TOKEN=你的genius_token"
    echo ""
    echo "💡 你可以從主伺服器複製 .env 過來"
    exit 1
fi

echo ""
echo "✅ 安裝完成！"

# 建立 systemd 服務
echo "🔧 建立 systemd 服務..."
cat > /etc/systemd/system/yokaro-failover.service << 'EOF'
[Unit]
Description=Yokaro Failover Monitor (Raspberry Pi)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/yokaro-backup
ExecStart=/opt/yokaro-backup/venv/bin/python3 /opt/yokaro-backup/pi_failover.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable yokaro-failover
systemctl start yokaro-failover

echo ""
echo "✅ systemd 服務已建立並啟動！"
echo ""
echo "📋 常用指令："
echo "  查看狀態: sudo systemctl status yokaro-failover"
echo "  查看日誌: sudo journalctl -u yokaro-failover -f"
echo "  重啟服務: sudo systemctl restart yokaro-failover"
echo "  停止服務: sudo systemctl stop yokaro-failover"
echo ""
echo "📡 心跳監聽埠: 8888"
echo "🔍 狀態查詢: http://<Pi_IP>:8888/status"
echo ""
echo "🍓 備援系統已就緒！當主伺服器離線時會自動接管！"