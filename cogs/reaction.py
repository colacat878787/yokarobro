import discord
from discord.ext import commands
import random

class ReactionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # AI 反應的隨機機率 (0-100)
        self.ai_reaction_chance = 30  # 30% 機率會 reaction
        
        # 常見的 reaction emoji 列表
        self.common_emojis = [
            '👍', '👎', '😂', '🎉', '😍', '🤔', '😮', '🔥', '❤️', '👏',
            '💯', '✨', '🚀', '💪', '🙌', '👀', '💀', '😭', '🥺', '😡',
            '🤣', '😎', '🤓', '😇', '🥳', '😋', '🤗', '🤩', '😴', '😪'
        ]
    
    @commands.command(name='reaction', aliases=['反應', 'r'])
    async def add_reaction(self, ctx, emoji: str):
        """對回覆的訊息添加表情符號
        
        使用方式：
        1. 先對要反應的訊息點擊回覆
        2. 輸入 !reaction <表情符號>
        3. 指令會自動刪除，並在目標訊息上添加表情
        
        範例：
        !reaction 👍
        !reaction :nerd:
        !reaction 😂
        """
        # 檢查是否為回覆訊息
        if not ctx.message.reference:
            return await ctx.send("❌ 請先對要反應的訊息點擊回覆，再使用此指令！", delete_after=5)
        
        # 取得被回覆的訊息
        try:
            target_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        except:
            return await ctx.send("❌ 找不到目標訊息！", delete_after=5)
        
        # 嘗試添加 reaction
        try:
            # 處理自訂 emoji 格式 (例如 :nerd: 或 <:nerd:123456789>)
            if emoji.startswith(':') and emoji.endswith(':'):
                # 嘗試找到對應的 emoji
                emoji_obj = discord.utils.get(ctx.guild.emojis, name=emoji.strip(':'))
                if emoji_obj:
                    await target_message.add_reaction(emoji_obj)
                else:
                    # 如果找不到，嘗試直接使用
                    await target_message.add_reaction(emoji)
            else:
                # 直接添加 emoji
                await target_message.add_reaction(emoji)
            
            # 刪除指令訊息
            await ctx.message.delete()
            
        except discord.HTTPException as e:
            await ctx.send(f"❌ 添加表情失敗：{str(e)}", delete_after=5)
            await ctx.message.delete()
        except Exception as e:
            await ctx.send(f"❌ 發生錯誤：{str(e)}", delete_after=5)
            await ctx.message.delete()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """AI 偶爾對訊息添加 reaction"""
        # 忽略機器人訊息
        if message.author.bot:
            return
        
        # 忽略 DM
        if not message.guild:
            return

        settings_cog = self.bot.get_cog("ServerSettingsCog")
        if settings_cog and not settings_cog.is_cog_enabled(message.guild.id, self.__class__.__name__):
            return
        
        # 隨機決定是否添加 reaction
        if random.randint(0, 100) > self.ai_reaction_chance:
            return
        
        try:
            # 根據訊息內容選擇合適的 emoji
            emoji = self._pick_emoji_for_message(message.content)
            if emoji:
                await message.add_reaction(emoji)
        except:
            pass
    
    def _pick_emoji_for_message(self, content: str) -> str:
        """根據訊息內容選擇合適的 emoji"""
        content_lower = content.lower()
        
        # 根據關鍵字選擇 emoji
        if any(word in content_lower for word in ['謝謝', '感謝', 'thanks', 'thank', 'thx']):
            return '❤️'
        elif any(word in content_lower for word in ['恭喜', '恭喜發財', '恭喜', 'happy', 'congrats']):
            return '🎉'
        elif any(word in content_lower for word in ['哈哈', '笑', 'lol', 'haha', '笑死']):
            return '😂'
        elif any(word in content_lower for word in ['酷', '厲害', 'amazing', 'awesome', 'cool']):
            return '🔥'
        elif any(word in content_lower for word in ['思考', '想', 'think', 'hmm']):
            return '🤔'
        elif any(word in content_lower for word in ['愛', 'love', '愛你']):
            return '💕'
        elif any(word in content_lower for word in ['哭', '難過', 'sad', 'cry']):
            return '😭'
        elif any(word in content_lower for word in ['生氣', '怒', 'angry', 'mad']):
            return '😡'
        elif any(word in content_lower for word in ['餓', '吃', 'food', 'hungry']):
            return '😋'
        elif any(word in content_lower for word in ['累', '疲勞', 'tired', 'sleepy']):
            return '😴'
        elif any(word in content_lower for word in ['問題', '疑問', '?', '？']):
            return '❓'
        elif any(word in content_lower for word in ['好', '讚', 'good', 'great', 'nice']):
            return '👍'
        elif any(word in content_lower for word in ['不好', '糟', 'bad', 'terrible']):
            return '👎'
        else:
            # 隨機選擇一個 emoji
            return random.choice(self.common_emojis)


async def setup(bot):
    await bot.add_cog(ReactionCog(bot))