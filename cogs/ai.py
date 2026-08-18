# Updated by Yokaro AI Assistant - Gemini Mode Ready
import discord
from discord.ext import commands
import aiohttp
import os
import json
import re
from collections import deque
from dotenv import load_dotenv

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
        self.load_ai_channels() # 讀取紀錄的 AI 頻道
        
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

    async def get_ai_response(self, user_name, user_id, user_input, channel_id):
        if channel_id not in self.conversation_history:
            self.conversation_history[channel_id] = deque(maxlen=10)
        
        history = self.conversation_history[channel_id]
        
        # 判斷是否為 Gemini 模式
        is_gemini = "generativelanguage.googleapis.com" in self.api_url
        
        if is_gemini:
            # --- Gemini 原生格式 (使用專用 system_instruction) ---
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.active_key}"
            
            contents = []
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
            messages = [{"role": "system", "content": get_system_prompt()}]
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
                            # 執行指令
                            cmd_result = await self._execute_ai_command(reply, message if 'message' in dir() else None)
                            if cmd_result:
                                return cmd_result
                        
                        history.append({"role": "user", "content": prompt_content})
                        history.append({"role": "assistant" if not is_gemini else "model", "content": reply})
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
            
            # 檢查是否有對應的指令
            cmd = self.bot.get_command(cmd_name)
            if not cmd:
                return f"❌ 找不到指令：!{cmd_name}"
            
            # 檢查權限
            if not message:
                return "❌ 無法執行指令：缺少上下文"
            
            # 建立假的 context
            ctx = await self.bot.get_context(message)
            ctx.author = message.author
            ctx.channel = message.channel
            ctx.guild = message.guild
            
            # 檢查使用者是否有權限執行指令
            try:
                # 嘗試取得權限檢查
                can_run = await cmd.can_run(ctx)
                if not can_run:
                    return f"❌ 你沒有權限執行 !{cmd_name}"
            except:
                # 如果無法檢查，假設有權限
                pass
            
            # 執行指令
            try:
                # 解析參數
                if cmd_args:
                    # 處理 @用戶 格式
                    cmd_args = cmd_args.replace('<@', '').replace('>', '')
                
                await ctx.invoke(cmd, *cmd_args.split())
                return f"✅ 已執行指令：!{cmd_name}"
            except Exception as e:
                return f"❌ 執行指令失敗：{e}"
        
        except Exception as e:
            print(f"Execute AI Command Error: {e}")
            return None

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

async def setup(bot):
    await bot.add_cog(AICog(bot))
