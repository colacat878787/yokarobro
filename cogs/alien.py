import discord
from discord.ext import commands
import re

# 注音文/外星文 翻譯字典 (英文鍵盤+注音輸入法)
# 格式: 輸入 -> 中文意思
ALIEN_DICT = {
    # 常用單字
    "ji3": "我", "vu": "我", "wu": "我",
    "ru": "你", "ru/": "你", "n4": "你",
    "t4": "他", "to": "她",
    "su3": "是", "4": "是",
    "ek7": "好", "ek7m4": "好嗎",
    "m4": "嗎", "e/": "了", "0": "的",
    "g4": "個", "g0": "跟", "g0": "和",
    "jo4": "說", "cjo4": "什", "xo": "麼",
    "au4": "要", "xu3": "可", "n5": "呢",
    "gg": "GG", "qq": "QQ",
    "3": "一", ";": "也", "vu;3": "愛",
    "ji3g4": "我的", "ru04": "你好",
    "su3m4": "是嗎", "xj": "小",
    "dl": "大", "vu4": "喔",
    
    # 常用短語
    "ji394su3": "我喜歡你",
    "ji3vu;3": "我愛你",
    "ji3vu;3ru": "我愛你",
    "ek7xj3": "好想",
    "xj3n4": "想你",
    "ek7xj3n4": "好想你",
    "au4m4": "要嗎",
    "cjo4xo": "什麼",
    "bj4": "爆",
    "c04": "超",
    "su3c04": "是超",
    "g4ru": "跟你",
    "au4g0ru": "要跟你",
    "jo4cjo4xo": "說什麼",
    "xu3o4": "可以",
    "xu3o4jo4": "可以說",
    "ek7jo4": "好說",
    "n4au4": "你要",
    "vu4n4": "喔你",
    "a4": "阿",
    "ji3a4": "我阿",
    "6": "啦",
    "su36": "是啦",
    "ek76": "好啦",
    "ji3a46": "我阿啦",
    "2u06": "早安",
    "2u06": "早安",
    "2u06m4": "早安嗎",
    "2u4": "早",
    "u06": "安",
    "ck6": "吃",
    "ck6ek7": "吃好",
    "ck6m4": "吃嗎",
    "ck6ek7m4": "吃好嗎",
    "vu;3": "要",
    "ck6vu;3": "要吃",
    "d06": "到",
    "d06ji3": "到我",
    "d06ru": "到你",
    "s06": "送",
    "s06ru": "送給你",
    "s06ji3": "送我",
    "t4s06": "他送",
    "ji3t4": "我他",
    "ji3s06ru": "我送給你",
    "wu;3": "要",
    "ck6wu;3": "要吃",
    "wu;3ck6": "要吃",
    "au4ck6": "要吃",
    "au4d06": "要到了",
    "g4ru": "跟你",
    "g4n4": "跟你",
    "ji3g0ru": "我跟你",
    "ji3g0n4": "我跟你",
    "ji3g0ru04": "我跟你你好",
    "ru04m4": "你好嗎",
    "ji3ru04": "我你好",
    "ji3ru04m4": "你好嗎",
    "d4": "大",
    "d4ek7": "大好",
    "ek7d4": "好大",
    "xj3": "想",
    "xj3ru": "想你",
    "xj3n4": "想你",
    "ek7xj3ru": "好想你",
    "ek7xj3n4": "好想你",
    "ji3xj3ru": "我想你",
    "ji3xj3n4": "我想你",
    "ji3ek7xj3ru": "我好想你",
    "ji3ek7xj3n4": "我好想你",
    "vu;3ji3": "愛我",
    "vu;3ru": "愛你",
    "vu;3n4": "愛你",
    "ji3vu;3ru": "我愛你",
    "ji3vu;3n4": "我愛你",
    "ji3vu;3ru04": "我愛你你好",
    "ji3vu;3ru04m4": "我愛你你好嗎",
    # 更多拼音組合
    "ji3s06": "我送",
    "s06ek7": "送好",
    "ek7s06": "好送",
    "s06ru04": "送你",
    "s06n4": "送你",
    "ji3s06ru04": "我送你",
    "ji3s06n4": "我送你",
    "ji3s06ru04m4": "我送你你好嗎",
    "ji3xu3o4": "我可以",
    "xu3o4ru04": "可以你",
    "xu3o4ji3": "可以我",
    "ji3xu3o4ru04": "我可以送給你",
    "ji3xu3o4s06ru04": "我可以送給你",
    "ji3xu3o4s06n4": "我可以送給你",
    "ji3xu3o4s06": "我可以送",
    "ek7g4": "好個",
    "ek7g4ru": "好個你",
    "ek7g4n4": "好個你",
    "ji3g4": "我的",
    "ru04g4": "你的",
    "t4g4": "他的",
    "tog4": "她的",
    "g4ru04": "個你",
    "g4g4": "各個",
    "ek7ek7": "好好",
    "ji3ji3": "我我",
    "ruru": "你你",
    "t4t4": "他他",
    "toto": "她她",
    ":-)": "😊",
    ":-(": "😢",
    ":-D": "😄",
    ":-P": "😛",
    "XD": "😆",
    "QQ": "😭",
    "T_T": "😢",
    "OwO": "😳",
    "OuO": "😳",
    "0w0": "😳",
    "0u0": "😳",
}

