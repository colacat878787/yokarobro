"""
Yokaro 多語言系統 (i18n)
支援語言: 繁體中文 (zh), 英文 (en), 日文 (ja), 阿拉伯文 (ar)

用法:
    from utils.i18n import t, get_language, set_language, SUPPORTED_LANGUAGES
    text = t(ctx.guild.id, "ping.latency", ms=123)
"""
import json
import os

LANG_FILE = "guild_language.json"

# ===== 支援的語言 =====
SUPPORTED_LANGUAGES = {
    "zh": {"name": "繁體中文", "flag": "🇹🇼", "native": "中文"},
    "en": {"name": "English", "flag": "🇺🇸", "native": "English"},
    "ja": {"name": "日本語", "flag": "🇯🇵", "native": "日本語"},
    "ar": {"name": "العربية", "flag": "🇸🇦", "native": "العربية"},
}

DEFAULT_LANGUAGE = "zh"


# ===== 每伺服器語言儲存 =====
def _load_store():
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_store(store):
    try:
        with open(LANG_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[i18n] 儲存語言設定失敗: {e}")


def get_language(guild_id) -> str:
    """取得伺服器的語言代碼 (無參數時預設 zh)"""
    if guild_id is None:
        return DEFAULT_LANGUAGE
    store = _load_store()
    code = store.get(str(guild_id))
    if code in SUPPORTED_LANGUAGES:
        return code
    return DEFAULT_LANGUAGE


def set_language(guild_id, code: str) -> bool:
    """設定伺服器的語言"""
    if code not in SUPPORTED_LANGUAGES:
        return False
    store = _load_store()
    store[str(guild_id)] = code
    _save_store(store)
    return True


def get_lang_flag(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, {}).get("flag", "🌐")

# ===== 翻譯字典 =====
# key 結構: "功能.項目"
TRANSLATIONS = {
    # ---- 通用 ----
    "common.yes": {"zh": "是", "en": "Yes", "ja": "はい", "ar": "نعم"},
    "common.no": {"zh": "否", "en": "No", "ja": "いいえ", "ar": "لا"},
    "common.success": {"zh": "成功", "en": "Success", "ja": "成功", "ar": "نجاح"},
    "common.error": {"zh": "錯誤", "en": "Error", "ja": "エラー", "ar": "خطأ"},
    "common.not_found": {"zh": "找不到", "en": "Not found", "ja": "見つかりません", "ar": "غير موجود"},
    "common.admin_only": {"zh": "只有管理員可以使用此指令", "en": "Only administrators can use this command", "ja": "管理者のみがこのコマンドを使用できます", "ar": "يمكن للمسؤولين فقط استخدام هذا الأمر"},

    # ---- 語言面板 (lang) ----
    "lang.panel.title": {"zh": "🌐 語言設定", "en": "🌐 Language Settings", "ja": "🌐 言語設定", "ar": "🌐 إعدادات اللغة"},
    "lang.panel.description": {"zh": "請從下方下拉選單選擇伺服器的顯示語言。", "en": "Please select the server's display language from the dropdown below.", "ja": "下のドロップダウンからサーバーの表示言語を選択してください。", "ar": "يرجى اختيار لغة العرض للخادم من القائمة المنسدلة أدناه."},
    "lang.panel.placeholder": {"zh": "選擇語言...", "en": "Select a language...", "ja": "言語を選択...", "ar": "اختر اللغة..."},
    "lang.panel.current": {"zh": "當前語言", "en": "Current language", "ja": "現在の言語", "ar": "اللغة الحالية"},
    "lang.changed": {"zh": "✅ 已將伺服器語言切換為 **{lang}**！", "en": "✅ Server language changed to **{lang}**!", "ja": "✅ サーバーの言語を **{lang}** に変更しました！", "ar": "✅ تم تغيير لغة الخادم إلى **{lang}**!"},
    "lang.admin_only": {"zh": "❌ 只有管理員可以變更伺服器語言！", "en": "❌ Only administrators can change the server language!", "ja": "❌ サーバー言語を変更できるのは管理者のみです！", "ar": "❌ يمكن للمسؤولين فقط تغيير لغة الخادم!"},

    # ---- Ping ----
    "ping.latency": {"zh": "🏓 砰！延遲是 {ms}ms", "en": "🏓 Pong! Latency is {ms}ms", "ja": "🏓 ポン！レイテンシーは {ms}ms", "ar": "🏓 بونغ! زمن الاستجابة {ms}ms"},
# ---- YouTube 訂閱倒數 (ytsubcountdown) ----
    "yt.started.title": {"zh": "📊 YouTube 訂閱數倒數計時已啟動！", "en": "📊 YouTube Subscriber Countdown Started!", "ja": "📊 YouTube 登録者数カウントダウン開始！", "ar": "📊 بدأ العد التنازلي لمشتركي يوتيوب!"},
    "yt.started.channel": {"zh": "**頻道：{channel}**", "en": "**Channel: {channel}**", "ja": "**チャンネル：{channel}**", "ar": "**القناة: {channel}**"},
    "yt.started.target": {"zh": "目標訂閱數：**{target:,}** 🎯", "en": "Target subscribers: **{target:,}** 🎯", "ja": "目標登録者数：**{target:,}** 🎯", "ar": "المشتركون المستهدفون: **{target:,}** 🎯"},
    "yt.started.current": {"zh": "當前訂閱數：**{current:,}** 📊", "en": "Current subscribers: **{current:,}** 📊", "ja": "現在の登録者数：**{current:,}** 📊", "ar": "المشتركون الحاليون: **{current:,}** 📊"},
    "yt.started.remaining": {"zh": "距離目標還差：**{remaining:,}** 📉", "en": "Remaining: **{remaining:,}** 📉", "ja": "目標まで残り：**{remaining:,}** 📉", "ar": "المتبقي: **{remaining:,}** 📉"},
    "yt.started.check": {"zh": "⏰ 每秒檢查一次", "en": "⏰ Checking every 1 second", "ja": "⏰ 1秒ごとに確認", "ar": "⏰ التحقق كل ثانية"},
    "yt.started.notify": {"zh": "📢 訂閱數變化時會通知", "en": "📢 Will notify on subscriber changes", "ja": "📢 登録者数が変化したら通知", "ar": "📢 سيتم الإشعار عند تغير المشتركين"},
    "yt.started.celebrate": {"zh": "🎉 達到目標時會慶祝！", "en": "🎉 Will celebrate when target is reached!", "ja": "🎉 目標達成時にお祝い！", "ar": "🎉 سيتم الاحتفال عند الوصول للهدف!"},
    "yt.started.footer": {"zh": "使用 !ytsubstop 停止計時", "en": "Use !ytsubstop to stop the countdown", "ja": "!ytsubstop で停止", "ar": "استخدم !ytsubstop للإيقاف"},
    "yt.change.title": {"zh": "{emoji} 訂閱數變化！", "en": "{emoji} Subscriber Count Changed!", "ja": "{emoji} 登録者数が変化！", "ar": "{emoji} تغير عدد المشتركين!"},
    "yt.change.from": {"zh": "從 {old:,} → {new:,}", "en": "From {old:,} → {new:,}", "ja": "{old:,} → {new:,}", "ar": "من {old:,} → {new:,}"},
    "yt.change.diff": {"zh": "變化：{diff}", "en": "Change: {diff}", "ja": "変化：{diff}", "ar": "التغيير: {diff}"},
    "yt.celebrate.title": {"zh": "🎉🎊 目標達成！🎊🎉", "en": "🎉🎊 Goal Achieved! 🎊🎉", "ja": "🎉🎊 目標達成！🎊🎉", "ar": "🎉🎊 تم تحقيق الهدف! 🎊🎉"},
    "yt.celebrate.desc": {"zh": "**恭喜！{channel}**\n已達到目標訂閱數：**{target:,}** 🎯\n當前訂閱數：**{current:,}** 🏆", "en": "**Congratulations! {channel}**\nReached target: **{target:,}** 🎯\nCurrent: **{current:,}** 🏆", "ja": "**おめでとう！{channel}**\n目標達成：**{target:,}** 🎯\n現在：**{current:,}** 🏆", "ar": "**تهانينا! {channel}**\nتم الوصول للهدف: **{target:,}** 🎯\nالحالي: **{current:,}** 🏆"},
    "yt.stop.title": {"zh": "⏹️ 訂閱數倒數計時已停止", "en": "⏹️ Subscriber Countdown Stopped", "ja": "⏹️ 登録者数カウントダウン停止", "ar": "⏹️ تم إيقاف العد التنازلي"},
    "yt.stop.desc": {"zh": "計時器已停止，不會再檢查訂閱數變化。", "en": "The countdown has been stopped. No more subscriber checks.", "ja": "カウントダウンを停止しました。", "ar": "تم إيقاف العد التنازلي."},
    "yt.status.title": {"zh": "📊 訂閱數倒數計時狀態", "en": "📊 Subscriber Countdown Status", "ja": "📊 登録者数カウントダウン状況", "ar": "📊 حالة العد التنازلي"},
    "yt.status.target": {"zh": "目標：**{target:,}** 🎯", "en": "Target: **{target:,}** 🎯", "ja": "目標：**{target:,}** 🎯", "ar": "الهدف: **{target:,}** 🎯"},
    "yt.status.current": {"zh": "當前：**{current:,}** 📊", "en": "Current: **{current:,}** 📊", "ja": "現在：**{current:,}** 📊", "ar": "الحالي: **{current:,}** 📊"},
    "yt.status.remaining": {"zh": "剩餘：**{remaining:,}** 📉", "en": "Remaining: **{remaining:,}** 📉", "ja": "残り：**{remaining:,}** 📉", "ar": "المتبقي: **{remaining:,}** 📉"},
    "yt.status.progress": {"zh": "進度：**{progress:.1f}%**", "en": "Progress: **{progress:.1f}%**", "ja": "進捗：**{progress:.1f}%**", "ar": "التقدم: **{progress:.1f}%**"},
    "yt.target.invalid": {"zh": "❌ 目標訂閱數必須大於 0！", "en": "❌ Target subscriber count must be greater than 0!", "ja": "❌ 目標登録者数は 0 より大きい必要があります！", "ar": "❌ يجب أن يكون عدد المشتركين المستهدف أكبر من 0!"},
    "yt.target.too_high": {"zh": "❌ 目標訂閱數不能超過 10 億！", "en": "❌ Target cannot exceed 1 billion!", "ja": "❌ 目標は10億を超えられません！", "ar": "❌ لا يمكن أن يتجاوز الهدف مليار!"},
    "yt.channel.invalid": {"zh": "❌ 無法辨識 YouTube 頻道連結或名稱！", "en": "❌ Cannot recognize YouTube channel!", "ja": "❌ YouTubeチャンネルを認識できません！", "ar": "❌ تعذر التعرف على قناة يوتيوب!"},
    "yt.testing": {"zh": "🔍 正在測試連接 YouTube 頻道...", "en": "🔍 Testing connection to YouTube channel...", "ja": "🔍 YouTubeチャンネルへの接続をテスト中...", "ar": "🔍 جاري اختبار الاتصال بقناة يوتيوب..."},
    "yt.fetch_fail": {"zh": "❌ 無法獲取該頻道的訂閱數，請確認頻道是否存在且公開。", "en": "❌ Cannot fetch subscriber count. Check the channel exists and is public.", "ja": "❌ 登録者数を取得できません。チャンネルが公開されているか確認してください。", "ar": "❌ تعذر الحصول على عدد المشتركين. تحقق من أن القناة موجودة وعامة."},
    "yt.already_tracking": {"zh": "⚠️ 當前頻道已經在追蹤 **{channel}**！", "en": "⚠️ This channel is already tracking **{channel}**!", "ja": "⚠️ このチャンネルは既に **{channel}** を追跡中です！", "ar": "⚠️ هذه القناة تتتبع بالفعل **{channel}**!"},
    "yt.already_target": {"zh": "🎉 太棒了！**{channel}** 已經達到目標訂閱數 {target:,}！", "en": "🎉 Great! **{channel}** already reached the target {target:,}!", "ja": "🎉 素晴らしい！**{channel}** は既に目標 {target:,} に到達しました！", "ar": "🎉 رائع! **{channel}** وصل بالفعل للهدف {target:,}!"},
    "yt.no_active": {"zh": "❌ 當前頻道沒有正在運行的訂閱數倒數計時！", "en": "❌ No active subscriber countdown in this channel!", "ja": "❌ このチャンネルにアクティブなカウントダウンはありません！", "ar": "❌ لا يوجد عد تنازلي نشط في هذه القناة!"},

    # ---- 趣味 (fun) ----
    "fun.fortune.title": {"zh": "🌸 {user} 的今日運勢", "en": "🌸 {user}'s fortune today", "ja": "🌸 {user} の今日の運勢", "ar": "🌸 حظ {user} اليوم"},
    "fun.fortune.result": {"zh": "你的運氣是：**{res}**", "en": "Your luck is: **{res}**", "ja": "あなたの運勢は：**{res}**", "ar": "حظك هو: **{res}**"},
    "fun.fortune.advice": {"zh": "洛洛的叮嚀", "en": "Yokaro's advice", "ja": "ヨカロの助言", "ar": "نصيحة يوكارو"},
    "fun.fortune.date": {"zh": "日期：{date}", "en": "Date: {date}", "ja": "日付：{date}", "ar": "التاريخ: {date}"},
    "fun.fortune.daiji": {"zh": "大吉", "en": "Great Fortune", "ja": "大吉", "ar": "حظ عظيم"},
    "fun.fortune.ji": {"zh": "吉", "en": "Good Fortune", "ja": "吉", "ar": "حظ جيد"},
    "fun.fortune.chuuji": {"zh": "中吉", "en": "Medium Fortune", "ja": "中吉", "ar": "حظ متوسط"},
    "fun.fortune.shoji": {"zh": "小吉", "en": "Small Fortune", "ja": "小吉", "ar": "حظ صغير"},
    "fun.fortune.matsuji": {"zh": "末吉", "en": "Late Fortune", "ja": "末吉", "ar": "حظ متأخر"},
    "fun.fortune.matsu_shoji": {"zh": "末小吉", "en": "Late Small Fortune", "ja": "末小吉", "ar": "حظ متأخر صغير"},
    "fun.fortune.kyo": {"zh": "凶", "en": "Bad Fortune", "ja": "凶", "ar": "حظ سيئ"},
    "fun.fortune.daikyo": {"zh": "大凶", "en": "Great Misfortune", "ja": "大凶", "ar": "حظ سيئ للغاية"},
    "fun.fortune.daiji_d": {"zh": "今天手氣超級好！", "en": "It's your lucky day!", "ja": "今日は運が最高！", "ar": "إنه يوم حظك!"},
    "fun.fortune.ji_d": {"zh": "今天是個充滿活力的一天，加油！", "en": "A day full of energy, go go go!", "ja": "元気いっぱいの一日，頑張って！", "ar": "يوم مليء بالطاقة، هيا!"},
    "fun.fortune.chuuji_d": {"zh": "心情愉悅，一切都會順利的。", "en": "Stay positive, everything will be fine.", "ja": "いい気分ですべてがうまくいく。", "ar": "كن إيجابياً، كل شيء سيكون بخير."},
    "fun.fortune.shoji_d": {"zh": "平穩安定，也是一種幸福。", "en": "Stable and peaceful, that's happiness.", "ja": "穏やかで安定、それも幸せ。", "ar": "استقرار وسلام، هذه سعادة."},
    "fun.fortune.matsuji_d": {"zh": "快結束的今天也會有好事的。", "en": "Good things come at day's end.", "ja": "終わり際にもいいことがある。", "ar": "أشياء جيدة ستحدث قبل نهاية اليوم."},
    "fun.fortune.matsu_shoji_d": {"zh": "生活中有些微小的小確幸等著你。", "en": "Small joys await you.", "ja": "小さな幸せが待っている。", "ar": "أفراح صغيرة تنتظرك."},
    "fun.fortune.kyo_d": {"zh": "今天要注意點，別漏掉重要訊息。", "en": "Be careful, don't miss important info.", "ja": "大事な情報を見逃さないように。", "ar": "كن حذراً، لا تفوت معلومات مهمة."},
    "fun.fortune.daikyo_d": {"zh": "沒關係，再衰一次明天就會轉運了！", "en": "Don't worry, tomorrow will be better!", "ja": "明日には運が好転する！", "ar": "لا تقلق، غداً سيكون أفضل!"},
    "fun.slot.title": {"zh": "🎰 優卡洛拉霸機 🎰", "en": "🎰 Yokaro Slot Machine 🎰", "ja": "🎰 ヨカロ スロット 🎰", "ar": "🎰 آلة يوكارو 🎰"},
    "fun.slot.result": {"zh": "結果", "en": "Result", "ja": "結果", "ar": "النتيجة"},
    "fun.slot.jackpot": {"zh": "⚡ **中大獎！！！** ⚡ 恭喜你！", "en": "⚡ **JACKPOT!!!** ⚡ Congratulations!", "ja": "⚡ **ジャックポット！！** ⚡ おめでとう！", "ar": "⚡ **جائزة كبرى!!!** ⚡ مبروك!"},
    "fun.slot.small": {"zh": "✨ **小有驚喜！** ✨ 連中兩個！", "en": "✨ **Small surprise!** ✨ Two matched!", "ja": "✨ **小さな喜び！** ✨ 2個そろった！", "ar": "✨ **مفاجأة صغيرة!** ✨ اثنان متطابقان!"},
    "fun.slot.again": {"zh": "再挑戰一次吧！相信下次一定能中的！", "en": "Try again! You'll win next time!", "ja": "もう一度挑戦！次はきっと勝てる！", "ar": "حاول مرة أخرى! ستربح المرة القادمة!"},
    "fun.slot.footer": {"zh": "由 {user} 啟動", "en": "Started by {user}", "ja": "{user} が開始", "ar": "بدأ بواسطة {user}"},
    "fun.giveaway.title": {"zh": "🎉 抽獎時間到！", "en": "🎉 Giveaway Time!", "ja": "🎉 プレゼント抽選！", "ar": "🎉 وقت السحب!"},
    "fun.giveaway.desc": {"zh": "獎品：**{prize}**\n時間：**{duration}** 秒\n\n點擊下方的 🎉 參與抽獎！", "en": "Prize: **{prize}**\nDuration: **{duration}s**\n\nClick 🎉 to enter!", "ja": "賞品：**{prize}**\n時間：**{duration}秒**\n\n🎉 をクリックして参加！", "ar": "الجائزة: **{prize}**\nالمدة: **{duration} ثانية**\n\nاضغط 🎉 للمشاركة!"},
    "fun.giveaway.footer": {"zh": "發起人：{user}", "en": "Host: {user}", "ja": "主催者：{user}", "ar": "المضيف: {user}"},
    "fun.giveaway.none": {"zh": "沒人參加抽獎嗎？獎品被洛洛自己拿走囉！", "en": "No one joined? Yokaro keeps the prize!", "ja": "参加者がいない？賞品はヨカロのもの！", "ar": "لم يشارك أحد؟ يوكارو سيحتفظ بالجائزة!"},
    "fun.giveaway.winner": {"zh": "🎉 恭喜 {user} 抽中了 **{prize}**！", "en": "🎉 Congratulations {user}, you won **{prize}**!", "ja": "🎉 おめでとう {user}！**{prize}** を獲得！", "ar": "🎉 مبروك {user}، فزت بـ **{prize}**!"},
    "fun.giveaway.error": {"zh": "抽獎結算時發生了錯誤！", "en": "An error occurred while settling the giveaway!", "ja": "抽選の確定中にエラーが発生！", "ar": "حدث خطأ أثناء إتمام السحب!"},
    "fun.duihua.notfound": {"zh": "❌ 找不到路徑：`{path}`，請檢查資料夾是否存在！", "en": "❌ Path not found: `{path}`. Check the folder exists!", "ja": "❌ パスが見つかりません：`{path}`。フォルダを確認してください！", "ar": "❌ المسار غير موجود: `{path}`. تحقق من وجود المجلد!"},
    "fun.duihua.novideo": {"zh": "❌ 該資料夾內沒有影片檔案！", "en": "❌ No video files in that folder!", "ja": "❌ そのフォルダに動画がありません！", "ar": "❌ لا توجد ملفات فيديو في هذا المجلد!"},

    # ---- 抱抱 (hug) ----
    "hug.title": {"zh": "🐾 抱抱時間！", "en": "🐾 Hug Time!", "ja": "🐾 ハグタイム！", "ar": "🐾 وقت العناق!"},
    "hug.target": {"zh": "💝 傳送對象", "en": "💝 Sent to", "ja": "💝 送る相手", "ar": "💝 أُرسل إلى"},
    "hug.received": {"zh": "{mention} 收到了滿滿的愛心！", "en": "{mention} received lots of love!", "ja": "{mention} はたくさんの愛を受け取った！", "ar": "تلقى {mention} الكثير من الحب!"},
    "hug.footer": {"zh": "✨ 洛洛的小爪子永遠為你敞開 ✨", "en": "✨ Yokaro's paws are always open for you ✨", "ja": "✨ ヨカロの手はいつでも君のために ✨", "ar": "✨ أيدي يوكارو مفتوحة دائماً لك ✨"},
    "hug.anim.1": {"zh": "伸出可愛的小爪爪緊緊抱住你 🤗", "en": "Reaches out cute little paws and hugs you tight 🤗", "ja": "可愛い小さな手でぎゅっと抱きしめる🤗", "ar": "يمد مخالب لطيفة ويعانقك بحرارة 🤗"},
    "hug.anim.2": {"zh": "用軟綿綿的爪子環抱住你 💕", "en": "Wraps you in soft fluffy paws 💕", "ja": "ふわふわの手で包み込む💕", "ar": "يلفك بمخالب ناعمة رقيقة 💕"},
    "hug.anim.3": {"zh": "輕輕地用爪子拍拍你的背 🐾", "en": "Gently pats your back with a paw 🐾", "ja": "そっと背中をトントン🐾", "ar": "يربت على ظهرك بلطف 🐾"},
    "hug.anim.4": {"zh": "用溫暖的小爪子給你一個大大的擁抱 ✨", "en": "Gives you a big warm hug with tiny paws ✨", "ja": "温かい小さな手で大きなハグ✨", "ar": "يعانقك عناقاً كبيراً بمخالب دافئة ✨"},
    "hug.anim.5": {"zh": "伸出毛茸茸的爪子緊緊摟住你 🥰", "en": "Wraps fluffy paws tightly around you 🥰", "ja": "もふもふの手でぎゅっと抱く🥰", "ar": "يلفك بمخالب ناعمة بحنان 🥰"},
    "hug.anim.6": {"zh": "用QQ的爪子輕輕抱著你搖啊搖 🎀", "en": "Holds you gently with squishy paws and sways 🎀", "ja": "ぷにぷにの手でゆらゆら🎀", "ar": "يحتضنك بمخالب ناعمة ويتمايل 🎀"},
    "hug.anim.7": {"zh": "伸出小手手給你一個溫暖的抱抱 🌸", "en": "Reaches out small hands for a warm hug 🌸", "ja": "小さな手で温かいハグ🌸", "ar": "يمد يديه الصغيرتين لعناق دافئ 🌸"},
    "hug.anim.8": {"zh": "用軟軟的爪子緊緊纏住你 💝", "en": "Wraps soft paws tightly around you 💝", "ja": "柔らかい手でしっかり抱く💝", "ar": "يلفك بمخالب ناعمة بشدة 💝"},

    # ---- Minecraft 伺服器狀態 (mcstatus) ----
    "mc.online": {"zh": "🟢 {addr}", "en": "🟢 {addr}", "ja": "🟢 {addr}", "ar": "🟢 {addr}"},
    "mc.offline": {"zh": "🔴 {addr} — 離線", "en": "🔴 {addr} — Offline", "ja": "🔴 {addr} — オフライン", "ar": "🔴 {addr} — غير متصل"},
    "mc.version": {"zh": "版本", "en": "Version", "ja": "バージョン", "ar": "الإصدار"},
    "mc.players": {"zh": "玩家", "en": "Players", "ja": "プレイヤー", "ar": "اللاعبون"},
    "mc.latency": {"zh": "延遲", "en": "Latency", "ja": "遅延", "ar": "زمن الاستجابة"},
    "mc.footer": {"zh": "結果已快取 60 秒。請確認 IP 與連接埠是否正確。", "en": "Result cached for 60s. Check IP and port.", "ja": "結果は60秒キャッシュ。IPとポートを確認してください。", "ar": "النتيجة مخزنة 60 ثانية. تحقق من IP والمنفذ."},
    "mc.refused": {"zh": "連線被拒絕（伺服器可能已關閉）", "en": "Connection refused (server may be offline)", "ja": "接続が拒否されました（オフラインかも）", "ar": "تم رفض الاتصال (قد يكون الخادم مغلقاً)"},
    "mc.timeout": {"zh": "連線逾時（超過 5 秒）", "en": "Connection timed out (over 5s)", "ja": "接続がタイムアウト（5秒超）", "ar": "انتهت مدة الاتصال (أكثر من 5 ثوان)"},
    "mc.unknown": {"zh": "未知", "en": "Unknown", "ja": "不明", "ar": "غير معروف"},

    # ---- 等級 (levels) ----
    "level.up": {"zh": "🎉 **{user}** 升到了 **等級 {level}**！", "en": "🎉 **{user}** leveled up to **Level {level}**!", "ja": "🎉 **{user}** が **Lv.{level}** にアップ！", "ar": "🎉 **{user}** ارتفع إلى **المستوى {level}**!"},
    "level.profile.title": {"zh": "🌸 {user} 的冒險紀錄", "en": "🌸 {user}'s adventure record", "ja": "🌸 {user} の冒険記録", "ar": "🌸 سجل مغامرات {user}"},
    "level.profile.level": {"zh": "等級", "en": "Level", "ja": "レベル", "ar": "المستوى"},
    "level.profile.xp": {"zh": "目前 XP", "en": "Current XP", "ja": "現在のXP", "ar": "نقاط الخبرة الحالية"},
    "level.no_data": {"zh": "洛洛還不認識你，快多聊天賺 XP 吧！", "en": "Yokaro doesn't know you yet. Chat more to earn XP!", "ja": "まだあなたを知りません。話してXPを稼ごう！", "ar": "يوكارو لا يعرفك بعد. تحدث أكثر لكسب النقاط!"},

    # ---- 匿名告白 (confession) ----
    "confession.modal.title": {"zh": "💌 匿名告白", "en": "💌 Anonymous Confession", "ja": "💌 匿名の告白", "ar": "💌 اعتراف مجهول"},
    "confession.target_label": {"zh": "告白對象", "en": "Confession target", "ja": "告白の相手", "ar": "الهدف"},
    "confession.target_ph": {"zh": "寫下你想告白的人的暱稱或名字...", "en": "Write the name of who you confess to...", "ja": "告白したい相手の名前を...", "ar": "اكتب اسم من تعترف له..."},
    "confession.content_label": {"zh": "你想說的話", "en": "Your message", "ja": "伝えたいこと", "ar": "رسالتك"},
    "confession.content_ph": {"zh": "寫下你想說的話...（支援文字、網址、圖片連結）", "en": "Write your message... (text, URLs, images)", "ja": "伝えたいことを書いてください...", "ar": "اكتب رسالتك...(نص، روابط، صور)"},
    "confession.sig_label": {"zh": "署名（可選）", "en": "Signature (optional)", "ja": "署名（任意）", "ar": "التوقيع (اختياري)"},
    "confession.sig_ph": {"zh": "例如：一個暗戀你的人、匿名者", "en": "e.g. someone who likes you, anonymous", "ja": "例：密かに想う人、匿名", "ar": "مثال: شخص معجب بك، مجهول"},
    "confession.wall": {"zh": "💌 匿名告白牆", "en": "💌 Anonymous Confession Wall", "ja": "💌 匿名の告白ウォール", "ar": "💌 جدار الاعترافات المجهول"},
    "confession.give": {"zh": "**💕 給 {target}：**\n\n{content}", "en": "**💕 To {target}:**\n\n{content}", "ja": "**💕 {target} へ：**\n\n{content}", "ar": "**💕 إلى {target}:**\n\n{content}"},
    "confession.published": {"zh": "💌 你的告白已成功發佈在 {channel} 頻道！\n**給 {target}：** {content}...", "en": "💌 Your confession was published in {channel}!\n**To {target}:** {content}...", "ja": "💌 あなたの告白が {channel} に公開されました！\n**{target} へ：**{content}...", "ar": "💌 تم نشر اعترافك في {channel}!\n**إلى {target}:** {content}..."},
    "confession.like": {"zh": "💌 我也想知道", "en": "💌 I want to know too", "ja": "💌 私も知りたい", "ar": "💌 أريد أن أعرف أيضاً"},
    "confession.already": {"zh": "你已經按過囉！", "en": "You already clicked!", "ja": "もう押しました！", "ar": "لقد ضغطت بالفعل!"},
    "confession.like_done": {"zh": "你對這則告白產生了共鳴！💕", "en": "You resonated with this confession! 💕", "ja": "この告白に共感しました！💕", "ar": "لقد تفاعلت مع هذا الاعتراف! 💕"},
    "confession.send_prompt": {"zh": "💌 請填寫告白內容：", "en": "💌 Please fill in your confession:", "ja": "💌 告白内容を記入してください：", "ar": "💌 يرجى تعبئة اعترافك:"},
    "confession.write_btn": {"zh": "✍️ 寫下告白", "en": "✍️ Write confession", "ja": "✍️ 告白を書く", "ar": "✍️ اكتب اعترافك"},
    "confession.anon": {"zh": "匿名者", "en": "Anonymous", "ja": "匿名", "ar": "مجهول"},

    # ---- 遊戲 (games) ----
    "games.pjsk.howto": {"zh": "❓ 如何使用 pjsekai 指令", "en": "❓ How to use the pjsekai command", "ja": "❓ pjsekai コマンドの使い方", "ar": "❓ كيفية استخدام أمر pjsekai"},
    "games.pjsk.howto_desc": {"zh": "請提供您的 **Project Sekai 遊戲內 ID** (不是 Discord ID 喔！)", "en": "Provide your **Project Sekai in-game ID** (not Discord ID!)", "ja": "**Project Sekai のゲーム内ID** を提供してください（Discord IDではありません）", "ar": "قدم **معرفك داخل لعبة بروجكت سيكاي** (وليس معرف ديسكورد)"},
    "games.pjsk.usage": {"zh": "📌 用法", "en": "📌 Usage", "ja": "📌 使い方", "ar": "📌 الاستخدام"},
    "games.pjsk.where": {"zh": "🔍 哪裡找 ID？", "en": "🔍 Where to find your ID?", "ja": "🔍 IDはどこで見つける？", "ar": "🔍 أين تجد المعرّف؟"},
    "games.pjsk.footer": {"zh": "目前僅支援日服 (JP Server) 查詢", "en": "Currently supports JP Server only", "ja": "現在は日本サーバーのみ対応", "ar": "يدعم خادم اليابان فقط حالياً"},
    "games.pjsk.ndigits": {"zh": "❌ 遊戲 ID 應該只包含數字喔！", "en": "❌ The game ID should only contain numbers!", "ja": "❌ ゲームIDは数字のみにしてください！", "ar": "❌ يجب أن يحتوي معرف اللعبة على أرقام فقط!"},
    "games.pjsk.unknown_player": {"zh": "未知玩家", "en": "Unknown player", "ja": "不明なプレイヤー", "ar": "لاعب غير معروف"},
    "games.pjsk.nocomment": {"zh": "無簡介", "en": "No bio", "ja": "自己紹介なし", "ar": "لا سيرة"},
    "games.pjsk.field_name": {"zh": "👤 玩家名稱", "en": "👤 Player name", "ja": "👤 プレイヤー名", "ar": "👤 اسم اللاعب"},
    "games.pjsk.field_rank": {"zh": "⭐ 等級 (Rank)", "en": "⭐ Level (Rank)", "ja": "⭐ ランク", "ar": "⭐ المستوى"},
    "games.pjsk.field_id": {"zh": "🆔 遊戲 ID", "en": "🆔 Game ID", "ja": "🆔 ゲームID", "ar": "🆔 معرف اللعبة"},
    "games.pjsk.field_event": {"zh": "🏆 最近活動排名", "en": "🏆 Recent event ranking", "ja": "🏆 最近のイベント順位", "ar": "🏆 ترتيب الحدث الأخير"},
    "games.pjsk.rank_place": {"zh": "第 {rank} 名", "en": "Rank {rank}", "ja": "{rank} 位", "ar": "المرتبة {rank}"},
    "games.pjsk.field_bio": {"zh": "📝 簡介", "en": "📝 Bio", "ja": "📝 自己紹介", "ar": "📝 السيرة"},
    "games.pjsk.mystery": {"zh": "這個玩家很神祕，什麼都沒寫。", "en": "This player is mysterious and wrote nothing.", "ja": "このプレイヤーは神秘的で何も書いていない。", "ar": "هذا اللاعب غامض ولم يكتب شيئاً."},
    "games.pjsk.notfound": {"zh": "❌ 找不到 ID 為 `{uid}` 的玩家。", "en": "❌ Player with ID `{uid}` not found.", "ja": "❌ そのIDのプレイヤーは見つかりません。", "ar": "❌ لم يتم العثور على لاعب بالمعرف `{uid}`."},
    "games.pjsk.api_error": {"zh": "❌ API 暫時沒反應 (代碼: {code})，洛洛待會再試！", "en": "❌ API temporarily not responding (code: {code}), try again later!", "ja": "❌ APIが一時的に応答しません（コード:{code}）", "ar": "❌ واجهة البرمجة غير مستجيبة مؤقتاً (الرمز: {code})"},
    "games.pjsk.fatal": {"zh": "API 壞掉惹，洛洛修不完嗚嗚...", "en": "The API is down and I can't fix it...", "ja": "APIが壊れた...直せない...", "ar": "واجهة البرمجة معطلة ولا أستطيع إصلاحها..."},

    # ---- HTTP Cat (httpcat) ----
    "httpcat.range": {"zh": "❌ HTTP 狀態碼必須在 100-599 之間！", "en": "❌ HTTP status code must be between 100-599!", "ja": "❌ HTTPステータスコードは100から599の間でなければなりません！", "ar": "❌ يجب أن يكون رمز حالة HTTP بين 100-599!"},
    "httpcat.footer": {"zh": "Powered by http.cat | 請求者：{user}", "en": "Powered by http.cat | Requested by {user}", "ja": "Powered by http.cat | 依頼者：{user}", "ar": "Powered by http.cat | طلب من قبل {user}"},

    # ---- Twitter/X (twitter) ----
    "twitter.tracked": {"zh": "嗷～開始追蹤 **{user}** 的推特！會在這裡發送通知喔。", "en": "Now tracking **{user}**'s tweets! Notifications will be sent here.", "ja": "**{user}** のツイートの追跡を開始！ここに通知します。", "ar": "بدأ تتبع تغريدات **{user}**! سيتم إرسال الإشعارات هنا."},
    "twitter.already": {"zh": "嗷～**{user}** 已經在名單裡了。", "en": "**{user}** is already on the list.", "ja": "**{user}** は既にリストにいます。", "ar": "**{user}** موجود بالفعل في القائمة."},
    "twitter.new": {"zh": "🔔 {user} 發布了新推文！", "en": "🔔 {user} posted a new tweet!", "ja": "🔔 {user} が新しいツイートを投稿！", "ar": "🔔 نشر {user} تغريدة جديدة!"},
    "twitter.footer": {"zh": "洛洛推特情報站 (via Nitter RSS)", "en": "Yokaro Twitter feed (via Nitter RSS)", "ja": "ヨカロのX情報 (Nitter RSS)", "ar": "تغذية يوكارو على تويتر (عبر Nitter RSS)"},
    "twitter.invalid": {"zh": "❌ 無法辨識 X/Twitter 個人檔案連結！請貼上類似 `https://x.com/username`、`https://twitter.com/username` 或 `@username` 的格式。", "en": "❌ Could not recognize that X/Twitter profile link! Please use something like `https://x.com/username`, `https://twitter.com/username` or `@username`.", "ja": "❌ X/Twitter のプロフィールリンクを認識できません！`https://x.com/username` や `@username` のような形式で貼ってください。", "ar": "❌ تعذر التعرف على رابط ملف X/Twitter الشخصي! استخدم `https://x.com/username` أو `@username`."},
    "twitter.updated": {"zh": "👌 已將 **{user}** 的貼文頻道更新為當前頻道！新貼文會發送到這裡。", "en": "👌 Updated **{user}**'s feed to this channel! New posts will be sent here.", "ja": "👌 **{user}** の配信先をこのチャンネルに更新しました！新しい投稿はここに送られます。", "ar": "👌 تم تحديث قناة تغريدات **{user}** إلى هذه القناة! سيتم إرسال المنشورات الجديدة هنا."},
    "twitter.stopped": {"zh": "⏹️ 已停止追蹤 **{user}**，此頻道不再接收該帳號的貼文。", "en": "⏹️ Stopped tracking **{user}**; this channel will no longer receive their posts.", "ja": "⏹️ **{user}** の追跡を停止しました。このチャンネルには投稿が届きません。", "ar": "⏹️ تم إيقاف تتبع **{user}**؛ لن تستقبل هذه القناة منشوراتهم بعد الآن."},
    "twitter.notfound": {"zh": "❌ 目前沒有追蹤 **{user}**，不需要停止。", "en": "❌ **{user}** is not being tracked, so there is nothing to stop.", "ja": "❌ **{user}** は追跡されていないため、停止するものはありません。", "ar": "❌ **{user}** غير متتبع، لذلك لا يوجد شيء لإيقافه."},

    # ---- 動漫搜索 (anime) ----
    "anime.searching": {"zh": "🔍 正在搜尋 **{query}**...", "en": "🔍 Searching for **{query}**...", "ja": "🔍 **{query}** を検索中...", "ar": "🔍 جاري البحث عن **{query}**..."},
    "anime.no_results": {"zh": "❌ 找不到「{query}」的相關結果。", "en": "❌ No results found for \"{query}\".", "ja": "❌ 「{query}」の結果が見つかりません。", "ar": "❌ لم يتم العثور على نتائج لـ \"{query}\"."},
    "anime.error": {"zh": "❌ Jikan API 暫時無法使用，請稍後再試。", "en": "❌ Jikan API is temporarily unavailable. Please try again later.", "ja": "❌ Jikan API が一時的に利用できません。後でもう一度お試しください。", "ar": "❌ واجهة Jikan غير متاحة مؤقتاً. حاول مرة أخرى لاحقاً."},
    "anime.select": {"zh": "🎯 請選擇要查看的結果...", "en": "🎯 Select a result to view...", "ja": "🎯 表示する結果を選択...", "ar": "🎯 اختر نتيجة لعرضها..."},
    "anime.title": {"zh": "標題", "en": "Title", "ja": "タイトル", "ar": "العنوان"},
    "anime.type": {"zh": "類型", "en": "Type", "ja": "種類", "ar": "النوع"},
    "anime.status": {"zh": "狀態", "en": "Status", "ja": "ステータス", "ar": "الحالة"},
    "anime.episodes": {"zh": "話數", "en": "Episodes", "ja": "話数", "ar": "الحلقات"},
    "anime.chapters": {"zh": "章節", "en": "Chapters", "ja": "話数", "ar": "الفصول"},
    "anime.score": {"zh": "評分", "en": "Score", "ja": "評価", "ar": "التقييم"},
    "anime.year": {"zh": "推出年份", "en": "Year", "ja": "公開年", "ar": "السنة"},
    "anime.genres": {"zh": "類型標籤", "en": "Genres", "ja": "ジャンル", "ar": "التصنيفات"},
    "anime.studios": {"zh": "製作公司", "en": "Studios", "ja": "制作会社", "ar": "الاستوديوهات"},
    "anime.author": {"zh": "作者", "en": "Author(s)", "ja": "作者", "ar": "المؤلفون"},
    "anime.synopsis": {"zh": "劇情簡介", "en": "Synopsis", "ja": "あらすじ", "ar": "الملخص"},
    "anime.none": {"zh": "無", "en": "None", "ja": "なし", "ar": "لا شيء"},
    "anime.no_synopsis": {"zh": "（尚無簡介）", "en": "(No synopsis yet)", "ja": "（あらすじはまだありません）", "ar": "(لا يوجد ملخص بعد)"},
    "anime.keyword": {"zh": "💡 提示：可在名稱前加「漫畫」來搜尋漫畫，例如 `!動漫搜索 漫畫 火影`", "en": "💡 Tip: add \"manga\" before the name to search manga, e.g. `!animesearch manga Naruto`", "ja": "💡 ヒント：名前の前に「漫画」を付けると漫画を検索します", "ar": "💡 تلميح: أضف \"مانغا\" قبل الاسم للبحث عن مانغا"},
}

# ===== 語言代碼 -> 該語言的指令別名對照 =====
# 用於每個伺服器註冊專屬語言的指令版本
COMMAND_ALIASES = {
    "zh": {
        "ytsubcountdown": ["訂閱倒數", "yt訂閱倒數"],
        "ytsubstop": ["停止訂閱倒數", "ytstop"],
        "ytsubstatus": ["訂閱狀態", "ytstatus"],
        "lang": ["語言", "language"],
    },
    "en": {
        "ytsubcountdown": ["ytsubcountdown"],
        "ytsubstop": ["ytsubstop"],
        "ytsubstatus": ["ytsubstatus"],
        "lang": ["lang", "language"],
    },
    "ja": {
        "ytsubcountdown": ["登録者カウントダウン"],
        "ytsubstop": ["カウントダウン停止"],
        "ytsubstatus": ["カウントダウン状況"],
        "lang": ["言語", "げんご"],
    },
    "ar": {
        "ytsubcountdown": ["عدتنازلي"],
        "ytsubstop": ["إيقافعد"],
        "ytsubstatus": ["حالةالعد"],
        "lang": ["لغة", "اللغة"],
    },
}


def translate(lang: str, key: str, **kwargs) -> str:
    """根據語言取得翻譯文字，並格式化參數"""
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def t(guild_id, key: str, **kwargs) -> str:
    """根據伺服器語言翻譯 (主要使用入口)"""
    lang = get_language(guild_id)
    return translate(lang, key, **kwargs)


def t_lang(lang: str, key: str, **kwargs) -> str:
    """根據指定語言翻譯"""
    return translate(lang, key, **kwargs)
