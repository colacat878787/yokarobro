#!/bin/bash
# ╔════════════════════════════════════════╗
# ║  Yokaro 自動啟動腳本                   ║
# ║  每次開機都會先從 GitHub 強制同步代碼  ║
# ╚════════════════════════════════════════╝

echo "================================================"
echo "🚀 Yokaro 啟動器 v2.0"
echo "================================================"

# 1. 確保 git 設定不需要終端機互動
export GIT_TERMINAL_PROMPT=0

# 2. 強制從 GitHub 拉取最新代碼（完全覆蓋本地）
echo "📡 正在從 GitHub 同步最新代碼..."
if git fetch --all 2>&1; then
    git reset --hard origin/main
    echo "✅ 代碼同步完成！"
else
    echo "⚠️  GitHub 同步失敗，使用本地現有代碼繼續啟動..."
fi

# 3. 安裝/更新 Python 套件 (移除靜音模式以利除錯)
echo "📦 正在安裝 Python 套件..."
python -m pip install -r requirements.txt

echo "================================================"
echo "🤖 正在啟動 Yokaro 機器人..."
echo "================================================"

# 4. 啟動機器人（無限循環自動重啟）
while true; do
    python yokaro.py
    echo "⚠️  機器人已停止，正在重啟..."
    sleep 1
done
