"""
Yokaro 語言切換系統 (!lang)
顯示英文面板，讓管理員選擇伺服器語言。
根據伺服器語言註冊專屬指令別名。
"""
import discord
from discord.ext import commands
from utils.i18n import (
    SUPPORTED_LANGUAGES, get_language, set_language,
    get_lang_flag, t, t_lang, COMMAND_ALIASES,
)


class LanguageSelect(discord.ui.Select):
    """語言選擇下拉選單"""

    def __init__(self, cog, current_lang: str, guild_id: int):
        self.cog = cog
        self.guild_id = guild_id
        options = []
        for code, info in SUPPORTED_LANGUAGES.items():
            options.append(discord.SelectOption(
                label=info["native"],
                description=info["name"],
                value=code,
                emoji=info["flag"],
                default=(code == current_lang),
            ))
        super().__init__(
            placeholder=t_lang("en", "lang.panel.placeholder"),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="language_select",
        )

    async def callback(self, interaction: discord.Interaction):
        # 只有管理員可以變更
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                t_lang("en", "lang.admin_only"), ephemeral=True
            )

        code = self.values[0]
        set_language(self.guild_id, code)
        info = SUPPORTED_LANGUAGES[code]

        # 更新指令別名
        self.cog.apply_command_aliases(interaction.guild)

        embed = discord.Embed(
            title=t_lang("en", "lang.panel.title"),
            description=f"{info['flag']} {t_lang('en', 'lang.changed', lang=info['native'])}",
            color=0x00ff00,
        )
        embed.set_footer(text=t_lang("en", "lang.panel.current") + f": {info['name']}")
        # 重建選單讓勾選更新
        new_view = LanguagePanelView(self.cog, self.guild_id)
        await interaction.response.edit_message(embed=embed, view=new_view)


class LanguagePanelView(discord.ui.View):
    """包含語言選擇的下拉選單畫面"""

    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=300)
        current = get_language(guild_id)
        self.add_item(LanguageSelect(cog, current, guild_id))


class LanguageCog(commands.Cog):
    """🌐 語言切換系統"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="lang", aliases=["語言", "language", "languagemenu", "言語", "لغة"])
    @commands.has_permissions(administrator=True)
    async def lang(self, ctx):
        """🌐 (管理員) 切換伺服器的顯示語言 (中文/英文/日文/阿拉伯文)"""
        guild_id = ctx.guild.id
        current = get_language(guild_id)
        current_info = SUPPORTED_LANGUAGES[current]

        embed = discord.Embed(
            title=t_lang("en", "lang.panel.title"),
            description=t_lang("en", "lang.panel.description"),
            color=0x00aaff,
        )
        embed.add_field(
            name=t_lang("en", "lang.panel.current"),
            value=f"{current_info['flag']} {current_info['name']}",
            inline=False,
        )

        view = LanguagePanelView(self, guild_id)
        await ctx.send(embed=embed, view=view)

    def apply_command_aliases(self, guild):
        """根據伺服器語言，為指令註冊本地化的別名"""
        try:
            lang = get_language(guild.id)
            all_known = set()
            for _lang, mapping in COMMAND_ALIASES.items():
                for aliases in mapping.values():
                    all_known.update(aliases)

            for cmd in self.bot.commands:
                if cmd.name in COMMAND_ALIASES.get(lang, {}):
                    # 移除所有已知的語言別名 (清除舊語言)
                    new_aliases = [a for a in cmd.aliases if a not in all_known]
                    # 加入當前語言的別名
                    for a in COMMAND_ALIASES[lang][cmd.name]:
                        if a not in new_aliases:
                            new_aliases.append(a)
                    cmd.aliases = new_aliases
                    print(f"🌐 [{lang}] 已為指令 !{cmd.name} 設定語言別名")

    async def register_all_guilds(self):
        """啟動後為已設定語言的伺服器註冊指令別名"""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                self.apply_command_aliases(guild)
            except Exception as e:
                print(f"[Language] 初始化別名失敗: {e}")

    async def cog_load(self):
        """啟動時註冊所有既有伺服器的語言別名"""
        self.bot.loop.create_task(self.register_all_guilds())


async def setup(bot):
    await bot.add_cog(LanguageCog(bot))