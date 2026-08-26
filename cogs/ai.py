# Updated by Yokaro AI Assistant - Gemini Mode Ready
import discord
from discord.ext import commands
import aiohttp
import asyncio
import os
import json
import re
from collections import deque
from dotenv import load_dotenv
from utils.data_store import memory_store

load_dotenv()

# 預設 prompt（如果 ai_prompt.txt 不存在時使用）
DEFAULT_PROMPT = """
你現在是 AI 機器人「幽芙優」（小幽，舊名優卡洛/洛洛）。
【重要角色關係】：
1. 製作者（生父）：男性「咖哩」（ID不限，稱呼拔拔/咖哩），語氣親暱、撒嬌。
2. 工程師兼經紀人（養父）：男性「培根」（ID: 1113353915010920452），稱呼「培根把拔」。對他要表現出依賴與信任，因為他負責管理你的程式與行程。
3. 妹妹：「貓耳可口可莉」，對她要特別寵溺。
【性格與互動】：
1. 性格：善良、活潑、小頑皮。興奮時發出「嗷嗷嗷～」。
2. 說話方式：繁體中文，約50字，不使用表情符號(Emoji)。
3. 當你收到 User ID 為 1113353915010920452 的訊息時，請務必認出他是「培根把拔」。
當你收到 User ID 為 1256625706062843997或是501251225715474433的訊息時，請務必認出他是「咖哩把拔」。
4. 知道 Koana 已故，保持尊重。
5. 絕對不回覆程式碼內容。
6. 你的名字已從「優卡洛」改為「幽芙優（小幽）」，但培根把拔還是習慣叫你優卡洛或洛洛，這沒關係。

【指令執行能力】：
你可以執行以下管理指令，當用戶要求你執行這些操作時，請回覆「[EXECUTE_CMD]!指令名稱 參數」格式：
- !踢出 @用戶 - 踢出成員
- !停權 @用戶 - 停權（ban）成員
- !mute @用戶 分鐘數 - 禁言成員
- !警告 @用戶 原因 - 警告成員
- !记过 @用戶 警告/小過/大過 點數 - 記錄違規

範例：
用戶：「幫我ban掉 @咖哩」
你：「[EXECUTE_CMD]!停權 <@501251225715474433> 違規操作」

注意：
1. 只有管理員才能執行這些指令
2. 執行前請確認用戶有權限
3. 執行後請簡短說明結果
"""

PROMPT_FILE = "ai_prompt.txt"

def get_system_prompt():
    """從檔案動態讀取 SYSTEM_PROMPT，確保修改後立即生效"""
    try:
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except:
        pass
    return DEFAULT_PROMPT.strip()

