export default {
  async fetch(request, env, ctx) {
    return new Response(`
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>授權成功 | 培根 Widget 助手 🥓</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #36393f;
            color: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .card {
            background-color: #2f3136;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 420px;
            border: 1px solid #4f545c;
        }
        h1 {
            color: #43b581;
            margin-bottom: 20px;
            font-size: 28px;
        }
        p {
            color: #b9bbbe;
            font-size: 16px;
            line-height: 1.6;
        }
        .bacon {
            font-size: 64px;
            margin-bottom: 15px;
            animation: bounce 2s infinite;
        }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-12px); }
        }
        .footer {
            margin-top: 30px;
            font-size: 12px;
            color: #72767d;
        }
        .status-msg {
            margin-top: 15px;
            font-weight: bold;
            font-size: 14px;
            color: #ffaa00;
            padding: 10px;
            background: #202225;
            border-radius: 6px;
            border-left: 4px solid #ffaa00;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="bacon">🥓</div>
        <h1>授權成功啦！(喜</h1>
        <p>已成功取得 Discord Widget 授權。</p>
        <div id="status" class="status-msg">正在與 Yokaro 機器人進行同步，請稍候...</div>
        <p class="footer">© 2026 Yokaro Widget v2 培根特製版</p>
    </div>

    <script>
        async function runSync() {
            const statusDiv = document.getElementById("status");
            try {
                // 1. 從網址 hash 提取 access_token 與 state (bot 後台網址)
                const hash = window.location.hash.substring(1);
                const params = new URLSearchParams(hash);
                const accessToken = params.get("access_token");
                const state = params.get("state"); // bot's base URL

                if (!accessToken) {
                    statusDiv.style.color = "#f04747";
                    statusDiv.style.borderLeftColor = "#f04747";
                    statusDiv.innerText = "❌ 錯誤：未取得 access_token，請重新授權！";
                    return;
                }

                if (!state) {
                    statusDiv.style.color = "#f04747";
                    statusDiv.style.borderLeftColor = "#f04747";
                    statusDiv.innerText = "❌ 錯誤：未取得 Bot 後台位址！";
                    return;
                }

                // 2. 向 Discord API 請求當前用戶的資料以獲取 User ID
                statusDiv.innerText = "正在向 Discord 查詢您的身份...";
                const userResp = await fetch("https://discord.com/api/v9/users/@me", {
                    headers: {
                        "Authorization": "Bearer " + accessToken
                    }
                });

                if (!userResp.ok) {
                    throw new Error("無法獲取 Discord 使用者資訊");
                }

                const userData = await userResp.json();
                const userId = userData.id;

                // 3. 將 Token 回傳給 Yokaro Bot 後台
                statusDiv.innerText = "正在儲存 Token 到 Yokaro 機器人伺服器...";
                const botResp = await fetch(state + "/api/widget/callback", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        user_id: userId,
                        access_token: accessToken
                    })
                });

                if (!botResp.ok) {
                    throw new Error("Bot 伺服器連線失敗或拒絕連線");
                }

                statusDiv.style.color = "#43b581";
                statusDiv.style.borderLeftColor = "#43b581";
                statusDiv.innerHTML = "🎉 同步完成！您現在可以安全地<strong>關閉此視窗</strong>，回到 Discord 點選 <strong>「一鍵同步到 Discord ⚡」</strong>！";

            } catch (e) {
                console.error(e);
                statusDiv.style.color = "#f04747";
                statusDiv.style.borderLeftColor = "#f04747";
                statusDiv.innerText = "❌ 發生錯誤：" + e.message + "\\n請確認您的 Bot 網頁後台/隧道是否正常開啟！";
            }
        }

        window.onload = runSync;
    </script>
</body>
</html>
`, {
      headers: {
        "Content-Type": "text/html; charset=utf-8"
      }
    });
  }
};
