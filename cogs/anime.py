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
        """呼叫 AniList GraphQL API 搜尋動畫或漫畫"""
        # kind: "anime" -> ANIME, "manga" -> MANGA
        media_type = "ANIME" if kind == "anime" else "MANGA"
        query_str = """
query ($search: String, $type: MediaType) {
  Page(perPage: 8) {
    media(search: $search, type: $type, sort: SCORE_DESC) {
      id
      title { romaji english native }
      format
      status
      episodes
      chapters
      averageScore
      startDate { year }
      studios { nodes { name } }
      genres
      description
      coverImage { large }
      siteUrl
    }
  }
}
"""
        payload = {
            "query": query_str,
            "variables": {"search": query, "type": media_type},
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://graphql.anilist.co", json=payload, timeout=15
                ) as resp:
                    if resp.status != 200:
                        print(f"[Anime] AniList 回應 {resp.status}")
                        return None
                    data = await resp.json()
                    if "errors" in data:
                        print(f"[Anime] AniList errors: {data['errors']}")
                        return None
            return (data.get("data", {}).get("Page", {}).get("media") or [])
        except Exception as e:
            print(f"[Anime] AniList API 錯誤: {e}")
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
        """建立單一結果的詳細資料 embed (AniList 資料格式)"""
        title_obj = item.get("title") or {}
        romaji = title_obj.get("romaji")
        english = title_obj.get("english")
        native = title_obj.get("native")
        embed_title = romaji or english or native or "?"

        extra = []
        if english and english != embed_title:
            extra.append(english)
        if native and native not in (embed_title, english):
            extra.append(native)
        if extra:
            embed_title = embed_title + "\n" + " / ".join(extra)

        embed = discord.Embed(
            title=embed_title,
            url=item.get("siteUrl"),
            color=0x0f94d1,
        )

        info_items = []
        fmt = item.get("format") or t(gid, "anime.none")
        info_items.append(f"**{t(gid, 'anime.type')}：** {fmt}")
        info_items.append(f"**{t(gid, 'anime.status')}：** {item.get('status') or t(gid, 'anime.none')}")

        score = item.get("averageScore")
        if score:
            info_items.append(f"**{t(gid, 'anime.score')}：** {score / 10:.1f}⭐")
        else:
            info_items.append(f"**{t(gid, 'anime.score')}：** {t(gid, 'anime.none')}")

        # 話數/章節
        field_key = "anime.episodes" if kind == "anime" else "anime.chapters"
        count = item.get("episodes") if kind == "anime" else item.get("chapters")
        count_str = f"{count}" if count is not None else t(gid, "anime.none")
        info_items.append(f"**{t(gid, field_key)}：** {count_str}")

        # 年份
        start_date = item.get("startDate") or {}
        year = start_date.get("year")
        year_str = str(year) if year else t(gid, "anime.none")
        info_items.append(f"**{t(gid, 'anime.year')}：** {year_str}")

        # 製作公司（動畫）／作者（漫畫 - 用 staff）
        if kind == "anime":
            studios = (item.get("studios") or {}).get("nodes") or []
            studio_str = ", ".join(s.get("name", "") for s in studios if s.get("name")) or t(gid, "anime.none")
            info_items.append(f"**{t(gid, 'anime.studios')}：** {studio_str}")

        embed.description = "\n".join(info_items)

        # 類型標籤
        genres = item.get("genres") or []
        if genres:
            genre_str = ", ".join(f"`{g}`" for g in genres)
            embed.add_field(name=t(gid, "anime.genres"), value=genre_str[:1024], inline=False)

        # 劇情簡介
        synopsis = self._strip_html(item.get("description") or t(gid, "anime.no_synopsis"))
        if len(synopsis) > 1024:
            synopsis = synopsis[:1021] + "..."
        embed.add_field(name=t(gid, "anime.synopsis"), value=synopsis[:1024], inline=False)

        # 封面
        cover = item.get("coverImage") or {}
        if cover.get("large"):
            embed.set_image(url=cover["large"])

        embed.set_footer(text="AniList API • https://anilist.co")
        return embed

    @staticmethod
    def _strip_html(text):
        """去除 AniList 描述中的 HTML 標籤"""
        import re as _re
        text = _re.sub(r"<br\s*/?>", "\n", text)
        text = _re.sub(r"<[^>]+>", "", text)
        return text.strip()


async def setup(bot):
    await bot.add_cog(AnimeCog(bot))