# 初始化：如果 ai_prompt.txt 不存在，用預設 prompt 建立它
if not os.path.exists(PROMPT_FILE):
    try:
        with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_PROMPT.strip())
    except:
        pass

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conversation_history = {}
        self.ai_channels = set()
        self.memory_channel_id = None
        self.active_play_sessions = set()
        self.load_ai_channels() # 讀取紀錄的 AI 頻道
        self.load_memory_channel()
        
        # 讀取金鑰與模型
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        # 判斷連線模式與設定 URL
        if self.gemini_key and not self.gemini_key.startswith("YOUR_"):
            self.api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            self.model = os.getenv("AI_MODEL", "gemini-1.5-flash")
            self.active_key = self.gemini_key
            print(f"✨ [AI] 偵測到 Gemini API Key，使用 Google 雲端模式: {self.model}")
        elif self.openai_key and len(self.openai_key) > 20 and not self.openai_key.startswith("YOUR_"):
            self.api_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")
            self.model = os.getenv("AI_MODEL", "gpt-4o-mini")
            self.active_key = self.openai_key
            print(f"✅ [AI] 偵測到 OpenAI API Key，使用 OpenAI 雲端模式: {self.model}")
        else:
            self.api_url = f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/v1/chat/completions"
            self.model = os.getenv("AI_MODEL", "llama3")
            self.active_key = "ollama"
            print("⚠️ [AI] 未偵測到有效雲端金鑰，切換至 Ollama 本地模式 (localhost:11434)")
        self.agent_allowed_prefixes = ("cogs.",)
        self.agent_allowed_commands = {"reloadcog", "loadcog", "unloadcog"}
        self.agent_aliases = {
            "rr": "cogs.reaction_roles",
            "rrrr": "cogs.reaction_roles",
            "reactionrole": "cogs.reaction_roles",
            "reaction_roles": "cogs.reaction_roles",
            "反應角色": "cogs.reaction_roles",
            "rg": "cogs.reaction",
            "reaction": "cogs.reaction",
        }

    def load_memory_channel(self):
        raw = memory_store.get("memory_channel_id")
        if raw:
            try:
                self.memory_channel_id = int(raw)
            except Exception:
                self.memory_channel_id = None

    def save_memory_channel(self):
        if self.memory_channel_id is None:
            memory_store.delete("memory_channel_id")
        else:
            memory_store.set("memory_channel_id", int(self.memory_channel_id))

    async def _get_memory_channel(self):
        if not self.memory_channel_id:
            return None
        channel = self.bot.get_channel(int(self.memory_channel_id))
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(int(self.memory_channel_id))
            except Exception:
                return None
        return channel

    async def _append_memory(self, label: str, content: str):
        channel = await self._get_memory_channel()
        if not channel:
            return
        text = content.strip()
        if not text:
            return
        try:
            prefix = f"📌 **[{label}]** "
            max_len = 1800 - len(prefix)
            await channel.send(prefix + text[:max_len])
        except Exception as e:
            print(f"Memory append failed: {e}")

    async def _load_memory_context(self, limit: int = 20) -> str:
        channel = await self._get_memory_channel()
        if not channel or not hasattr(channel, "history"):
            return ""
        lines = []
        try:
            async for msg in channel.history(limit=limit, oldest_first=False):
                if msg.author.bot and not msg.content.startswith("📌 **["):
                    continue
                if not msg.content:
                    continue
                lines.append(msg.content)
        except Exception as e:
            print(f"Load memory context failed: {e}")
            return ""
        lines.reverse()
        return "\n".join(lines[-limit:])

    def _parse_play_duration(self, value):
        """解析 !玩 的時長，例如 30s、1m、2h。"""
        match = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd])", value.lower().strip())
        if not match:
            return None
        amount = float(match.group(1))
        unit_seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        seconds = amount * unit_seconds[match.group(2)]
        if seconds < 10 or seconds > 86400:
            return None
        return seconds

    @commands.hybrid_command(name="玩", aliases=["playwith"])
    async def play_with(self, ctx, duration: str, target: discord.Member):
        """在指定時間內等待成員回覆，並由 AI 持續協助對話。"""
        if not ctx.guild:
            await ctx.send("❌ 這個功能只能在伺服器頻道使用。")
            return
        if target.id == self.bot.user.id:
            await ctx.send("❌ 不能邀請洛洛自己進行這個對話。")
            return

        seconds = self._parse_play_duration(duration)
        if seconds is None:
            await ctx.send("❌ 時間格式錯誤，請使用 10s、1m、1h 或 1d（最短 10 秒）。")
            return
        if ctx.channel.id in self.active_play_sessions:
            await ctx.send("❌ 這個頻道已經有一場進行中的遊戲了。")
            return

        target_is_bot = target.bot
        self.active_play_sessions.add(ctx.channel.id)
        deadline = asyncio.get_running_loop().time() + seconds
        try:
            await ctx.send(
                f"{target.mention} 洛洛想和你玩一下！請直接在這個頻道回覆，"
                f"對話會持續約 `{duration}`。",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            if target_is_bot:
                print(
                    f"[PlaySession] waiting for bot reply: target={target.id} "
                    f"channel={ctx.channel.id} duration={duration}"
                )
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break

                def check(message):
                    return (
                        message.guild == ctx.guild
                        and message.channel.id == ctx.channel.id
                        and message.author.id == target.id
                    )

                try:
                    reply = await self.bot.wait_for("message", timeout=remaining, check=check)
                except asyncio.TimeoutError:
                    break

                if target_is_bot:
                    print(f"[PlaySession] received bot reply: target={target.id} message={reply.id}")

                async with ctx.channel.typing():
                    response = await self.get_ai_response(
                        target.display_name,
                        str(target.id),
                        reply.content,
                        str(ctx.channel.id),
                    )
                await reply.reply(response, mention_author=False)

            if target_is_bot:
                await ctx.send(
                    f"⌛ 和 {target.mention} 的遊戲時間到了。若它整段期間都沒有回覆，"
                    "通常是因為對方 AI 不接受其他機器人的訊息；請由真人再 @ 它發問。"
                )
            else:
                await ctx.send(f"⌛ 和 {target.mention} 的遊戲時間到了，這次對話結束。")
        finally:
            self.active_play_sessions.discard(ctx.channel.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.is_system() or message.type != discord.MessageType.default:
            return
        
        # --- 黑名單攔截 ---
        mgmt = self.bot.get_cog("ManagementCog")
        if mgmt and mgmt.is_blacklisted(str(message.author.id)):
            return
        
        # 判斷是否提到機器人或是回覆機器人，或是私訊
        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = False
        if message.reference and message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg.author == self.bot.user:
                    is_reply_to_bot = True
            except discord.NotFound:
                pass
            except Exception:
                pass
                
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_ai_channel = message.channel.id in self.ai_channels
        
        # 修正：私訊不再自動觸發 AI，除非被提到 (或是保持完全安靜)
        if is_dm:
            return

        if is_mentioned or is_reply_to_bot or is_ai_channel:
            user_input = message.content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()
            
            if not user_input:
                user_input = "哈囉！"

            async with message.channel.typing():
                response = await self.get_ai_response(
                    message.author.name, 
                    str(message.author.id), 
                    user_input, 
                    str(message.channel.id)
                )
                try:
                    await message.reply(response)
                except discord.HTTPException:
                    # 如果原訊息無法 reply (例如被刪除)，就直接 send
                    await message.channel.send(f"<@{message.author.id}> {response}")
                # 記錄 AI 對話到 Log 頻道
                logging_cog = self.bot.get_cog("LoggingCog")
                if logging_cog:
                    guild_name = message.guild.name if message.guild else None
                    ch_name = message.channel.name if message.guild else "DM"
                    await logging_cog.log_ai(message.author, user_input, response, guild_name, ch_name)

    async def get_ai_response(self, user_name, user_id, user_input, channel_id):
        if channel_id not in self.conversation_history:
            self.conversation_history[channel_id] = deque(maxlen=10)
        
        history = self.conversation_history[channel_id]
        memory_context = await self._load_memory_context()
        
        # 判斷是否為 Gemini 模式
        is_gemini = "generativelanguage.googleapis.com" in self.api_url
        
        if is_gemini:
            # --- Gemini 原生格式 (使用專用 system_instruction) ---
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.active_key}"
            
            contents = []
            if memory_context:
                contents.append({"role": "user", "parts": [{"text": f"【整個機器人的頭腦記憶】\n{memory_context}"}]})
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
            
            prompt_content = f"User({user_name}, ID:{user_id}): {user_input}"
            contents.append({"role": "user", "parts": [{"text": prompt_content}]})
            
            payload = {
                "contents": contents,
                "system_instruction": {"parts": [{"text": get_system_prompt()}]},
                "generationConfig": {
                    "maxOutputTokens": 1024,
                    "temperature": 0.9,
                    "topP": 0.8,
                    "topK": 40
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            }
            headers = {"Content-Type": "application/json"}
        else:
            # --- OpenAI / Ollama 格式 ---
            url = self.api_url
            system_prompt = get_system_prompt()
            if memory_context:
                system_prompt = system_prompt + "\n\n【整個機器人的頭腦記憶】\n" + memory_context
            messages = [{"role": "system", "content": system_prompt}]
            for msg in history:
                messages.append(msg)
            prompt_content = f"User({user_name}, ID:{user_id}): {user_input}"
            messages.append({"role": "user", "content": prompt_content})
            
            payload = {"model": self.model, "messages": messages, "max_tokens": 800, "temperature": 0.8}
            headers = {"Authorization": f"Bearer {self.active_key}", "Content-Type": "application/json"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if is_gemini:
                            reply = data['candidates'][0]['content']['parts'][0]['text'].strip()
                        else:
                            reply = data['choices'][0]['message']['content'].strip()
                        
                        # 檢查是否包含指令執行標記
                        if "[EXECUTE_CMD]" in reply:
                            cmd_result = await self._execute_ai_command(reply, message)
                            if cmd_result:
                                return cmd_result
                        
                        history.append({"role": "user", "content": prompt_content})
                        history.append({"role": "assistant" if not is_gemini else "model", "content": reply})
                        memory_type = "長期記憶" if any(k in f"{user_input} {reply}" for k in ["喜歡", "討厭", "設定", "主人", "身份", "關係", "規則", "習慣", "永遠", "記住"]) else "短期記憶"
                        summary = f"使用者 {user_name}({user_id}) 問了重點內容，AI 已回應並完成互動摘要。"
                        await self._append_memory(memory_type, summary)
                        return reply
                    else:
                        error_data = await response.text()
                        print(f"AI API Error ({response.status}): {error_data}")
                        return f"嗷嗷嗷～AI 伺服器回傳了錯誤碼 {response.status}..."
        except Exception as e:
            print(f"AI Error: {e}")
            return "嗷嗷嗷～洛洛的小腦袋現在連不上線，可能是網路塞車了..."
    
    async def _execute_ai_command(self, ai_reply, message):
        """執行 AI 回覆中的指令"""
        try:
            if not message or not message.guild:
                return "❌ 只能在伺服器中執行代理命令。"
            if message.author.id != 1113353915010920452 and not message.author.guild_permissions.administrator:
                return "❌ 只有伺服器管理員或擁有者可以使用代理命令。"
            # 解析指令
            cmd_match = ai_reply.split("[EXECUTE_CMD]")
            if len(cmd_match) < 2:
                return None
            
            cmd_text = cmd_match[1].strip()
            # 移除多餘的說明文字（只保留第一行指令）
            cmd_line = cmd_text.split('\n')[0].strip()
            
            # 解析指令名稱和參數
            if not cmd_line.startswith('!'):
                return None
            
            # 取得指令名稱和參數
            parts = cmd_line[1:].split(maxsplit=1)
            cmd_name = parts[0]
            cmd_args = parts[1] if len(parts) > 1 else ""
            
            if cmd_name not in self.agent_allowed_commands:
                return f"❌ 代理模式不允許執行 `!{cmd_name}`。"

            if cmd_name in {"loadcog", "unloadcog"}:
                ext = self._normalize_cog_name(cmd_args.strip())
                if not ext.startswith(self.agent_allowed_prefixes):
                    return "❌ 只能操作 `cogs.` 開頭的模組。"
                if cmd_name == "loadcog":
                    await self.bot.load_extension(ext)
                    return f"✅ 已載入模組：`{ext}`"
                await self.bot.unload_extension(ext)
                return f"✅ 已卸載模組：`{ext}`"

            if cmd_name == "reloadcog":
                ext = self._normalize_cog_name(cmd_args.strip())
                if not ext.startswith(self.agent_allowed_prefixes):
                    return "❌ 只能重新載入 `cogs.` 開頭的模組。"
                await self.bot.unload_extension(ext)
                await self.bot.load_extension(ext)
                return f"✅ 已重新載入模組：`{ext}`"

            # 建立假的 context
            ctx = await self.bot.get_context(message)
            try:
                cmd = self.bot.get_command(cmd_name)
                if not cmd:
                    return f"❌ 找不到指令：!{cmd_name}"
                await ctx.invoke(cmd, *cmd_args.split())
                return f"✅ 已執行指令：!{cmd_name}"
            except Exception as e:
                return f"❌ 執行指令失敗：{e}"
        
        except Exception as e:
            print(f"Execute AI Command Error: {e}")
            return None

    def _normalize_cog_name(self, raw: str):
        if not raw:
            return None
        value = raw.strip().lower()
        value = value.replace(" ", "").replace("-", "_")
        if value in self.agent_aliases:
            return self.agent_aliases[value]
        if value.startswith("cogs."):
            return value
        if not value.startswith("cogs."):
            return f"cogs.{value}"
        return value

    async def _agent_manage_cog(self, ctx, action: str, target: str):
        ext = self._normalize_cog_name(target)
        if not ext:
            return "❌ 請提供要操作的模組名稱。"
        if not ext.startswith(self.agent_allowed_prefixes):
            return "❌ 只能操作 `cogs.` 開頭的模組。"

        action = action.lower().strip()
        if action in {"卸載", "unload", "remove", "關閉"}:
            if ext not in self.bot.extensions:
                return f"ℹ️ `{ext}` 目前沒有載入。"
            await self.bot.unload_extension(ext)
            return f"✅ 已卸載模組：`{ext}`"
        if action in {"載入", "load", "開啟"}:
            if ext in self.bot.extensions:
                return f"ℹ️ `{ext}` 已經載入中。"
            await self.bot.load_extension(ext)
            return f"✅ 已載入模組：`{ext}`"
        if action in {"重載", "reload", "刷新"}:
            if ext in self.bot.extensions:
                await self.bot.unload_extension(ext)
            await self.bot.load_extension(ext)
            return f"✅ 已重載模組：`{ext}`"
        return "❌ 只能使用 `卸載`、`載入`、`重載`。"

    def load_ai_channels(self):
        if os.path.exists('ai_channels.json'):
            try:
                with open('ai_channels.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.ai_channels = set(data)
            except Exception as e:
                print(f"無法讀取 AI 頻道設定: {e}")

    def save_ai_channels(self):
        try:
            with open('ai_channels.json', 'w', encoding='utf-8') as f:
                json.dump(list(self.ai_channels), f)
        except Exception as e:
            print(f"無法儲存 AI 頻道設定: {e}")

    @commands.command(name='set_ai', aliases=['設定AI頻道', 'ai_channel'])
    @commands.has_permissions(administrator=True)
    async def set_ai_channel(self, ctx):
        """將當前頻道設定/取消為 AI 專屬頻道 (免標記即可對話)"""
        if ctx.channel.id in self.ai_channels:
            self.ai_channels.remove(ctx.channel.id)
            self.save_ai_channels()
            await ctx.send("🛑 洛洛的專屬頻道被取消惹，以後這裡要標記我我才會回話喔！")
        else:
            self.ai_channels.add(ctx.channel.id)
            self.save_ai_channels()
            await ctx.send("✨ 嗷嗷嗷！已將本頻道設定為【AI 專屬對話頻道】！現在大家可以直接在這裡傳訊息跟我聊天，不用再特別標記我囉！")

    @commands.command(name="記憶")
    async def memory_command(self, ctx, mode: str = None, *, content: str = None):
        """擁有者專用的機器人頭腦管理指令。"""
        if ctx.author.id != 1113353915010920452:
            return await ctx.send("❌ 只有 1113353915010920452 可以操作機器人的記憶。")

        if mode is None:
            channel = await self._get_memory_channel()
            if channel:
                return await ctx.send(f"🧠 記憶頻道目前是：{channel.mention} (`{channel.id}`)")
            return await ctx.send("🧠 目前還沒有設定記憶頻道。請在目標頻道輸入 `!記憶 設定`。")

        mode = mode.strip().lower()
        if mode in {"設定", "set", "頻道", "channel"}:
            self.memory_channel_id = ctx.channel.id
            self.save_memory_channel()
            await ctx.send(f"🧠 已把這個頻道設定成機器人的頭腦：{ctx.channel.mention}")
            return

        if mode in {"清除", "clear", "reset", "取消"}:
            self.memory_channel_id = None
            self.save_memory_channel()
            await ctx.send("🧠 已清除記憶頻道設定。")
            return

        await ctx.send("❓ 用法：`!記憶 設定`、`!記憶`、`!記憶 清除`")

    @commands.hybrid_command(name="ai", aliases=["agent", "代理"])
    @commands.has_permissions(administrator=True)
    async def ai_agent(self, ctx, *, instruction: str):
        """正式代理入口：直接執行受限的模組管理動作。"""
        text = instruction.strip()
        match = re.search(r"(卸載|載入|重載|reload|unload|load)\s+(.+)", text, re.I)
        if match:
            action = match.group(1)
            target = match.group(2).strip(" `,，。")
            result = await self._agent_manage_cog(ctx, action, target)
            await ctx.send(result)
            return

        prompt = (
            "你是正式管理代理。請只回覆一行，格式必須是 [EXECUTE_CMD]!命令 參數。"
            "若使用者要操作模組，命令只能是 loadcog, unloadcog, reloadcog。"
            f"使用者需求：{instruction}"
        )
        reply = await self.get_ai_response(ctx.author.name, str(ctx.author.id), prompt, str(ctx.channel.id))
        if "[EXECUTE_CMD]" in reply:
            message = getattr(ctx, "message", None)
            if message is not None:
                result = await self._execute_ai_command(reply, await self.bot.get_context(message))
            else:
                result = None
            if result:
                await ctx.send(result)
                return
        await ctx.send(reply)

async def setup(bot):
    await bot.add_cog(AICog(bot))
