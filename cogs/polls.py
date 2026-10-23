"""
cogs/polls.py
原生投票系統（Discord Poll API）
指令：
  !poll <時間> <問題> | 選項1 | 選項2 | ...   - 建立原生投票（2~10 個選項）
  !poll <問題> | 選項1 | 選項2                - 不填時間預設 1 天
  !快速投票 <問題>                            - 一小時的 👍/👎 快速投票
時間格式：30m、2h、1d、1w（投票時長最短 1 小時、最長 32 天）
"""

import discord
from discord.ext import commands

from utils.data_store import parse_duration

HAS_POLL = hasattr(discord, "Poll")

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class PollCog(commands.Cog):
    """🗳️ 原生投票系統"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="poll", aliases=["投票"])
    @commands.guild_only()
    async def poll(self, ctx, *, text: str = ""):
        """建立原生投票：!poll [時間] <問題> | 選項1 | 選項2 | ..."""
        text = text.strip()
        if not text:
            await ctx.send(
                "🗳️ **投票用法**\n"
                "`!poll 2h 你想聽什麼歌 | 卡拉永遠OK | 恋愛サーキュレーション`\n"
                "`!poll 明天要不要唱歌 | 要 | 不要`\n"
                "↑ 不填時間預設 **1 天**；支援 `m/h/d/w`，最短 1 小時、最長 32 天。"
            )
            return

        if not HAS_POLL:
            await ctx.send("❌ 這台機器人的 discord.py 版本太舊，不支援原生投票。請升級 discord.py ≥ 2.4。")
            return

        # 解析時間（第一個 token 若可解析成時間就用掉）
        duration_hours = 24
        tokens = text.split()
        if tokens:
            seconds = parse_duration(tokens[0])
            if seconds > 0:
                duration_hours = max(1, min(768, (seconds + 3599) // 3600))
                text = " ".join(tokens[1:]).strip()

        if not text:
            await ctx.send("❌ 請提供投票問題與選項。範例：`!poll 2h 去哪吃飯 | 麥當勞 | 肯德基`")
            return

        # 選項以 | 分隔
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if len(parts) < 2:
            # 只有問題 → 使用表情符號本身做簡易投票
            await ctx.send(
                f"🗳️ **{parts[0] if parts else text}**\n（以 👍 / 👎 投票）",
            )
            msg = await ctx.send("👍＝贊成　👎＝反對")
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            return
        if len(parts) == 2:
            # 只有問題 + 1 個「選項」（可能是忘了打）→ 當作贊成/反對投票
            msg = await ctx.send(f"🗳️ **{parts[0]}**\n全伺服器可用 👍 / 👎 投票！")
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            return

        question = parts[0]
        answers = parts[1:]
        if len(answers) > 10:
            await ctx.send("❌ 選項最多 10 個。")
            return
        if any(len(a) > 55 for a in answers):
            await ctx.send("❌ 有選項文字太長（上限 55 字）。")
            return

        poll = discord.Poll(question=question[:95], duration=duration_hours)
        for idx, answer in enumerate(answers, 1):
            emoji = NUMBER_EMOJIS[idx - 1] if idx <= 10 else None
            poll.add_answer(text=answer[:55], emoji=emoji)
        await ctx.send(poll=poll)

    @commands.command(name="快速投票", aliases=["快投票", "quickpoll"])
    @commands.guild_only()
    async def quickpoll(self, ctx, *, question: str = None):
        """1 小時的贊成/反對快速投票：!快速投票 <問題>"""
        question = (question or "").strip()
        if not question:
            await ctx.send("❌ 請提供問題，例如：`!快速投票 今晚要不要一起唱歌`")
            return
        if not HAS_POLL:
            msg = await ctx.send(f"🗳️ **{question}**\n（👍＝贊成　👎＝反對）")
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            return
        poll = discord.Poll(question=question[:95], duration=1)
        poll.add_answer(text="贊成", emoji="👍")
        poll.add_answer(text="反對", emoji="👎")
        await ctx.send(poll=poll)


async def setup(bot):
    await bot.add_cog(PollCog(bot))
