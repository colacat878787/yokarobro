import discord
from discord.ext import commands
import json
import os
import re
from datetime import datetime, timedelta

class ProfanityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.profanity_file = "profanity_list.json"
        self.warnings_file = "profanity_warnings.json"
        
        # 預設髒話庫（多國語言）
        self.default_profanity = {
            "zh-TW": ["幹", "靠北", "靠腰", "媽的", "他媽的", "王八蛋", "垃圾", "白痴", "智障", "廢物", "死媽", "操", "幹你", "幹你娘", "機掰", "雞掰", "哭啊", "靠邀", "幹你老師"],
            "zh-CN": ["操", "草", "妈的", "他妈", "傻逼", "脑残", "废物", "狗屎", "去死", "滚", "贱人", "婊子", "龟儿子", "王八蛋", "日你"],
            "en": ["fuck", "shit", "asshole", "bitch", "cunt", "dick", "piss", "bastard", "damn", "hell", "cock", "pussy", "nigga", "retard", "stfu"],
            "ja": ["クソ", "死ね", "バカ", "アホ", "くたばれ", "ちくしょう", "くそ", "カス", "ゴミ"],
            "ko": ["씨발", "좆", "병신", "개새끼", "미친", "죽어", "꺼져", "븅신", "호로"]
        }
        
        self.profanity_list = self._load_profanity()
        self.warnings = self._load_warnings()
    
    def _load_profanity(self):
        """載入髒話庫"""
        if os.path.exists(self.profanity_file):
            try:
                with open(self.profanity_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return self.default_profanity.copy()
    
    def _save_profanity(self):
        """儲存髒話庫"""
        try:
            with open(self.profanity_file, 'w', encoding='utf-8') as f:
                json.dump(self.profanity_list, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 儲存髒話庫失敗: {e}")
    
    def _load_warnings(self):
        """載入警告記錄"""
        if os.path.exists(self.warnings_file):
            try:
                with open(self.warnings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_warnings(self):
        """儲存警告記錄"""
        try:
            with open(self.warnings_file, 'w', encoding='utf-8') as f:
                json.dump(self.warnings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 儲存警告記錄失敗: {e}")
    
    def _contains_profanity(self, text):
        """檢查文字是否包含髒話"""
        text_lower = text.lower()
        for lang, words in self.profanity_list.items():
            for word in words:
                if word.lower() in text_lower:
                    return word
        return None
    
    def _censor_text(self, text, profanity_word):
        """將髒話中間的字碼掉"""
        if not profanity_word:
            return text
        
        # 找到髒話的位置
        pattern = re.compile(re.escape(profanity_word), re.IGNORECASE)
        matches = list(pattern.finditer(text))
        
        if not matches:
            return text
        
        # 只遮罩第一個匹配的髒話
        match = matches[0]
        start, end = match.span()
        word = text[start:end]
        
        # 保留前後字，中間用*取代
        if len(word) <= 2:
            censored = word[0] + '*' * (len(word) - 1)
        else:
            censored = word[0] + '*' * (len(word) - 2) + word[-1]
        
        return text[:start] + censored + text[end:]
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """監聽訊息，過濾髒話"""
        # 忽略機器人訊息
        if message.author.bot:
            return
        
        # 忽略DM
        if not message.guild:
            return
        
        # 檢查是否包含髒話
        profanity_word = self._contains_profanity(message.content)
        if profanity_word:
            # 記錄警告
            user_id = str(message.author.id)
            guild_id = str(message.guild.id)
            
            if guild_id not in self.warnings:
                self.warnings[guild_id] = {}
            if user_id not in self.warnings[guild_id]:
                self.warnings[guild_id][user_id] = {
                    "count": 0,
                    "warnings": [],
                    "last_warning": None
                }
            
            # 增加警告次數
            self.warnings[guild_id][user_id]["count"] += 1
            self.warnings[guild_id][user_id]["last_warning"] = datetime.now().isoformat()
            self.warnings[guild_id][user_id]["warnings"].append({
                "word": profanity_word,
                "time": datetime.now().isoformat(),
                "channel": message.channel.id
            })
            self._save_warnings()
            
            # 遮罩訊息
            censored = self._censor_text(message.content, profanity_word)
            
            # 發送警告訊息
            warning_msg = f"⚠️ {message.author.mention} 請勿使用不雅用語！\n"
            warning_msg += f"已遮罩：`{censored}`\n"
            warning_msg += f"警告次數：{self.warnings[guild_id][user_id]['count']} 次"
            
            await message.channel.send(warning_msg)
            
            # 自動刪除原始訊息（可選）
            try:
                await message.delete()
            except:
                pass
    
    @commands.command(name='脏话列表', aliases=['髒話列表', 'profanity'])
    @commands.has_permissions(administrator=True)
    async def profanity_list(self, ctx, action=None, *, content=None):
        """管理髒話列表"""
        if not action:
            # 顯示目前列表
            embed = discord.Embed(
                title="📝 髒話列表管理",
                description="使用方式：\n"
                           "`!脏话列表 list` - 查看所有髒話\n"
                           "`!脏话列表 set <語言> <詞彙>` - 添加髒話\n"
                           "`!脏话列表 remove <語言> <詞彙>` - 移除髒話\n"
                           "`!脏话列表 sync` - 同步預設髒話庫\n"
                           "`!脏话列表 clear` - 清空自定義髒話",
                color=0x3498db
            )
            await ctx.send(embed=embed)
            return
        
        if action == "list":
            # 列出所有髒話
            msg = "**📋 髒話庫內容：**\n\n"
            for lang, words in self.profanity_list.items():
                msg += f"**{lang}** ({len(words)} 個):\n"
                msg += f"{', '.join(words[:10])}"
                if len(words) > 10:
                    msg += f" ... (+{len(words)-10}個)"
                msg += "\n\n"
            
            # 分割訊息避免超過限制
            if len(msg) > 2000:
                parts = [msg[i:i+1900] for i in range(0, len(msg), 1900)]
                for part in parts:
                    await ctx.send(part)
            else:
                await ctx.send(msg)
        
        elif action == "set":
            # 添加髒話
            if not content:
                return await ctx.send("❌ 請指定語言和詞彙！\n使用方式：`!脏话列表 set <語言> <詞彙>`")
            
            parts = content.split(maxsplit=1)
            if len(parts) < 2:
                return await ctx.send("❌ 格式錯誤！\n使用方式：`!脏话列表 set <語言> <詞彙>`")
            
            lang, words = parts
            word_list = [w.strip() for w in words.split(',') if w.strip()]
            
            if lang not in self.profanity_list:
                self.profanity_list[lang] = []
            
            added = []
            for word in word_list:
                if word not in self.profanity_list[lang]:
                    self.profanity_list[lang].append(word)
                    added.append(word)
            
            self._save_profanity()
            await ctx.send(f"✅ 已添加 {len(added)} 個髒話到 {lang}：{', '.join(added)}")
        
        elif action == "remove":
            # 移除髒話
            if not content:
                return await ctx.send("❌ 請指定語言和詞彙！\n使用方式：`!脏话列表 remove <語言> <詞彙>`")
            
            parts = content.split(maxsplit=1)
            if len(parts) < 2:
                return await ctx.send("❌ 格式錯誤！\n使用方式：`!脏话列表 remove <語言> <詞彙>`")
            
            lang, words = parts
            word_list = [w.strip() for w in words.split(',') if w.strip()]
            
            if lang not in self.profanity_list:
                return await ctx.send(f"❌ 找不到語言：{lang}")
            
            removed = []
            for word in word_list:
                if word in self.profanity_list[lang]:
                    self.profanity_list[lang].remove(word)
                    removed.append(word)
            
            self._save_profanity()
            await ctx.send(f"✅ 已從 {lang} 移除 {len(removed)} 個髒話：{', '.join(removed)}")
        
        elif action == "sync":
            # 同步預設髒話庫
            synced = 0
            for lang, words in self.default_profanity.items():
                if lang not in self.profanity_list:
                    self.profanity_list[lang] = []
                
                for word in words:
                    if word not in self.profanity_list[lang]:
                        self.profanity_list[lang].append(word)
                        synced += 1
            
            self._save_profanity()
            await ctx.send(f"✅ 已同步 {synced} 個預設髒話到詞庫！")
        
        elif action == "clear":
            # 清空自定義髒話（保留預設）
            self.profanity_list = self.default_profanity.copy()
            self._save_profanity()
            await ctx.send("✅ 已清空自定義髒話，恢復為預設髒話庫！")
        
        else:
            await ctx.send("❌ 未知的操作！請使用 `!脏话列表` 查看使用方式。")
    
    @commands.command(name='警告', aliases=['warn'])
    @commands.has_permissions(administrator=True)
    async def warn_user(self, ctx, member: discord.Member, *, reason=None):
        """警告使用者"""
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        
        if guild_id not in self.warnings:
            self.warnings[guild_id] = {}
        if user_id not in self.warnings[guild_id]:
            self.warnings[guild_id][user_id] = {
                "count": 0,
                "warnings": [],
                "last_warning": None
            }
        
        self.warnings[guild_id][user_id]["count"] += 1
        self.warnings[guild_id][user_id]["last_warning"] = datetime.now().isoformat()
        self.warnings[guild_id][user_id]["warnings"].append({
            "reason": reason or "手動警告",
            "time": datetime.now().isoformat(),
            "moderator": ctx.author.id
        })
        self._save_warnings()
        
        count = self.warnings[guild_id][user_id]["count"]
        await ctx.send(f"⚠️ 已警告 {member.mention}！\n原因：{reason or '無'}\n總警告次數：{count}")
    
    @commands.command(name='记过', aliases=['記過'])
    @commands.has_permissions(administrator=True)
    async def record_violation(self, ctx, member: discord.Member, level: str, points: int):
        """記錄違規（警告/小過/大過）"""
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        
        if level not in ['警告', '小過', '大過']:
            return await ctx.send("❌ 違規等級必須是：警告、小過、或 大過")
        
        if guild_id not in self.warnings:
            self.warnings[guild_id] = {}
        if user_id not in self.warnings[guild_id]:
            self.warnings[guild_id][user_id] = {
                "count": 0,
                "warnings": [],
                "last_warning": None
            }
        
        self.warnings[guild_id][user_id]["count"] += points
        self.warnings[guild_id][user_id]["last_warning"] = datetime.now().isoformat()
        self.warnings[guild_id][user_id]["warnings"].append({
            "type": level,
            "points": points,
            "time": datetime.now().isoformat(),
            "moderator": ctx.author.id
        })
        self._save_warnings()
        
        total = self.warnings[guild_id][user_id]["count"]
        await ctx.send(f"📝 已記錄 {member.mention} 的違規：\n等級：{level}\n點數：{points}\n總點數：{total}")
    
    @commands.command(name='踢出', aliases=['kick'])
    @commands.has_permissions(kick_members=True)
    async def kick_member(self, ctx, member: discord.Member, *, reason=None):
        """踢出成員"""
        try:
            await member.kick(reason=reason or f"被 {ctx.author} 踢出")
            await ctx.send(f"👢 已踢出 {member.mention}！\n原因：{reason or '無'}")
        except Exception as e:
            await ctx.send(f"❌ 踢出失敗：{e}")
    
    @commands.command(name='停权', aliases=['停權', 'ban'])
    @commands.has_permissions(ban_members=True)
    async def ban_member(self, ctx, member: discord.Member, *, reason=None):
        """停權（ban）成員"""
        try:
            await member.ban(reason=reason or f"被 {ctx.author} 停權")
            await ctx.send(f"🔨 已停權 {member.mention}！\n原因：{reason or '無'}")
        except Exception as e:
            await ctx.send(f"❌ 停權失敗：{e}")
    
    @commands.command(name='mute')
    @commands.has_permissions(moderate_members=True)
    async def mute_member(self, ctx, member: discord.Member, duration: int = 10, *, reason=None):
        """禁言成員（預設10分鐘）"""
        try:
            await member.timeout(timedelta(minutes=duration), reason=reason or f"被 {ctx.author} 禁言")
            await ctx.send(f"🔇 已禁言 {member.mention} {duration} 分鐘！\n原因：{reason or '無'}")
        except Exception as e:
            await ctx.send(f"❌ 禁言失敗：{e}")
    
    @commands.command(name='警告查詢', aliases=['warnings'])
    async def check_warnings(self, ctx, member: discord.Member = None):
        """查詢警告記錄"""
        member = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        
        if guild_id not in self.warnings or user_id not in self.warnings[guild_id]:
            return await ctx.send(f"✅ {member.mention} 沒有警告記錄！")
        
        data = self.warnings[guild_id][user_id]
        count = data["count"]
        warnings = data["warnings"][-10:]  # 只顯示最近10條
        
        embed = discord.Embed(
            title=f"⚠️ {member.display_name} 的警告記錄",
            description=f"總警告次數：{count}",
            color=0xe74c3c
        )
        
        for i, w in enumerate(warnings[-5:], 1):  # 只顯示最近5條
            if "type" in w:
                embed.add_field(
                    name=f"{i}. {w['type']} (+{w['points']}點)",
                    value=f"時間：{w['time'][:19]}\n執行人：<@{w['moderator']}>",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"{i}. 警告",
                    value=f"原因：{w.get('reason', '無')}\n時間：{w['time'][:19]}",
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='同步脏话库', aliases=['同步髒話庫', 'sync_profanity'])
    @commands.has_permissions(administrator=True)
    async def sync_profanity_db(self, ctx):
        """同步髒話庫（AI 輔助）"""
        await ctx.send("🔄 正在同步髒話庫，請稍候...")
        
        # 這裡可以整合 AI 來獲取最新的髒話庫
        # 目前先使用預設庫
        synced = 0
        for lang, words in self.default_profanity.items():
            if lang not in self.profanity_list:
                self.profanity_list[lang] = []
            
            for word in words:
                if word not in self.profanity_list[lang]:
                    self.profanity_list[lang].append(word)
                    synced += 1
        
        self._save_profanity()
        await ctx.send(f"✅ 髒話庫同步完成！\n新增 {synced} 個詞彙\n目前總共 {sum(len(v) for v in self.profanity_list.values())} 個髒話")

async def setup(bot):
    await bot.add_cog(ProfanityCog(bot))