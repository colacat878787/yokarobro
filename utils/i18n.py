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
