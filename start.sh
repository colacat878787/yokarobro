#!/bin/bash
# ╔════════════════════════════════════════╗
# ║  Yokaro 自動啟動腳本                   ║
# ║  每次開機都會先從 GitHub 強制同步代碼  ║
# ╚════════════════════════════════════════╝

echo "================================================"
echo "🚀 Yokaro 啟動器 v2.0"
echo "================================================"

# 無論由 systemd、cron 或其他目錄呼叫，都固定使用本腳本所在的專案目錄。
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
echo "📁 工作目錄: $PWD"

# 1. 確保 git 設定不需要終端機互動
export GIT_TERMINAL_PROMPT=0

# 2. 強制從 GitHub 拉取最新代碼（完全覆蓋本地）
echo "📡 正在從 GitHub 同步最新代碼..."
if git fetch --all 2>&1; then
    git reset --hard origin/main
    echo "✅ 代碼同步完成！"
    echo "📌 實際版本: $(git rev-parse --short HEAD)"
else
    echo "⚠️  GitHub 同步失敗，使用本地現有代碼繼續啟動..."
fi

if [[ -f "cogs/user_settings.py" ]]; then
    echo "✅ 已找到 cogs/user_settings.py"
else
    echo "❌ 找不到 cogs/user_settings.py，請檢查工作目錄與 Git 同步結果"
fi

# 3. 安裝/更新 Python 套件 (移除靜音模式以利除錯)
echo "📦 正在安裝 Python 套件..."
python -m pip install -r requirements.txt
python -m pip install mcstatus==11.1.0
# yt-dlp 需要保持最新，否則 YouTube 串流 URL 會失效
echo "🔄 正在升級 yt-dlp 至最新版本..."
python -m pip install -U yt-dlp

echo "================================================"
echo "🤖 正在啟動 Yokaro 機器人..."
echo "================================================"

# 4. 啟動機器人（無限循環自動重啟）
while true; do
    python yokaro.py
    echo "⚠️  機器人已停止，正在重啟..."
    sleep 1
done