class AlienCog(commands.Cog):
    """👽 外星文翻譯機 - 自動偵測注音文並回覆"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # 忽略機器人自己的訊息
        if message.author.bot:
            return
        
        # 只處理文字訊息
        if not message.content:
            return
        
        content = message.content.strip()
        
        # 檢查是否為外星文（全部由英文字母和數字組成）
        # 過濾掉一般的英文單字（太長的不處理）
        if not re.match(r'^[a-zA-Z0-9\s/\-:;()]+$', content):
            return
        
        # 移除空白
        clean = content.replace(' ', '').lower()
        
        if len(clean) < 2 or len(clean) > 20:
            return
        
        # 檢查是否為常見英文單字（跳過一般英文）
        common_words = ['hello', 'hi', 'hey', 'yes', 'no', 'ok', 'okay', 'good', 'bad',
                       'love', 'hate', 'like', 'game', 'play', 'stop', 'go', 'come',
                       'help', 'save', 'load', 'new', 'old', 'big', 'small', 'hot',
                       'cold', 'warm', 'cool', 'nice', 'fine', 'well', 'sad', 'happy',
                       'mad', 'glad', 'fun', 'run', 'sit', 'stand', 'walk', 'talk',
                       'see', 'look', 'find', 'keep', 'hold', 'give', 'take', 'make',
                       'do', 'done', 'doing', 'does', 'did', 'has', 'have', 'had',
                       'get', 'got', 'gotten', 'say', 'says', 'said', 'tell', 'told',
                       'think', 'thought', 'know', 'knew', 'known', 'want', 'wanted',
                       'need', 'needed', 'use', 'used', 'using', 'work', 'works',
                       'test', 'tested', 'testing', 'play', 'played', 'playing',
                       'music', 'song', 'video', 'image', 'file', 'code', 'data',
                       'info', 'help', 'about', 'more', 'less', 'most', 'least',
                       'some', 'any', 'all', 'each', 'every', 'both', 'few', 'many',
                       'much', 'no', 'none', 'not', 'only', 'own', 'same', 'very',
                       'just', 'also', 'too', 'very', 'really', 'quite', 'pretty',
                       'still', 'already', 'yet', 'again', 'never', 'ever', 'always',
                       'often', 'sometimes', 'usually', 'now', 'then', 'here', 'there',
                       'where', 'when', 'why', 'how', 'what', 'which', 'who', 'whom',
                       'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
                       'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
                       'his', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'its',
                       'ours', 'theirs', 'a', 'an', 'the', 'and', 'or', 'but', 'if',
                       'because', 'so', 'than', 'as', 'until', 'while', 'of', 'at',
                       'by', 'for', 'with', 'about', 'against', 'between', 'into',
                       'through', 'during', 'before', 'after', 'above', 'below',
                       'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
                       'under', 'again', 'further', 'then', 'once', 'here', 'there',
                       'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
                       'little', 'much', 'many', 'some', 'any', 'no', 'none', 'not',
                       'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
                       'also', 'quite', 'pretty', 'still', 'already', 'yet', 'again',
                       'ever', 'never', 'always', 'often', 'sometimes', 'usually',
                       'well', 'badly', 'early', 'late', 'early', 'fast', 'slow',
                       'hard', 'easily', 'really', 'truly', 'mainly', 'mostly',
                       'nearly', 'almost', 'exactly', 'simply', 'quickly', 'quietly',
                       'loudly', 'carefully', 'carelessly', 'properly', 'correctly',
                       'wrongly', 'fairly', 'unfairly', 'clearly', 'plainly',
                       'similarly', 'differently', 'specially', 'especially',
                       'specifically', 'generally', 'typically', 'normally',
                       'usually', 'commonly', 'rarely', 'seldom', 'never',
                       'always', 'forever', 'ever', 'never', 'now', 'then',
                       'today', 'tomorrow', 'yesterday', 'soon', 'later',
                       'earlier', 'already', 'yet', 'still', 'anymore',
                       'anytime', 'anywhere', 'everywhere', 'somewhere',
                       'nowhere', 'anyway', 'anyhow', 'somehow', 'therefore',
                       'however', 'whatever', 'whenever', 'wherever', 'whoever']
        
        if clean in common_words:
            return
        
        # 檢查是否在翻譯字典中
        if clean in ALIEN_DICT:
            translation = ALIEN_DICT[clean]
            # 回覆訊息
            # 隨機選擇回覆方式
            import random
            replies = [
                f"👽 **外星文翻譯：** {translation}",
                f"🔤 **你說的應該是：** {translation}",
                f"💬 **翻譯：** {translation}",
                f"🤖 **偵測到外星文！** 「{clean}」→ **{translation}**",
                f"📡 **外星訊號解析：** {translation}",
            ]
            await message.reply(random.choice(replies), mention_author=False)
            return
        
        # 若單字不在字典中，但看起來像外星文（全部英文且無意義）
        # 嘗試比對最長的子字串
        if len(clean) >= 3:
            # 嘗試從長到短比對
            for length in range(len(clean), 2, -1):
                for start in range(len(clean) - length + 1):
                    sub = clean[start:start+length]
                    if sub in ALIEN_DICT:
                        translation = ALIEN_DICT[sub]
                        await message.reply(f"👽 **偵測到外星文！** 「{sub}」→ **{translation}**", mention_author=False)
                        return

async def setup(bot):
    await bot.add_cog(AlienCog(bot))