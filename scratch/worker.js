export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const code = url.searchParams.get("code");
    const state = url.searchParams.get("state"); // bot's base URL

    // 如果沒有 code，顯示錯誤頁面
    if (!code) {
      const error = url.searchParams.get("error") || "unknown";
      const errorDesc = url.searchParams.get("error_description") || "未知錯誤";
      return new Response(`
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>授權失敗 | 培根 Widget 助手 🥓</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #36393f; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background-color: #2f3136; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); text-align: center; max-width: 420px; border: 1px solid #4f545c; }
        h1 { color: #f04747; margin-bottom: 20px; }
        p { color: #b9bbbe; font-size: 16px; line-height: 1.6; }
        .error-box { background: #202225; padding: 12px; border-radius: 6px; border-left: 4px solid #f04747; color: #f04747; font-size: 14px; margin-top: 15px; word-break: break-all; }
    </style>
</head>
<body>
    <div class="card">
        <div style="font-size:64px;margin-bottom:15px;">❌</div>
        <h1>授權失敗</h1>
        <p>Discord 沒有回傳授權碼，請回到 Discord 重新點選授權連結。</p>
        <div class="error-box">錯誤代碼: ${error}<br>${errorDesc}</div>
    </div>
</body>
</html>`, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }

    // 有 code，嘗試把 code 傳給 Bot 伺服器換 token
    if (state) {
      try {
        const resp = await fetch(state + "/api/widget/exchange", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code: code }),
        });
        const result = await resp.json();

        if (result.status === "success") {
          return new Response(`
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>授權成功 | 培根 Widget 助手 🥓</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #36393f; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background-color: #2f3136; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); text-align: center; max-width: 420px; border: 1px solid #4f545c; }
        h1 { color: #43b581; margin-bottom: 20px; font-size: 28px; }
        p { color: #b9bbbe; font-size: 16px; line-height: 1.6; }
        .bacon { font-size: 64px; margin-bottom: 15px; animation: bounce 2s infinite; }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
        .footer { margin-top: 30px; font-size: 12px; color: #72767d; }
        .success-box { background: #202225; padding: 12px; border-radius: 6px; border-left: 4px solid #43b581; color: #43b581; font-size: 14px; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="bacon">🥓</div>
        <h1>授權成功啦！(喜</h1>
        <p>歡迎回來，<strong>${result.username || "培根"}</strong>！</p>
        <div class="success-box">🎉 Token 已安全儲存至 Yokaro 機器人！<br>請回到 Discord 點選<strong>「一鍵同步到 Discord ⚡」</strong>即可。</div>
        <p class="footer">© 2026 Yokaro Widget v2 培根特製版<br>您現在可以安全地關閉此視窗。</p>
    </div>
</body>
</html>`, { headers: { "Content-Type": "text/html; charset=utf-8" } });
        } else {
          throw new Error(result.message || "Unknown error from bot server");
        }
      } catch (e) {
        return new Response(`
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>同步失敗 | 培根 Widget 助手 🥓</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #36393f; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background-color: #2f3136; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); text-align: center; max-width: 420px; border: 1px solid #4f545c; }
        h1 { color: #f04747; margin-bottom: 20px; }
        p { color: #b9bbbe; font-size: 16px; line-height: 1.6; }
        .error-box { background: #202225; padding: 12px; border-radius: 6px; border-left: 4px solid #f04747; color: #f04747; font-size: 14px; margin-top: 15px; word-break: break-all; }
    </style>
</head>
<body>
    <div class="card">
        <div style="font-size:64px;margin-bottom:15px;">⚠️</div>
        <h1>Token 交換失敗</h1>
        <p>Worker 已收到授權碼，但無法與 Yokaro 機器人伺服器連線完成 Token 交換。</p>
        <div class="error-box">${e.message}</div>
        <p style="margin-top:20px;color:#72767d;font-size:13px;">請確認您的機器人是否已上線、隧道是否開啟。</p>
    </div>
</body>
</html>`, { headers: { "Content-Type": "text/html; charset=utf-8" } });
      }
    }

    // 沒有 state（不應該發生，但以防萬一）
    return new Response(`
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>設定錯誤 | 培根 Widget 助手 🥓</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #36393f; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background-color: #2f3136; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); text-align: center; max-width: 420px; border: 1px solid #4f545c; }
        h1 { color: #f04747; }
        p { color: #b9bbbe; }
    </style>
</head>
<body>
    <div class="card">
        <h1>缺少 state 參數</h1>
        <p>請回到 Discord 使用 <code>!widget</code> 指令重新產生授權連結。</p>
    </div>
</body>
</html>`, { headers: { "Content-Type": "text/html; charset=utf-8" } });
  }
};
