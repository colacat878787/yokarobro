# 🤖 幽芙優 (小幽) - Yokaro Discord Bot

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Discord.py](https://img.shields.io/badge/Discord.py-2.0%2B-purple)
![License](https://img.shields.io/badge/License-MIT-green)

**幽芙優 (小幽)** 是一個功能豐富的 Discord 機器人，提供 AI 對話、音樂播放、錄影系統、經濟系統、股票市場等多種功能。支援自動備援機制，確保服務永不中斷。

> 💡 **名稱由來**：原本叫做「優卡洛」，2026-07-31 全面改版後改名為「幽芙優」，但開發者還是習慣叫它優卡洛 :D

---

## ✨ 主要功能

### 🤖 AI 與智慧對話
- **多模型支援**：Google Gemini、OpenAI GPT、本地 Ollama
- **智能對話**：自然語言理解與回應
- **上下文記憶**：記住對話歷史

### 🎵 音樂與語音
- **YouTube/Spotify 播放**：支援多平台音樂搜尋與播放
- **歌詞顯示**：自動搜尋並顯示歌詞
- **播放清單管理**：佇列、跳過、暫停、音量控制
- **247 模式**：全天候自動播放
- **音樂推薦**：智能推薦相似歌曲

### 🎥 錄影系統
- **語音錄製**：高品質語音捕捉
- **AI 自動剪輯**：智能剪輯精彩片段
- **字幕燒製**：自動生成字幕並嵌入影片
- **頭像動畫**：顯示發言者頭像

### 💰 經濟與博弈
- **虛擬貨幣系統**：打工、簽到、領取獎勵
- **銀行系統**：存款、提款、轉帳
- **股票市場**：即時股價、買賣交易
- **抽卡系統**：每日簽到抽卡，稀有度系統
- **一番賞**：星空主題抽獎
- **信用卡系統**：先買後付功能

### 🎮 遊戲與娛樂
- **狼人殺**：多人語音遊戲
- **等級系統**：聊天獲得經驗值
- **排行榜**：競爭與成就
- **每日運勢**：隨機籤詩
- **外星文翻譯機**：趣味文字變換

### 🛡️ 管理與安全
- **黑名單系統**：禁止特定用戶使用
- **驗證系統**：防止機器人加入
- **票單系統**：客服支援
- **Modmail**：私訊客服系統
- **自動審核**：內容過濾

### 📊 實用工具
- **天氣查詢**：即時天氣資訊
- **股票報價**：美股/台股即時行情
- **維基百科搜尋**：快速查詢資料
- **Twitter 整合**：推文通知
- **TTS 語音**：文字轉語音

---

## 🚀 快速開始

### 需求

- Python 3.9 或更高版本
- FFmpeg
- Git
- Discord Bot Token

### 安裝

```bash
# 1. 克隆專案
git clone https://github.com/colacat878787/yokarobro.git
cd yokarobro

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 設定環境變數
cp .env.example .env
nano .env  # 填入你的設定

# 4. 啟動機器人
python3 yokaro.py
```

### 環境變數設定

在 `.env` 檔案中設定：

```env
# Discord Bot Token（必須）
DISCORD_TOKEN=你的Discord_Bot_Token

# AI 功能（可選）
GEMINI_API_KEY=你的Gemini_API_Key
OPENAI_API_KEY=你的OpenAI_API_Key
AI_MODEL=gemini-2.5-flash

# 音樂功能（可選）
GENIUS_ACCESS_TOKEN=你的Genius_Token
DISCORD_CLIENT_SECRET=你的Client_Secret

# 備援系統（可選）
PI_IP=192.168.1.100
```

---

## 🍓 備援系統（Raspberry Pi）

當主伺服器離線時，Raspberry Pi Zero 2W 會自動啟動備援機器人，確保服務不中斷。

### 運作流程
1. **主伺服器**在埠 8080 提供狀態查詢服務
2. **Pi 每 30 秒**檢查主伺服器狀態（主動輪詢）
3. **連續 4 次失敗**（120 秒）→ Pi 自動啟動備援機器人
4. **主伺服器恢復** → Pi 檢測到後自動關閉備援

### 特色功能
- ✅ **跨地區支援** - Pi 主動輪詢，不限區域網路
- ✅ **自動偵測** - 120 秒無回應自動啟動備援
- ✅ **自動恢復** - 主伺服器恢復後自動關閉備援
- ✅ **開機自啟** - systemd 服務實現開機自動啟動
- ✅ **狀態監控** - HTTP 端點提供狀態查詢

### 快速部署

```bash
# 在 Pi 上執行
git clone https://github.com/colacat878787/yokarobro.git /opt/yokaro-backup
cd /opt/yokaro-backup
sudo bash pi_setup.sh
```

### 主伺服器設定

在主伺服器的 `.env` 中加入：
```env
MAIN_SERVER_URL=https://你的主伺服器網址
```

📖 **詳細說明**：請參考 [PI_DEPLOYMENT.md](PI_DEPLOYMENT.md)

---

## 📁 專案結構

```
yokarobro/
├── yokaro.py              # 主程式入口
├── pi_failover.py         # Pi 備援監控程式
├── pi_setup.sh            # Pi 安裝腳本
├── pi_check.py            # Pi 環境檢查腳本
├── .env                   # 環境變數（不公開）
├── .env.pi.example        # Pi 環境變數範例
├── requirements.txt       # Python 依賴
├── .gitignore            # Git 忽略清單
├── PI_DEPLOYMENT.md      # Pi 部署說明
├── README.md             # 專案說明
├── cogs/                 # 功能模組
│   ├── ai.py            # AI 對話
│   ├── music.py         # 音樂播放
│   ├── record.py        # 錄影系統
│   ├── economy.py       # 經濟系統
│   ├── stocks.py        # 股票系統
│   ├── levels.py        # 等級系統
│   ├── security.py      # 安全管理
│   ├── admin.py         # 管理員功能
│   └── ...              # 更多模組
├── utils/               # 工具函式
│   ├── config.py
│   ├── data_store.py
│   └── mobile_status.py
└── assets/              # 資源檔案
    └── fonts/
```

---

## 🎯 使用指南

### 基本指令

| 指令 | 別名 | 說明 |
|------|------|------|
| `!help` | `!幫助` | 顯示功能說明面板 |
| `!ping` | `!延遲` | 檢查機器人延遲 |
| `!version` | `!版本` | 查看版本資訊 |
| `!reboot` | `!重啟` | 重啟機器人（管理員） |

### 音樂指令

| 指令 | 說明 |
|------|------|
| `!play [歌名]` | 播放音樂 |
| `!skip` | 跳過當前歌曲 |
| `!stop` | 停止播放 |
| `!queue` | 查看播放清單 |
| `!247` | 開啟全天候模式 |

### 經濟指令

| 指令 | 說明 |
|------|------|
| `!錢包` | 查看餘額 |
| `!打工` | 賺取金幣 |
| `!簽到` | 每日簽到 |
| `!抽卡` | 抽卡系統 |
| `!股市` | 股票交易 |

---

## 🛠️ 系統管理

### 查看服務狀態（Pi）

```bash
sudo systemctl status yokaro-failover
```

### 查看日誌

```bash
# Pi 備援系統日誌
sudo journalctl -u yokaro-failover -f

# 主機器人日誌
tail -f pi_failover.log
```

### 重啟服務

```bash
# 重啟 Pi 備援服務
sudo systemctl restart yokaro-failover

# 重啟主機器人
# 使用 !reboot 指令或手動重啟
```

---

## 🔧 開發指南

### 新增功能模組

1. 在 `cogs/` 目錄建立新檔案，例如 `cogs/myfeature.py`
2. 繼承 `commands.Cog` 並實作功能
3. 在 `yokaro.py` 的 `initial_extensions` 中註冊

範例：

```python
from discord.ext import commands

class MyFeature(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mycommand(self, ctx):
        await ctx.send("Hello!")

async def setup(bot):
    await bot.add_cog(MyFeature(bot))
```

### 執行測試

```bash
# 檢查 Pi 環境
python3 pi_check.py

# 測試特定功能
python3 -c "from cogs.music import MusicCog; print('OK')"
```

---

## 📊 系統需求

### 主伺服器
- CPU: 2 核心以上
- RAM: 2GB 以上
- 儲存: 10GB 以上
- 網路: 穩定連線

### Raspberry Pi 備援
- 硬體: Raspberry Pi Zero 2W
- OS: Raspberry Pi OS (Bookworm)
- RAM: 512MB（建議 1GB）
- 儲存: 16GB MicroSD 卡
- 網路: Wi-Fi 或有線網路

---

## 🛡️ 安全建議

1. **使用獨立 Bot Token**
   - 主伺服器和備援使用不同的 Discord Bot
   - 避免同時上線導致衝突

2. **保護敏感資訊**
   - 不要將 `.env` 檔案提交到 Git
   - 定期更換 API Key

3. **限制存取**
   - 設定 Pi 防火牆，只允許主伺服器 IP 存取心跳埠
   - 使用強密碼保護伺服器

4. **定期更新**
   - 定期執行 `git pull` 更新程式碼
   - 更新系統套件

---

## 🐛 故障排除

### 機器人無法啟動

```bash
# 檢查 .env 設定
cat .env | grep DISCORD_TOKEN

# 測試 Discord 連線
python3 -c "import discord; print('Discord.py OK')"

# 查看錯誤日誌
python3 yokaro.py
```

### Pi 備援沒有啟動

```bash
# 檢查服務狀態
sudo systemctl status yokaro-failover

# 查看日誌
sudo journalctl -u yokaro-failover -n 100

# 執行檢查腳本
python3 pi_check.py

# 測試主伺服器連線
curl https://你的主伺服器網址/status
```

### 音樂播放失敗

```bash
# 檢查 FFmpeg
ffmpeg -version

# 重新安裝依賴
pip install --upgrade discord.py[voice] yt-dlp
```

---

## 📈 效能監控

### Pi 狀態監控

```bash
# CPU 溫度
vcgencmd measure_temp

# CPU 使用率
top -bn1 | grep "Cpu(s)"

# 記憶體使用
free -h

# 磁碟使用
df -h
```

### 外部監控

建議使用以下工具監控：
- **UptimeRobot** - 監控 Pi 狀態頁面
- **Discord Webhook** - 備援啟動通知
- **Grafana** - 系統效能圖表

---

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

1. Fork 專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

---

## 📝 更新日誌

### 2026-07-31 - 全面改版 (幽芙優)
- ✨ 改名為「幽芙優 (小幽)」
- 🤖 新增 AI 對話系統（Gemini/OpenAI/Ollama）
- 🎥 全新錄影系統（AI 自動剪輯）
- 💰 經濟系統全面升級
- 📈 股票市場系統
- 🎮 狼人殺遊戲
- 🍓 Raspberry Pi 備援系統
- 🎨 全新 UI/UX 設計

---

## 📄 授權

此專案採用 MIT 授權 - 詳見 [LICENSE](LICENSE) 檔案

---

## 👨‍💻 開發者

**ColaCat** - [GitHub](https://github.com/colacat878787)

---

## 🙏 致謝

- [discord.py](https://github.com/Rapptz/discord.py) - Discord API  wrapper
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 音樂下載
- [Google Gemini](https://ai.google.dev/) - AI 模型
- [Raspberry Pi Foundation](https://www.raspberrypi.org/) - 硬體平台

---

## 📞 聯絡方式

- **GitHub Issues**: [回報問題](https://github.com/colacat878787/yokarobro/issues)
- **Discord**: 邀請機器人到你的伺服器

---

**🍓 讓幽芙優(小幽)陪伴你的伺服器，永不離線！**

*最後更新：2026-07-31*