"""
Yokaro 動漫搜索系統 (!動漫搜索)
使用 Jikan API (MyAnimeList 非官方 API) - 免費、免 API Key
搜尋動畫或漫畫的詳細資料。
"""
import urllib.parse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from utils.i18n import t

JIKAN_API = "https://api.jikan.moe/v4"


class AnimeResultsSelect(discord.ui.Select):
    """結果選單：讓使用者選擇要查看的搜尋結果"""

    def __init__(self, cog, guild_id, kind, results):
        self.cog = cog
        self.guild_id = guild_id
        self.kind = kind
        self.results = results
        options = []
        for idx, item in enumerate(results):
            title = (item.get("title_english") or item.get("title") or "?")[:90]
            score = item.get("score")
            desc = f"{t(guild_id, 'anime.score')}: {score}" if score else None
            options.append(discord.SelectOption(
                label=title[:100],
                description=(desc or "")[:100],
                value=str(idx),
            ))
        super().__init__(
            placeholder=t(guild_id, "anime.select"),
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id=f"anime_sel_{guild_id}_{id(self)}",
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            idx = int(self.values[0])
            if idx >= len(self.results):
                return
            item = self.results[idx]
            embed = self.cog._build_embed(self.guild_id, self.kind, item)
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            print(f"[Anime] 選擇結果失敗: {e}")


class AnimeSearchView(discord.ui.View):
    def __init__(self, cog, guild_id, kind, results):
        super().__init__(timeout=120)
        self.add_item(AnimeResultsSelect(cog, guild_id, kind, results))


class AnimeCog(commands.Cog):
    """🎬 動漫搜索系統 (Jikan / MyAnimeList)"""

    def __init__(self, bot):
        self.bot = bot

    async def _search(self, query, kind):
        """呼叫 Jikan API 搜尋動畫或漫畫"""
        url = f"{JIKAN_API}/{kind}?q={urllib.parse.quote(query)}&limit=8&order_by=score&sort=desc"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
            return data.get("data", [])
        except Exception as e:
            print(f"[Anime] Jikan API 錯誤: {e}")
            return None

    @commands.hybrid_command(name='動漫搜索', aliases=['animesearch', '動漫搜尋', '搜索動漫'])
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def anime_search(self, ctx, *, query: str):
        """搜尋動畫/漫畫的詳細資料：!動漫搜索 <動漫或漫畫名稱>（前方加"漫畫"可搜漫畫）"""
        gid = ctx.guild.id if ctx.guild else None
        kind = "anime"
        content = query.strip()
        words = content.split(maxsplit=1)
        if words:
            first = words[0].lower()
            if first in ("漫畫", "manga"):
                kind = "manga"
                content = words[1] if len(words) > 1 else ""
            elif first in ("動畫", "動漫", "anime"):
                kind = "anime"
                content = words[1] if len(words) > 1 else ""

        if not content:
            return await ctx.send(
                t(gid, "anime.no_results", query=query) + "\n\n" + t(gid, "anime.keyword")
            )

        await ctx.send(t(gid, "anime.searching", query=content))
        results = await self._search(content, kind)

        if not results:
            return await ctx.send(t(gid, "anime.no_results", query=content))

        if len(results) == 1:
            embed = self._build_embed(gid, kind, results[0])
            return await ctx.send(embed=embed)

        view = AnimeSearchView(self, gid, kind, results)
        await ctx.send(
            t(gid, "anime.select"),
            view=view,
        )
    def _build_embed(self, gid, kind, item):
        """建立單一結果的詳細資料 embed"""
        title = item.get("title") or "?"
        title_eng = item.get("title_english")
        embed_title = title if not title_eng or title_eng == title else f"{title} ({title_eng})"

        # 用日文/羅馬拼音標題當 fallback
        alt = item.get("title_japanese") or item.get("title_romaji")
        if alt and alt not in (title, title_eng):
            embed_title = f"{embed_title}\n{alt}"

        embed = discord.Embed(
            title=embed_title,
            url=item.get("url"),
            color=0x0f94d1,
        )

        info_items = []
        info_items.append(f"**{t(gid, 'anime.type')}：** {item.get('type') or t(gid, 'anime.none')}")
        info_items.append(f"**{t(gid, 'anime.status')}：** {item.get('status') or t(gid, 'anime.none')}")

        score = item.get("score")
        score_str = f"{score}⭐" if score else t(gid, "anime.none")
        info_items.append(f"**{t(gid, 'anime.score')}：** {score_str}")

        # 話數/章節
        field_key = "anime.episodes" if kind == "anime" else "anime.chapters"
        count = item.get("episodes") if kind == "anime" else item.get("chapters")
        count_str = f"{count}" if count is not None else t(gid, "anime.none")
        info_items.append(f"**{t(gid, field_key)}：** {count_str}")

        # 年份
        aired = item.get("aired", {})
        prop = aired.get("prop") if isinstance(aired, dict) else None
        year = None
        if prop and prop.get("from") and prop["from"].get("year"):
            year = prop["from"]["year"]
        elif isinstance(aired, dict) and aired.get("from"):
            from_obj = aired["from"]
            if isinstance(from_obj, dict):
                year = from_obj.get("year")
        year_str = str(year) if year else t(gid, "anime.none")
        info_items.append(f"**{t(gid, 'anime.year')}：** {year_str}")

        # 製作公司 / 作者
        if kind == "anime":
            studios = item.get("studios") or []
            studio_str = ", ".join(s.get("name", "") for s in studios if s.get("name")) or t(gid, "anime.none")
            info_items.append(f"**{t(gid, 'anime.studios')}：** {studio_str}")
        else:
            authors = item.get("authors") or []
            author_str = ", ".join(a.get("name", "") for a in authors if a.get("name")) or t(gid, "anime.none")
            info_items.append(f"**{t(gid, 'anime.author')}：** {author_str}")

        embed.description = "\n".join(info_items)

        # 類型標籤
        genres = item.get("genres") or []
        if genres:
            genre_str = ", ".join(f"`{g.get('name', '')}`" for g in genres if g.get("name"))
            embed.add_field(name=t(gid, "anime.genres"), value=genre_str[:1024], inline=False)

        # 劇情簡介
        synopsis = item.get("synopsis") or t(gid, "anime.no_synopsis")
        if len(synopsis) > 1024:
            synopsis = synopsis[:1021] + "..."
        embed.add_field(name=t(gid, "anime.synopsis"), value=synopsis[:1024], inline=False)

        # 封面
        images = item.get("images", {})
        jpg = images.get("jpg", {})
        if jpg.get("large_image_url"):
            embed.set_image(url=jpg["large_image_url"])
        elif jpg.get("image_url"):
            embed.set_thumbnail(url=jpg["image_url"])

        embed.set_footer(text="Jikan API (MyAnimeList) • https://api.jikan.moe")
        return embed


async def setup(bot):
    await bot.add_cog(AnimeCog(bot))