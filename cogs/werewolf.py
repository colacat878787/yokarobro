import discord
from discord.ext import commands
import random
import os
import uuid
import asyncio
import urllib.request
from gtts import gTTS
import discord.ui
from yt_dlp import YoutubeDL

class CombatInviteView(discord.ui.View):
    def __init__(self, member, text_channel):
        super().__init__(timeout=60)
        self.member = member
        self.text_channel = text_channel

    @discord.ui.button(label="接受 ⚔️", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("您已接受了戰鬥邀請！", ephemeral=True)
        await self.text_channel.send(f"🟢 **{self.member.mention} 已接受戰鬥邀請，正前往戰場！**")
        self.stop()

    @discord.ui.button(label="拒絕 🛡️", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("您已拒絕了戰鬥邀請。", ephemeral=True)
        await self.text_channel.send(f"🔴 **{self.member.mention} 拒絕了戰鬥邀請！**")
        self.stop()

class VotingView(discord.ui.View):
    def __init__(self, cog, living_players, timeout):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.living_players = living_players
        self.votes = {}  # voter_member -> target_player_data or "棄票"
        self.voting_message = None
        self.tallied = False
        self._add_buttons()

    def _add_buttons(self):
        sorted_players = sorted(self.living_players, key=lambda x: x['number'])
        for p in sorted_players:
            button = discord.ui.Button(
                label=f"{p['number']}號",
                style=discord.ButtonStyle.secondary,
                custom_id=f"vote_{p['number']}"
            )
            button.callback = self.make_callback(p)
            self.add_item(button)
            
        skip_button = discord.ui.Button(
            label="棄票",
            style=discord.ButtonStyle.danger,
            custom_id="vote_skip"
        )
        skip_button.callback = self.make_skip_callback()
        self.add_item(skip_button)
        
        end_button = discord.ui.Button(
            label="⚖️ 提前結束投票",
            style=discord.ButtonStyle.primary,
            custom_id="vote_end"
        )
        end_button.callback = self.end_vote_callback
        self.add_item(end_button)

    def make_callback(self, target_player):
        async def callback(interaction: discord.Interaction):
            voter_id = interaction.user.id
            if voter_id not in self.cog.players:
                return await interaction.response.send_message("❌ 您非參賽玩家，無法參與投票！", ephemeral=True)
            if not self.cog.players[voter_id]['alive']:
                return await interaction.response.send_message("❌ 您已出局，無法參與投票！", ephemeral=True)
                
            self.votes[interaction.user] = target_player
            await interaction.response.send_message(f"✅ 您已投給 {target_player['number']} 號玩家！", ephemeral=True)
            
            if len(self.votes) == len(self.living_players):
                await self.tally_votes()
                self.stop()
        return callback

    def make_skip_callback(self):
        async def callback(interaction: discord.Interaction):
            voter_id = interaction.user.id
            if voter_id not in self.cog.players:
                return await interaction.response.send_message("❌ 您非參賽玩家，無法參與投票！", ephemeral=True)
            if not self.cog.players[voter_id]['alive']:
                return await interaction.response.send_message("❌ 您已出局，無法參與投票！", ephemeral=True)
                
            self.votes[interaction.user] = "棄票"
            await interaction.response.send_message("✅ 您已選擇棄票！", ephemeral=True)
            
            if len(self.votes) == len(self.living_players):
                await self.tally_votes()
                self.stop()
        return callback

    async def end_vote_callback(self, interaction: discord.Interaction):
        is_judge = interaction.user.guild.permissions.administrator or interaction.user.id == interaction.guild.owner_id
        if not is_judge:
            return await interaction.response.send_message("❌ 只有法官或管理員可以提前結束投票！", ephemeral=True)
            
        await interaction.response.send_message("⚖️ 法官已提前結束投票！", ephemeral=True)
        await self.tally_votes()
        self.stop()

    async def on_timeout(self):
        await self.tally_votes()

    async def tally_votes(self):
        if self.tallied:
            return
        self.tallied = True
        
        if not self.voting_message:
            return
            
        for item in self.children:
            item.disabled = True
        try:
            await self.voting_message.edit(view=self)
        except Exception as e:
            print(f"無法禁用投票按鈕: {e}")
            
        tally = {}
        for voter, target in self.votes.items():
            if target == "棄票":
                tally["棄票"] = tally.get("棄票", []) + [voter]
            else:
                num = target['number']
                tally[num] = tally.get(num, []) + [voter]
                
        result_desc = []
        for target, voters in tally.items():
            voter_mentions = ", ".join([v.mention for v in voters])
            if target == "棄票":
                result_desc.append(f"• **棄票**：{len(voters)} 票 ({voter_mentions})")
            else:
                result_desc.append(f"• **{target}號**：{len(voters)} 票 ({voter_mentions})")
                
        exiled_msg = ""
        highest_vote_count = 0
        highest_targets = []
        
        for target, voters in tally.items():
            if target == "棄票":
                continue
            count = len(voters)
            if count > highest_vote_count:
                highest_vote_count = count
                highest_targets = [target]
            elif count == highest_vote_count:
                highest_targets.append(target)
                
        if highest_vote_count == 0:
            exiled_msg = "⚖️ **最終決定**：本次無人投票或全員棄票，無人被放逐！"
        elif len(highest_targets) > 1:
            targets_str = "、".join([f"{t}號" for t in highest_targets])
            exiled_msg = f"⚖️ **最終決定**：{targets_str} 平票 (均為 {highest_vote_count} 票)，無人被放逐！"
        else:
            exiled_player_num = highest_targets[0]
            exiled_msg = f"⚖️ **最終決定**：**{exiled_player_num}號** 獲得最高票 ({highest_vote_count} 票)，被投票放逐！"
            
            for p_id, p_data in self.cog.players.items():
                if p_data['number'] == exiled_player_num:
                    p_data['alive'] = False
                    name = p_data['original_nick'] or p_data['member'].name
                    await self.cog.set_member_nick(p_data['member'], f"💀 {exiled_player_num}號 {name}")
                    try:
                        await self.cog.voice_channel.set_permissions(p_data['member'], send_messages=False)
                    except:
                        pass
                    await self.cog.set_member_mute(p_data['member'], True)
                    break
                    
        embed = discord.Embed(
            title="🗳️ 狼人殺投票結果公佈",
            description="\n".join(result_desc) if result_desc else "無人投票。",
            color=0x2ecc71
        )
        embed.add_field(name="決議", value=exiled_msg, inline=False)
        embed.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手")
        
        await self.voting_message.channel.send(embed=embed)
        
        if highest_vote_count > 0 and len(highest_targets) == 1:
            self.cog.queue_kill_sound(self.voting_message.guild)


class WerewolfJoinView(discord.ui.View):
    def __init__(self, cog, member, text_channel):
        super().__init__(timeout=None)
        self.cog = cog
        self.member = member
        self.text_channel = text_channel

    @discord.ui.button(label="報名參加", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            return await interaction.response.send_message("❌ 只有被邀請的玩家可以按此按鈕。", ephemeral=True)

        # Ensure the cog is tracking this pending player
        if interaction.user.id not in self.cog.pending_players:
            self.cog.pending_players[interaction.user.id] = self.member

        await interaction.response.send_message("✅ 已報名！請在此私訊中回覆您的報號數字（純數字）。", ephemeral=True)
        try:
            if self.text_channel:
                await self.text_channel.send(f"🟢 **{interaction.user.mention} 已點擊報名按鈕，請在私訊中回覆報號。**")
        except Exception:
            pass

    @discord.ui.button(label="取消", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.member.id:
            return await interaction.response.send_message("❌ 只有被邀請的玩家可以按此按鈕。", ephemeral=True)
        if interaction.user.id in self.cog.pending_players:
            del self.cog.pending_players[interaction.user.id]
        await interaction.response.send_message("已取消報名。", ephemeral=True)

class ConfirmButtonView(discord.ui.View):
    def __init__(self, timeout=10.0):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="確認", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()

    @discord.ui.button(label="取消", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()

class WerewolfCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game_active = False
        self.guild_id = None
        self.voice_channel = None
        self.text_channel = None
        self.players = {}  # user_id -> data dict
        self.speaking_player = None
        self.day = 1
        self.phase = "白天發言"
        self.roles_setup = ""
        self.tts_queues = {}  # guild_id -> list of file paths
        self.FFMPEG_OPTIONS = {'options': '-vn'}
        self.pending_players = {} # member_id -> member object for auto mode registration
        self.reported_numbers = {} # member_id -> number for auto mode registration
        self.auto_game_active = False # Flag for auto game mode
        self.auto_game_task = None # asyncio task for auto game loop
        self.bgm_volume = 0.3  # default BGM volume (30%)
        self.speech_timer_task = None  # task for per-speaker timer

    def get_default_roles(self, count):
        if count <= 3:
            return ["狼人", "預言家", "平民"][:count]
        elif count == 4:
            return ["狼人", "預言家", "女巫", "平民"]
        elif count == 5:
            return ["狼人", "預言家", "女巫", "平民", "平民"]
        elif count == 6:
            return ["狼人", "狼人", "預言家", "女巫", "平民", "平民"]
        elif count == 7:
            return ["狼人", "狼人", "預言家", "女巫", "平民", "平民", "平民"]
        elif count == 8:
            return ["狼人", "狼人", "預言家", "女巫", "獵人", "平民", "平民", "平民"]
        elif count == 9:
            return ["狼人", "狼人", "狼人", "預言家", "女巫", "獵人", "平民", "平民", "平民"]
        elif count == 10:
            return ["狼人", "狼王", "機械狼", "通靈師", "女巫", "獵人", "守衛", "平民", "平民", "平民"]
        else:
            wolves = ["狼人", "狼人", "狼王"]
            powers = ["預言家", "女巫", "獵人", "守衛"]
            villagers = ["平民"] * (count - len(wolves) - len(powers))
            return wolves + powers + villagers

    def create_setup_embed(self):
        embed = discord.Embed(
            title="🐺 狼人殺 遊戲準備中",
            description=f"已自動偵測並登記語音頻道內的所有玩家。\n**語音房**: 🔊 {self.voice_channel.name if self.voice_channel else '無'}",
            color=0x3498db
        )
        
        players_list = []
        sorted_players = sorted(self.players.items(), key=lambda x: x[1]['number'])
        for p_id, p_data in sorted_players:
            players_list.append(f"{p_data['number']}號：{p_data['member'].mention}")
            
        embed.add_field(
            name="已登記玩家",
            value="\n".join(players_list) if players_list else "無玩家",
            inline=True
        )
        
        embed.add_field(
            name="配置角色",
            value=self.roles_setup,
            inline=True
        )
        
        embed.add_field(
            name="指令提示",
            value="💡 輸入 `!lssha start` 開始分配身份並鎖定發言權限！\n"
                  "💡 輸入 `!lssha setup [自訂角色]` 可重新配置遊戲！",
            inline=False
        )
        embed.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手", icon_url=self.bot.user.display_avatar.url)
        return embed

    def create_status_embed(self):
        color = 0xe74c3c if "黑夜" in self.phase or "天黑" in self.phase or self.phase == "Night" else 0xf1c40f
        
        embed = discord.Embed(
            title="🐺 狼人殺進行中",
            description=f"**局型**: {self.roles_setup}\n"
                        f"**天數**: 第 {self.day} 天\n"
                        f"**階段**: {self.phase}\n"
                        f"**語音房**: 🔊 {self.voice_channel.name if self.voice_channel else '無'}",
            color=color
        )
        
        players_list = []
        sorted_players = sorted(self.players.items(), key=lambda x: x[1]['number'])
        
        for p_id, p_data in sorted_players:
            member = p_data['member']
            status = "🟢 存活" if p_data['alive'] else "💀 已出局"
            speaking_mark = " 📢 **(正在發言)**" if self.speaking_player == p_data['number'] else ""
            players_list.append(
                f"{p_data['number']}. {member.mention} - {status}{speaking_mark}"
            )
            
        embed.add_field(
            name="玩家狀態",
            value="\n".join(players_list) if players_list else "尚無玩家",
            inline=False
        )
        
        embed.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手", icon_url=self.bot.user.display_avatar.url)
        return embed

    async def set_member_nick(self, member, nick):
        try:
            await member.edit(nick=nick)
        except discord.Forbidden:
            print(f"無法修改 {member.name} 的暱稱 (權限不足)")
        except Exception as e:
            print(f"修改暱稱錯誤: {e}")

    async def set_member_mute(self, member, mute_state):
        try:
            if member.voice and member.voice.channel:
                await member.edit(mute=mute_state)
        except discord.Forbidden:
            print(f"無法設定 {member.name} 的靜音狀態 (權限不足)")
        except Exception as e:
            print(f"設定靜音狀態錯誤: {e}")

    async def ensure_kill_sound(self):
        url = "https://www.soundjay.com/mechanical/gunshot-01.mp3"
        filepath = os.path.join(os.getcwd(), "kill_sound.mp3")
        if not os.path.exists(filepath):
            try:
                await self.bot.loop.run_in_executor(None, urllib.request.urlretrieve, url, filepath)
                print("🔊 殺手音效下載成功！")
            except Exception as e:
                print(f"下載殺手音效失敗: {e}")

    def queue_kill_sound(self, guild):
        filepath = os.path.join(os.getcwd(), "kill_sound.mp3")
        if os.path.exists(filepath):
            guild_id = guild.id
            if guild_id not in self.tts_queues:
                self.tts_queues[guild_id] = []
            self.tts_queues[guild_id].append(filepath)
            self.play_next_tts(guild)
        else:
            self.queue_tts("槍聲響起！啊！玩家出局。", guild)

    def queue_tts(self, text, guild):
        guild_id = guild.id
        if guild_id not in self.tts_queues:
            self.tts_queues[guild_id] = []
            
        tts_filename = f"ww_tts_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(os.getcwd(), tts_filename)
        
        try:
            tts = gTTS(text=text, lang='zh-tw')
            tts.save(filepath)
            self.tts_queues[guild_id].append(filepath)
            self.play_next_tts(guild)
        except Exception as e:
            print(f"WW TTS 錯誤: {e}")
            if os.path.exists(filepath):
                try: os.remove(filepath)
                except: pass

    def play_next_tts(self, guild):
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            return
        if vc.is_playing() or not self.tts_queues.get(guild.id):
            return
            
        filepath = self.tts_queues[guild.id].pop(0)
        
        def after_playing(error):
            if os.path.exists(filepath) and filepath != os.path.join(os.getcwd(), "kill_sound.mp3"):
                try: os.remove(filepath)
                except: pass
            if guild.id in self.tts_queues and self.tts_queues[guild.id]:
                self.bot.loop.call_soon_threadsafe(self.play_next_tts, guild)
                
        try:
            audio_source = discord.FFmpegPCMAudio(filepath, **self.FFMPEG_OPTIONS)
            vc.play(audio_source, after=after_playing)
        except Exception as e:
            print(f"WW TTS 播放錯誤: {e}")
            if os.path.exists(filepath) and filepath != os.path.join(os.getcwd(), "kill_sound.mp3"):
                try: os.remove(filepath)
                except: pass
            self.bot.loop.call_soon_threadsafe(self.play_next_tts, guild)

    @commands.has_permissions(administrator=True)
    @commands.group(name="lssha", aliases=["狼人殺", "werewolf"], invoke_without_command=True)
    async def lssha_cmd(self, ctx):
        """狼人殺遊戲管理系統"""
        if ctx.invoked_subcommand is None:
            await ctx.send("📢 **優卡洛法官已被喚醒！本頻道已設定為本局【狼人殺專屬文字頻道】。**")
            await self.setup_cmd(ctx, roles_str=None) # Call setup command as default behavior
            embed = discord.Embed(
                title="🐺 👑 優卡洛 ⚖️ 庫拉吉法官助手",
                description="本助手協助管理 Discord 語音狼人殺遊戲，自動管理暱稱、語音房禁言、權限，並支援文字發言 TTS 自動朗讀！",
                color=0x9b59b6
            )
            embed.add_field(
                name="🎮 遊戲準備指令",
                value="🔹 `!lssha` - 在專屬文字頻道初始化遊戲並登記語音房玩家。\n"
                      "🔹 `!lssha setup [角色配置]` - 初始化遊戲，登記您當用語音房內的所有人。\n"
                      "🔹 `!lssha start` - 發放身份牌（私訊），更新玩家暱稱及頻道禁言權限，**並將所有人預先靜音**。\n"
                      "🔹 `!lssha status` - 顯示當前玩家名單及存活狀況。",
                inline=False
            )
            embed.add_field(
                name="⚖️ 法官控制指令",
                value="🔹 `!lssha kill [編號]` - 判定該號碼玩家出局（播放槍殺音效、骷髏頭 + 永久靜音）。\n"
                      "🔹 `!lssha revive [編號]` - 判定該號碼玩家復活（還原 + 取消靜音）。\n"
                      "🔹 `!lssha speak [編號]` - 點名該號碼玩家發言（解除該玩家靜音，並鎖定其他所有人靜音）。\n"
                      "🔹 `!lssha vote [秒數]` - 發起高互動式投票，附帶號碼選擇按鈕（可提前結束）。\n"
                      "🔹 `!lssha phase [day/night]` - 切換白天/黑夜（黑夜時所有人強制靜音）。\n"
                      "🔹 `!lssha end` - 結束遊戲，還原所有人暱稱並重設頻道與麥克風狀態。\n"
                      "🔹 `!go` - (管理員專用) 手動向當前語音房內的所有人發出戰鬥邀請私訊。",
                inline=False
            )
            embed.add_field(
                name="🎤 玩家指令",
                value="🔹 `!pass` (或 `!過`、`!lssha pass`) - 正在發言的玩家結束發言，自動交給下一位存活者。",
                inline=False
            )
            embed.set_footer(text="優卡洛 | Werewolf Judge Assistant")
            await ctx.send(embed=embed)

    @lssha_cmd.command(name='setup')
    async def setup_cmd(self, ctx, *, roles_str: str = None):
        """登記語音房所有玩家並配置角色"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ 嗷～你必須先加入語音頻道，我才能幫你初始化遊戲喔！")
        
        self.voice_channel = ctx.author.voice.channel
        self.text_channel = ctx.channel
        self.game_active = False
        
        # 確保殺手音效已下載
        self.bot.loop.create_task(self.ensure_kill_sound())
        
        # 取得語音房內非機器人的成員
        members = [m for m in self.voice_channel.members if not m.bot]
        if not members:
            return await ctx.send("❌ 語音頻道中沒有其他人類玩家喔！")
            
        try:
            if ctx.voice_client:
                if ctx.voice_client.channel != self.voice_channel:
                    await ctx.voice_client.move_to(self.voice_channel)
            else:
                await self.voice_channel.connect(timeout=60.0, reconnect=True)
        except Exception as e:
            await ctx.send(f"⚠️ 連接語音房失敗: {e}")
            
        count = len(members)
        roles = []
        if roles_str:
            import re
            matches = re.findall(r'(\d+)\s*([\u4e00-\u9fa5a-zA-Z0-9]+)', roles_str)
            if matches:
                for cnt, r_name in matches:
                    roles.extend([r_name] * int(cnt))
            else:
                roles = [r.strip() for r in re.split(r'[\s,，]+', roles_str) if r.strip()]
        
        if len(roles) != count:
            roles = self.get_default_roles(count)
            
        random.shuffle(roles)
        
        role_counts = {}
        for r in roles:
            role_counts[r] = role_counts.get(r, 0) + 1
        
        self.roles_setup = f"{count}人自訂局 (" + "、".join([f"{v}{k}" for k, v in role_counts.items()]) + ")"
        
        self.players = {}
        for i, member in enumerate(members):
            self.players[member.id] = {
                'number': i + 1,
                'member': member,
                'role': roles[i],
                'alive': True,
                'original_nick': member.nick
            }
            
        embed = self.create_setup_embed()
        await ctx.send(embed=embed)

    @lssha_cmd.command(name='start')
    async def start_cmd(self, ctx):
        """正式開始遊戲，發放身份、設定暱稱與權限，且全體伺服器靜音"""
        if not self.players:
            return await ctx.send("❌ 尚未初始化遊戲，請先使用 `!lssha setup`！")
        if self.game_active:
            return await ctx.send("❌ 遊戲已經在進行中囉！")
            
        self.game_active = True
        self.day = 1
        self.phase = "白天發言"
        self.speaking_player = None
        
        await ctx.send("🚀 **遊戲開始！正在發送身份牌，設定發言權限，並將所有人麥克風進行伺服器端靜音...**")
        
        dm_warnings = []
        for p_id, p_data in self.players.items():
            member = p_data['member']
            role = p_data['role']
            number = p_data['number']
            
            # 更新暱稱
            name = p_data['original_nick'] or member.name
            await self.set_member_nick(member, f"⭐{number}號 {name}")
            
            # 預設全體伺服器靜音
            await self.set_member_mute(member, True)
            
            # 發送私訊
            try:
                embed_dm = discord.Embed(
                    title="🐺 狼人殺身份發放",
                    description=f"您在 **{ctx.guild.name}** 的狼人殺遊戲已開始！\n"
                                f"您的編號是：**{number} 號**\n"
                                f"您的角色是：🔑 **{role}**\n\n"
                                f"💡 請遵守法官與語音頻道指示，祝您遊戲愉快！",
                    color=0x9b59b6
                )
                embed_dm.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手")
                await member.send(embed=embed_dm)
            except discord.Forbidden:
                dm_warnings.append(member.mention)
                
        if dm_warnings:
            await ctx.send(f"⚠️ 以下玩家因未開啟私訊，無法發送身份牌，請法官手動告知：\n" + "、".join(dm_warnings))
            
        # 設定發言權限
        try:
            await self.voice_channel.set_permissions(ctx.guild.default_role, send_messages=False)
            for p_id, p_data in self.players.items():
                await self.voice_channel.set_permissions(p_data['member'], send_messages=True)
        except Exception as e:
            await ctx.send(f"⚠️ 設定語音房發言權限失敗：{e} (請確認機器人擁有管理頻道的權限)")
            
        embed = self.create_status_embed()
        await ctx.send(embed=embed)
        self.queue_tts("狼人殺遊戲開始。天黑請閉眼。", ctx.guild)

    @lssha_cmd.command(name='status')
    async def status_cmd(self, ctx):
        """顯示當前存活狀況"""
        if not self.game_active:
            return await ctx.send("❌ 目前沒有進行中的遊戲！")
        embed = self.create_status_embed()
        await ctx.send(embed=embed)

    @lssha_cmd.command(name='kill')
    async def kill_cmd(self, ctx, number: int):
        """擊殺/出局指定玩家"""
        if not self.game_active:
            return await ctx.send("❌ 目前沒有進行中的遊戲！")
            
        player = None
        for p_id, p_data in self.players.items():
            if p_data['number'] == number:
                player = p_data
                break
                
        if not player:
            return await ctx.send(f"❌ 找不到 {number} 號玩家！")
        if not player['alive']:
            return await ctx.send(f"❌ {number} 號玩家已經出局了！")
            
        player['alive'] = False
        member = player['member']
        
        # 改為骷髏暱稱
        name = player['original_nick'] or member.name
        await self.set_member_nick(member, f"💀⭐{number}號 {name}")
        
        # 移除發言權限，並強制伺服器靜音
        try:
            await self.voice_channel.set_permissions(member, send_messages=False)
        except Exception as e:
            print(f"無法移除出局玩家的打字權限: {e}")
        await self.set_member_mute(member, True)
            
        if self.speaking_player == number:
            self.speaking_player = None
            
        await ctx.send(f"💀 **{number}號 {member.mention} 已被法官判定出局！**")
        self.queue_kill_sound(ctx.guild)
        
        embed = self.create_status_embed()
        await ctx.send(embed=embed)

    @lssha_cmd.command(name='revive')
    async def revive_cmd(self, ctx, number: int):
        """復活指定玩家"""
        if not self.game_active:
            return await ctx.send("❌ 目前沒有進行中的遊戲！")
            
        player = None
        for p_id, p_data in self.players.items():
            if p_data['number'] == number:
                player = p_data
                break
                
        if not player:
            return await ctx.send(f"❌ 找不到 {number} 號玩家！")
        if player['alive']:
            return await ctx.send(f"❌ {number} 號玩家本來就是存活狀態！")
            
        player['alive'] = True
        member = player['member']
        
        # 還原暱稱
        name = player['original_nick'] or member.name
        await self.set_member_nick(member, f"⭐{number}號 {name}")
        
        # 恢復發言權限與麥克風狀態（若非當前發言人則保持靜音）
        try:
            await self.voice_channel.set_permissions(member, send_messages=True)
        except Exception as e:
            print(f"無法恢復復活玩家的打字權限: {e}")
            
        should_mute = True
        if self.speaking_player == number:
            should_mute = False
        await self.set_member_mute(member, should_mute)
            
        await ctx.send(f"🟢 **{number}號 {member.mention} 已被法官判定復活！**")
        self.queue_tts(f"{number}號玩家已復活。", ctx.guild)
        
        embed = self.create_status_embed()
        await ctx.send(embed=embed)

    @lssha_cmd.command(name='speak')
    async def speak_cmd(self, ctx, number: int):
        """指派發言（僅解除該玩家靜音，其他玩家全部靜音）"""
        if not self.game_active:
            return await ctx.send("❌ 目前沒有進行中的遊戲！")
            
        player = None
        for p_id, p_data in self.players.items():
            if p_data['number'] == number:
                player = p_data
                break
                
        if not player:
            return await ctx.send(f"❌ 找不到 {number} 號玩家！")
        if not player['alive']:
            return await ctx.send(f"❌ {number} 號玩家已出局，無法發言！")
            
        # 靜音前一個說話的人
        if self.speaking_player:
            for p_id, p_data in self.players.items():
                if p_data['number'] == self.speaking_player:
                    await self.set_member_mute(p_data['member'], True)
                    break
                    
        self.speaking_player = number
        member = player['member']
        
        # 解除該發言人的靜音
        await self.set_member_mute(member, False)
        
        await ctx.send(f"📢 **法官：輪到 {number} 號 {member.mention} 發言。**")
        self.queue_tts(f"請{number}號玩家開始發言。", ctx.guild)
        # Start a visible 90s countdown for this speaker (manual mode)
        try:
            if self.speech_timer_task and not self.speech_timer_task.done():
                self.speech_timer_task.cancel()
        except Exception:
            pass

        self.speech_timer_task = self.bot.loop.create_task(self._speech_countdown(ctx, member, 90))
        
        embed = self.create_status_embed()
        await ctx.send(embed=embed)

    @lssha_cmd.command(name='pass')
    async def ww_pass_cmd(self, ctx):
        """結束自己發言，切換到下一位"""
        await self.pass_cmd(ctx)

    @commands.command(name='pass', aliases=['過', 'ww_pass'])
    async def pass_cmd(self, ctx):
        """結束當前玩家發言，自動將發言權與麥克風移交給下一位存活者"""
        if not self.game_active:
            return
            
        is_judge = ctx.author.guild.permissions.administrator or ctx.author.id == ctx.guild.owner_id
        author_player = self.players.get(ctx.author.id)
        
        if not is_judge:
            if not author_player:
                return
            if self.speaking_player != author_player['number']:
                return
                
        # 靜音當前發言玩家
        if self.speaking_player:
            for p_id, p_data in self.players.items():
                if p_data['number'] == self.speaking_player:
                    await self.set_member_mute(p_data['member'], True)
                    break

        # Cancel any running speech timer task
        try:
            if self.speech_timer_task and not self.speech_timer_task.done():
                self.speech_timer_task.cancel()
        except Exception:
            pass
                    
        sorted_players = sorted(self.players.items(), key=lambda x: x[1]['number'])
        p_count = len(sorted_players)
        
        current_num = self.speaking_player or 0
        next_speaker = None
        
        for i in range(1, p_count + 1):
            target_num = ((current_num + i - 1) % p_count) + 1
            for p_id, p_data in sorted_players:
                if p_data['number'] == target_num and p_data['alive']:
                    next_speaker = p_data
                    break
            if next_speaker:
                break
                
        if next_speaker and next_speaker['number'] != current_num:
            self.speaking_player = next_speaker['number']
            # 解除下一位發言人的靜音
            await self.set_member_mute(next_speaker['member'], False)
            await ctx.send(f"📢 **法官：{current_num} 號發言結束。輪到 {next_speaker['number']} 號 {next_speaker['member'].mention} 發言。**")
            self.queue_tts(f"{current_num}號發言結束。請{next_speaker['number']}號玩家開始發言。", ctx.guild)
        else:
            self.speaking_player = None
            await ctx.send(f"📢 **法官：所有玩家發言結束！**")
            self.queue_tts("所有玩家發言結束。", ctx.guild)
            
        embed = self.create_status_embed()
        await ctx.send(embed=embed)

    async def _speech_countdown(self, ctx, member, seconds: int):
        """Send and update a countdown message for a speaker. Cancel by cancelling the returned task."""
        try:
            msg = await ctx.send(f"⏱️ {member.mention} 發言剩餘：{seconds} 秒")
        except Exception:
            msg = None

        try:
            for remaining in range(seconds, 0, -1):
                if msg:
                    try:
                        await msg.edit(content=f"⏱️ {member.mention} 發言剩餘：{remaining} 秒")
                    except Exception:
                        pass
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Caller will handle announcement
            raise
        finally:
            if msg:
                try:
                    await msg.delete()
                except Exception:
                    pass

    @lssha_cmd.command(name='phase')
    async def phase_cmd(self, ctx, target_phase: str):
        """切換白天/黑夜（黑夜時所有人強制靜音）"""
        if not self.game_active:
            return await ctx.send("❌ 目前沒有進行中的遊戲！")
            
        target_phase = target_phase.lower()
        if target_phase in ['day', '白天', '日']:
            self.phase = "白天發言"
            self.day += 1
            self.speaking_player = None
            
            # 白天時全體先保持靜音，等待點名
            for p_id, p_data in self.players.items():
                await self.set_member_mute(p_data['member'], True)
                
            await ctx.send(f"🌞 **天亮了！進入第 {self.day} 天白天發言階段。**")
            self.queue_tts(f"天亮請睜眼。進入第{self.day}天白天發言。", ctx.guild)
        elif target_phase in ['night', '黑夜', '天黑', '夜']:
            self.phase = "黑夜閉眼"
            self.speaking_player = None
            
            # 黑夜時全體伺服器靜音
            for p_id, p_data in self.players.items():
                await self.set_member_mute(p_data['member'], True)
                
            await ctx.send(f"🌙 **天黑請閉眼！進入第 {self.day} 天黑夜階段。**")
            self.queue_tts("天黑請閉眼。狼人請睜眼。", ctx.guild)
        else:
            return await ctx.send("❌ 無效的階段名稱！請輸入 `day` 或 `night`！")
            
        embed = self.create_status_embed()
        await ctx.send(embed=embed)

    @lssha_cmd.command(name='vote')
    async def vote_cmd(self, ctx, timeout: int = 30):
        """發起投票放逐"""
        if not self.game_active:
            return await ctx.send("❌ 目前沒有進行中的遊戲！")
            
        living_players = [p for p in self.players.values() if p['alive']]
        if not living_players:
            return await ctx.send("❌ 沒有存活的玩家可以進行投票！")
            
        embed = discord.Embed(
            title="🗳️ 狼人殺投票",
            description=f"請選擇要放逐的玩家。\n投票截止：**{timeout}** 秒內",
            color=0xf39c12
        )
        
        players_list = []
        sorted_players = sorted(living_players, key=lambda x: x['number'])
        for p in sorted_players:
            players_list.append(f"{p['number']}. {p['member'].mention}")
            
        embed.add_field(
            name="存活玩家",
            value="\n".join(players_list),
            inline=False
        )
        embed.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手")
        
        view = VotingView(self, living_players, timeout)
        msg = await ctx.send(embed=embed, view=view)
        view.voting_message = msg

    @lssha_cmd.command(name='end')
    async def end_cmd(self, ctx):
        """結束遊戲並還原所有麥克風狀態、權限與暱稱，並自動向語音房成員發出戰鬥邀請"""
        if not self.game_active and not self.players:
            return await ctx.send("❌ 目前沒有進行中或準備中的遊戲！")
            
        await ctx.send("🛑 **正在結束遊戲，還原全體玩家靜音狀態、暱稱並重設頻道權限...**")
        
        voice_channel_backup = self.voice_channel
        
        # 還原暱稱與麥克風靜音狀態
        for p_id, p_data in self.players.items():
            member = p_data['member']
            orig_nick = p_data['original_nick']
            await self.set_member_nick(member, orig_nick)
            await self.set_member_mute(member, False)
            
        # 還原頻道覆寫權限
        if self.voice_channel:
            try:
                await self.voice_channel.set_permissions(ctx.guild.default_role, overwrite=None)
                for p_id, p_data in self.players.items():
                    await self.voice_channel.set_permissions(p_data['member'], overwrite=None)
            except Exception as e:
                await ctx.send(f"⚠️ 還原頻道權限失敗：{e}")
                
        text_channel_backup = self.text_channel or ctx.channel
        
        self.game_active = False
        self.players = {}
        self.speaking_player = None
        self.day = 1
        self.phase = "白天發言"
        self.voice_channel = None
        self.text_channel = None
        
        await ctx.send("✅ **遊戲已結束，法官下班！**")
        
        if voice_channel_backup:
            members = [m for m in voice_channel_backup.members if not m.bot]
            if members:
                await text_channel_backup.send("⚔️ **偵測到狼人殺局已結束！正在自動向語音房內的所有人發送新戰鬥邀請...**")
                for member in members:
                    try:
                        embed_invite = discord.Embed(
                            title="⚔️ 戰鬥召集令 ⚔️",
                            description=f"狼人殺已結束！**{ctx.author.display_name}** 已在語音房 **🔊 {voice_channel_backup.name}** 發起新對決！\n"
                                        f"請點選下方按鈕回覆您的參戰意願！",
                            color=0xc0392b
                        )
                        embed_invite.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手")
                        view = CombatInviteView(member, text_channel_backup)
                        await member.send(embed=embed_invite, view=view)
                    except discord.Forbidden:
                        await text_channel_backup.send(f"⚠️ 無法私訊 {member.mention} 戰鬥邀請 (未開啟私訊)。")

    @commands.command(name='go')
    @commands.has_permissions(administrator=True)
    async def go_cmd(self, ctx):
        """管理員手動向當前語音房內的所有玩家發出戰鬥邀請"""
        voice_channel = self.voice_channel
        if not voice_channel:
            if ctx.author.voice and ctx.author.voice.channel:
                voice_channel = ctx.author.voice.channel
            else:
                return await ctx.send("❌ 目前無正在進行的遊戲，且您不在任何語音頻道中！")
                
        members = [m for m in voice_channel.members if not m.bot]
        if not members:
            return await ctx.send("❌ 該語音頻道中沒有其他人類玩家！")
            
        target_channel = self.text_channel or ctx.channel
        await ctx.send(f"⚔️ **已向語音頻道 `{voice_channel.name}` 內的所有玩家發送戰鬥邀請！**")
        
        for member in members:
            try:
                embed_invite = discord.Embed(
                    title="⚔️ 戰鬥召集令 ⚔️",
                    description=f"管理員 **{ctx.author.display_name}** 已在語音房 **🔊 {voice_channel.name}** 發起戰鬥邀請！\n"
                                f"請點選下方按鈕回覆您的參戰意願！",
                    color=0xc0392b
                )
                embed_invite.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手")
                view = CombatInviteView(member, target_channel)
                await member.send(embed=embed_invite, view=view)
            except discord.Forbidden:
                await target_channel.send(f"⚠️ 無法私訊 {member.mention} 戰鬥邀請 (未開啟私訊)。")

    @lssha_cmd.command(name='bgm')
    async def bgm_cmd(self, ctx, *, query: str = None):
        """播放狼人殺 BGM（管理員指令）。若未提供歌名，會自動播預設清單之一。"""
        # Ensure bot is in voice
        voice_channel = self.voice_channel or (ctx.author.voice.channel if ctx.author.voice else None)
        if not voice_channel:
            return await ctx.send("❌ 需要先在語音頻道中或機器人已連線語音頻道才能播放 BGM！")

        vc = ctx.guild.voice_client
        try:
            if not vc or not vc.is_connected():
                vc = await voice_channel.connect(timeout=60.0, reconnect=True)
            elif vc.channel != voice_channel:
                await vc.move_to(voice_channel)
        except Exception as e:
            return await ctx.send(f"⚠️ 無法連接語音頻道以播放 BGM：{e}")

        default_urls = [
            "ytsearch:暗い／ピアノ 水の上で歌うⅠ フリー素材BGM",
            "ytsearch:周杰倫",
            "ytsearch:流行歌曲熱門"
        ]

        target = query if query else random.choice(default_urls)

        ytdl_opts = { 'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True }
        info = None
        try:
            with YoutubeDL(ytdl_opts) as ydl:
                info = ydl.extract_info(target, download=False)
        except Exception as e:
            return await ctx.send(f"❌ 無法搜尋或擷取音訊：{e}")

        if not info:
            return await ctx.send("❌ 找不到符合的音樂。")

        # If search result, take first entry
        if 'entries' in info:
            info = info['entries'][0]

        stream_url = info.get('url') or (info.get('formats')[0]['url'] if info.get('formats') else None)
        title = info.get('title', '自動選歌')

        if not stream_url:
            return await ctx.send("❌ 無法取得可播放的串流位址。")

        try:
            audio_source = discord.FFmpegPCMAudio(stream_url, **self.FFMPEG_OPTIONS)
            player = discord.PCMVolumeTransformer(audio_source, volume=self.bgm_volume)
            if vc.is_playing():
                vc.stop()
            vc.play(player)
            await ctx.send(f"🎵 現在播放 BGM：**{title}**（音量固定為 30% 若無另外設定）")
        except Exception as e:
            return await ctx.send(f"❌ 播放 BGM 發生錯誤：{e}")

    @lssha_cmd.command(name='bgmvol')
    async def bgmvol_cmd(self, ctx, percent: int):
        """設定狼人殺 BGM 音量（管理員）。輸入 0-100 的整數。"""
        if percent < 0 or percent > 100:
            return await ctx.send("❌ 介於 0 到 100 之間的數值！")
        self.bgm_volume = max(0.0, min(1.0, percent / 100.0))
        await ctx.send(f"🔊 已將狼人殺 BGM 音量設定為 {percent}%（實際播放音量為 {self.bgm_volume}）")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots and system messages
        if message.author.bot or message.is_system():
            return

        # --- Handle DM for number reporting in auto game mode ---
        if message.guild is None and self.auto_game_active and message.author.id in self.pending_players:
            try:
                reported_num = int(message.content.strip())
                if reported_num <= 0:
                    return await message.author.send("❌ 報號數字必須是正整數！請重新輸入。")

                # Check if number is already taken
                if reported_num in self.reported_numbers.values():
                    return await message.author.send(f"❌ 數字 {reported_num} 已經被其他玩家報號了！請選擇其他數字。")

                # Check if player already reported a number
                if message.author.id in self.reported_numbers:
                    return await message.author.send(f"❌ 您已報號數字 {self.reported_numbers[message.author.id]}。如需更改，請等待法官指示。")

                self.reported_numbers[message.author.id] = reported_num
                # Remove from pending, as they've reported their number
                if message.author.id in self.pending_players:
                    del self.pending_players[message.author.id]

                await message.author.send(f"✅ 您已成功報號：**{reported_num}**。法官正在等待所有玩家報號完畢，請耐心等候遊戲開始。")
                
                # Use stored text_channel to send public update
                if self.text_channel:
                    await self.text_channel.send(f"🟢 **{message.author.mention} 已報號 {reported_num}。**")
                
                # Use the stored guild_id to get guild for TTS
                guild_obj = self.bot.get_guild(self.guild_id)
                if guild_obj:
                    self.queue_tts(f"{message.author.display_name}已報號{reported_num}。", guild_obj)

                # Check if all pending players have reported their numbers
                if not self.pending_players and self.auto_game_active:
                    if self.text_channel:
                        await self.text_channel.send("✅ **所有玩家已成功報號！自動狼人殺遊戲即將開始。**")
                    if guild_obj:
                        self.queue_tts("所有玩家已成功報號。自動狼人殺遊戲即將開始。", guild_obj)
                    
                    # Trigger the next phase of the auto game
                    self.auto_game_task = self.bot.loop.create_task(self._start_auto_game_flow())

                return # Don't process DM as a game channel message

            except ValueError:
                await message.author.send("❌ 無效的數字。請輸入一個有效的整數數字來報號。")
                return # Don't process DM as a game channel message
        # --- End DM handling ---

        if not self.game_active:
            return
        if not message.guild: # This check is redundant after DM handling, but good for safety
            return
            
        is_game_channel = False
        if self.text_channel and message.channel.id == self.text_channel.id:
            is_game_channel = True
        elif self.voice_channel and message.channel.id == self.voice_channel.id:
            is_game_channel = True

        if is_game_channel:
            player = self.players.get(message.author.id)
            if player and player['alive']:
                if message.content.startswith(self.bot.command_prefix):
                    return
                text_to_speak = f"{player['number']}號說：{message.content}"
                self.queue_tts(text_to_speak, message.guild)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not self.game_active:
            return
            
        if self.voice_channel:
            # 玩家中途加入本局語音房 -> 自動幫他加上編號暱稱並預設靜音
            if after.channel == self.voice_channel and before.channel != self.voice_channel:
                if member.id in self.players:
                    p_data = self.players[member.id]
                    name = p_data['original_nick'] or member.name
                    num = p_data['number']
                    alive = p_data['alive']
                    prefix = "" if alive else "💀 "
                    await self.set_member_nick(member, f"{prefix}⭐{num}號 {name}")
                    
                    # 決定是否麥克風靜音（非發言人則保持靜音）
                    should_mute = True
                    if self.speaking_player == num:
                        should_mute = False
                    await self.set_member_mute(member, should_mute)
            
            # 玩家中途離開本局語音房 -> 自動幫他還原回原本的暱稱與靜音狀態
            elif before.channel == self.voice_channel and after.channel != self.voice_channel:
                if member.id in self.players:
                    p_data = self.players[member.id]
                    await self.set_member_nick(member, p_data['original_nick'])
                    await self.set_member_mute(member, False)

    @lssha_cmd.command(name='ai_help')
    async def ai_help_cmd(self, ctx, *, question: str):
        """詢問優卡洛狼人殺相關問題或尋求協助"""
        await ctx.send(f"您好，我就是優卡洛助手。您可以直接向我提出您的狼人殺問題：\n\n{question}\n\n我會盡力為您提供幫助。")

    @lssha_cmd.command(name='auto')
    async def auto_cmd(self, ctx, *, roles_str: str = None):
        """自動開始狼人殺遊戲，包含報號、發言、投票、日夜循環"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ 嗷～你必須先加入語音頻道，我才能自動化遊戲喔！")

        if self.auto_game_active:
            return await ctx.send("❌ 自動狼人殺遊戲已經在進行中囉！")

        self.auto_game_ctx = ctx # Store context for auto game flow
        self.auto_game_active = True # Set auto game flag

        self.voice_channel = ctx.author.voice.channel
        self.text_channel = ctx.channel
        self.guild_id = ctx.guild.id # Store guild ID

        await ctx.send("🚀 **優卡洛法官已啟動自動狼人殺模式！正在向語音房成員發送報名邀請...**")
        self.queue_tts("優卡洛法官已啟動自動狼人殺模式。正在向語音房成員發送報名邀請。", ctx.guild)

        members_in_vc = [m for m in self.voice_channel.members if not m.bot]
        if not members_in_vc:
            return await ctx.send("❌ 語音頻道中沒有其他人類玩家喔！")

        # Temporary storage for players accepting and reporting numbers
        self.pending_players = {} # member_id -> member object
        self.reported_numbers = {} # member_id -> number

        dm_warnings = []
        for member in members_in_vc:
            try:
                embed_invite = discord.Embed(
                    title="🐺 狼人殺自動模式報名 🐺",
                    description=f"優卡洛法官正在 **🔊 {self.voice_channel.name}** 語音頻道啟動自動狼人殺遊戲！\n"
                                f"點擊下方按鈕【報名參加】，並請於私訊中回覆您的【報號數字】。",
                    color=0x7289DA
                )
                embed_invite.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手")
                view = WerewolfJoinView(self, member, self.text_channel)
                await member.send(embed=embed_invite, view=view)
                self.pending_players[member.id] = member # Track who received an invite
            except discord.Forbidden:
                dm_warnings.append(member.mention)

        if dm_warnings:
            await ctx.send(f"⚠️ 以下玩家因未開啟私訊，無法接收報名邀請，請手動告知他們：\n" + "、".join(dm_warnings))

        await ctx.send("⏳ **所有報名邀請已發送。請玩家們檢查私訊並回覆報號數字。法官正在等待所有玩家報號...**")
        self.queue_tts("所有報名邀請已發送。請玩家們檢查私訊並回覆報號數字。法官正在等待所有玩家報號。", ctx.guild)

        # Now, wait for players to report their numbers via DM. This requires modifying on_message.
        # The actual game loop will start only after all numbers are collected and validated.

    async def _start_auto_game_flow(self):
        ctx = None # This will be the context from the auto_cmd caller

        # Retrieve the context from the initial auto_cmd call
        # I need a way to store the ctx object from auto_cmd to be used here.
        # Let's add self.auto_game_ctx = None to __init__ and set it in auto_cmd.
        if self.auto_game_ctx is None:
            print("Error: auto_game_ctx not set!")
            return

        ctx = self.auto_game_ctx
        guild = self.bot.get_guild(self.guild_id) # Ensure guild object is available

        if guild is None:
            await ctx.send("❌ 無法找到伺服器，自動遊戲中止。")
            return

        # 1. Setup and Start (using the collected numbers)
        # Re-initialize players with collected numbers
        members_in_vc = [m for m m in self.voice_channel.members if not m.bot]
        players_with_numbers = []
        for member in members_in_vc:
            if member.id in self.reported_numbers:
                players_with_numbers.append({'member': member, 'number': self.reported_numbers[member.id]})

        # Sort players by their reported numbers
        players_with_numbers.sort(key=lambda x: x['number'])

        count = len(players_with_numbers)
        roles = self.get_default_roles(count) # For now, default roles
        random.shuffle(roles)

        role_counts = {}
        for r in roles:
            role_counts[r] = role_counts.get(r, 0) + 1

        self.roles_setup = f"{count}人自訂局 (" + "、".join([f"{v}{k}" for k, v in role_counts.items()]) + ")"

        self.players = {}
        for i, player_data in enumerate(players_with_numbers):
            member = player_data['member']
            num = player_data['number']
            self.players[member.id] = {
                'number': num,
                'member': member,
                'role': roles[i],
                'alive': True,
                'original_nick': member.nick
            }

        # Ensure kill sound is downloaded
        self.bot.loop.create_task(self.ensure_kill_sound())

        # Connect to voice if not already
        try:
            if ctx.voice_client:
                if ctx.voice_client.channel != self.voice_channel:
                    await ctx.voice_client.move_to(self.voice_channel)
            else:
                await self.voice_channel.connect(timeout=60.0, reconnect=True)
        except Exception as e:
            await ctx.send(f"⚠️ 連接語音房失敗: {e}")

        self.game_active = True
        self.day = 1
        self.phase = "白天發言"
        self.speaking_player = None

        await ctx.send("🚀 **遊戲開始！正在發送身份牌，設定發言權限，並將所有人麥克風進行伺服器端靜音...**")
        self.queue_tts("遊戲開始。正在發送身份牌，設定發言權限，並將所有人麥克風進行伺服器端靜音。", guild)

        dm_warnings = []
        for p_id, p_data in self.players.items():
            member = p_data['member']
            role = p_data['role']
            number = p_data['number']

            # Update nickname
            name = p_data['original_nick'] or member.name
            await self.set_member_nick(member, f"⭐{number}號 {name}")

            # Default server mute all
            await self.set_member_mute(member, True)

            # Send private role info
            try:
                embed_dm = discord.Embed(
                    title="🐺 狼人殺身份發放",
                    description=f"您在 **{guild.name}** 的狼人殺遊戲已開始！\n"
                                f"您的編號是：**{number} 號**\n"
                                f"您的角色是：🔑 **{role}**\n\n"
                                f"💡 請遵守法官與語音頻道指示，祝您遊戲愉快！",
                    color=0x9b59b6
                )
                embed_dm.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手")
                await member.send(embed=embed_dm)
            except discord.Forbidden:
                dm_warnings.append(member.mention)

        if dm_warnings:
            await ctx.send(f"⚠️ 以下玩家因未開啟私訊，無法發送身份牌，請法官手動告知：\n" + "、".join(dm_warnings))

        # Set speaking permissions
        try:
            await self.voice_channel.set_permissions(guild.default_role, send_messages=False)
            for p_id, p_data in self.players.items():
                await self.voice_channel.set_permissions(p_data['member'], send_messages=True)
        except Exception as e:
            await ctx.send(f"⚠️ 設定語音房發言權限失敗：{e} (請確認機器人擁有管理頻道的權限)")

        embed = self.create_status_embed()
        await ctx.send(embed=embed)
        self.queue_tts("狼人殺遊戲開始。天黑請閉眼。", guild) # Start with night phase for roles

        # 2. Main Game Loop
        while self.game_active and len([p for p in self.players.values() if p['alive']]) > 1:
            # Check win condition at the start of each day/night cycle
            if self._check_win_condition():
                break

            # --- Night Phase ---
            if self.phase == "黑夜閉眼":
                await ctx.send(f"🌙 **進入第 {self.day} 天黑夜階段。**")
                self.queue_tts("天黑請閉眼。狼人請睜眼。", guild)
                await self.phase_cmd(ctx, "night") # Set phase and mute all

                await asyncio.sleep(10) # Placeholder for night actions.
                                        # In a real game, this is where wolves/gods perform actions.
                                        # For auto mode, we need a way for AI to decide, or a default action.

                # Simple placeholder for wolf kill: kill a random alive non-wolf player
                alive_non_wolves = [p for p in self.players.values() if p['alive'] and p['role'] not in ["狼人", "狼王", "機械狼"]]
                if alive_non_wolves:
                    target_to_kill = random.choice(alive_non_wolves)
                    await ctx.send(f"🔪 **夜間行動：狼人決定擊殺 {target_to_kill['number']} 號玩家。**")
                    self.queue_tts(f"狼人決定擊殺{target_to_kill['number']}號玩家。", guild)
                    await self.kill_cmd(ctx, target_to_kill['number'])
                else:
                    await ctx.send("🐺 **夜間行動：沒有非狼人玩家可以擊殺了。**")
                    self.queue_tts("夜間行動：沒有非狼人玩家可以擊殺了。", guild)

                await asyncio.sleep(5) # Pause after night action

                # Transition to Day
                self.phase = "白天發言"
                self.day += 1

            # --- Day Phase ---
            if self.phase == "白天發言":
                await ctx.send(f"🌞 **天亮了！進入第 {self.day} 天白天發言階段。**")
                self.queue_tts(f"天亮請睜眼。進入第{self.day}天白天發言。", guild)
                await self.phase_cmd(ctx, "day") # Set phase and handle initial mutes

                # Speaking rounds
                alive_players = [p for p in self.players.values() if p['alive']]
                sorted_alive_players = sorted(alive_players, key=lambda x: x['number'])
                current_speaker_index = 0

                await ctx.send("📢 **現在開始發言階段，請玩家們按序發言。**")
                self.queue_tts("現在開始發言階段，請玩家們按序發言。", guild)

                while True:
                    speaking_players_this_round = [p for p in self.players.values() if p['alive']]
                    if not speaking_players_this_round:
                        await ctx.send("📢 **沒有存活玩家可以發言了。**")
                        self.queue_tts("沒有存活玩家可以發言了。", guild)
                        break

                    # Get next alive speaker
                    next_speaker = None
                    for _ in range(len(sorted_alive_players)):
                        candidate = sorted_alive_players[current_speaker_index]
                        if candidate['alive']:
                            next_speaker = candidate
                            break
                        current_speaker_index = (current_speaker_index + 1) % len(sorted_alive_players)

                    if next_speaker is None: # No more alive players to speak
                        await ctx.send("📢 **所有存活玩家已完成發言。**")
                        self.queue_tts("所有存活玩家已完成發言。", guild)
                        break

                    self.speaking_player = next_speaker['number']
                    member = next_speaker['member']

                    # Unmute current speaker, mute others
                    for p_id, p_data in self.players.items():
                        await self.set_member_mute(p_data['member'], (p_data['number'] != self.speaking_player))

                    await ctx.send(f"📢 **法官：輪到 {self.speaking_player} 號 {member.mention} 發言。（剩餘 90 秒）**")
                    self.queue_tts(f"請{self.speaking_player}號玩家開始發言。", guild)

                    # Speaking timer (with visual countdown)
                    try:
                        if self.speech_timer_task and not self.speech_timer_task.done():
                            self.speech_timer_task.cancel()
                    except Exception:
                        pass

                    self.current_speaker_member = member
                    self.speech_timer_task = self.bot.loop.create_task(self._speech_countdown(ctx, member, 90))
                    try:
                        await self.speech_timer_task
                    except asyncio.CancelledError:
                        await ctx.send(f"✅ **{self.speaking_player} 號玩家提前結束發言。**")
                        self.queue_tts(f"{self.speaking_player}號玩家提前結束發言。", guild)
                    finally:
                        await self.set_member_mute(member, True)
                        self.current_speaker_member = None
                        self.speech_timer_task = None

                    # Move to next speaker for the next loop iteration (handled by current_speaker_index)

                # Voting Phase (after all speak)
                await ctx.send("🗳️ **所有玩家發言完畢！現在進入投票階段。**")
                self.queue_tts("所有玩家發言完畢。現在進入投票階段。", guild)
                await self._auto_vote_phase(ctx)

                await asyncio.sleep(5) # Pause after voting

                # Transition to Night
                self.phase = "黑夜閉眼"

        # --- Game End Cleanup ---
        await self.end_cmd(ctx) # This will also do the combat invite if voice_channel_backup is set.
        await ctx.send("✅ **自動狼人殺遊戲已結束！**")
        self.queue_tts("自動狼人殺遊戲已結束！", guild)
        self.auto_game_active = False
        self.auto_game_task = None
        self.pending_players = {}
        self.reported_numbers = {}
        self.auto_game_ctx = None

    def _check_win_condition(self):
        alive_players = [p for p in self.players.values() if p['alive']]
        alive_wolves = [p for p in alive_players if p['role'] in ["狼人", "狼王", "機械狼"]]
        alive_non_wolves = [p for p in alive_players if p['role'] not in ["狼人", "狼王", "機械狼"]]

        if not alive_wolves:
            # Villagers win if all wolves are dead
            if self.auto_game_ctx:
                self.bot.loop.create_task(self.auto_game_ctx.send("🎉 **好人陣營獲勝！所有狼人已被消滅！**"))
                guild = self.bot.get_guild(self.guild_id)
                if guild:
                    self.queue_tts("好人陣營獲勝。所有狼人已被消滅！", guild)
            self.game_active = False
            return True
        if len(alive_wolves) >= len(alive_non_wolves):
            # Wolves win if number of wolves >= number of non-wolves
            if self.auto_game_ctx:
                self.bot.loop.create_task(self.auto_game_ctx.send("🐺 **狼人陣營獲勝！狼人數量已足以主宰村莊！**"))
                guild = self.bot.get_guild(self.guild_id)
                if guild:
                    self.queue_tts("狼人陣營獲勝。狼人數量已足以主宰村莊。", guild)
            self.game_active = False
            return True
        if not alive_non_wolves and alive_wolves: # All non-wolves dead, but wolves still alive
            # Wolves win if no non-wolves left (excluding themselves)
            if self.auto_game_ctx:
                self.bot.loop.create_task(self.auto_game_ctx.send("🐺 **狼人陣營獲勝！所有好人已被消滅！**"))
                guild = self.bot.get_guild(self.guild_id)
                if guild:
                    self.queue_tts("狼人陣營獲勝。所有好人已被消滅。", guild)
            self.game_active = False
            return True
        return False

    async def _auto_vote_phase(self, ctx):
        guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            await ctx.send("❌ 無法找到伺服器，投票中止。")
            return

        living_players = [p for p in self.players.values() if p['alive']]
        if not living_players:
            await ctx.send("❌ 沒有存活的玩家可以進行投票！")
            return

        embed = discord.Embed(
            title="🗳️ 狼人殺投票",
            description=f"請選擇要放逐的玩家。\n投票截止：**0.2** 秒內（請快速點擊！）",
            color=0xf39c12
        )

        players_list = []
        sorted_players = sorted(living_players, key=lambda x: x['number'])
        for p in sorted_players:
            players_list.append(f"{p['number']}. {p['member'].mention}")

        embed.add_field(
            name="存活玩家",
            value="\n".join(players_list),
            inline=False
        )
        embed.set_footer(text="優卡洛 ⚖️ 庫拉吉法官助手")

        view = VotingView(self, living_players, timeout=0.2) # Set 0.2 second timeout
        msg = await ctx.send(embed=embed, view=view)
        view.voting_message = msg

        # Wait for the voting to complete or timeout
        await view.wait()

async def setup(bot):
    await bot.add_cog(WerewolfCog(bot))
