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
    </style>
</head>
<body>
    <div class="card">
        <div class="bacon">🥓</div>
        <h1>授權成功啦！(喜</h1>
        <p>您已成功對此應用程式進行 Widget 授權。</p>
        <p>現在您可以安全地<strong>關閉此視窗</strong>，回到 Discord 點選 <strong>「一鍵同步到 Discord ⚡」</strong> 完成同步！</p>
        <div class="footer">© 2026 Yokaro Widget v2 培根特製版</div>
    </div>
</body>
</html>
`, {
      headers: {
        "Content-Type": "text/html; charset=utf-8"
      }
    });
  }
};
