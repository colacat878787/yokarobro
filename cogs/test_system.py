import discord
from discord.ext import commands
import asyncio
import json
import time
from datetime import datetime
import sys
import os

class TestSystemCog(commands.Cog):
    """完整的機器人功能測試系統"""
    
    def __init__(self, bot):
        self.bot = bot
        self.test_results = {}
        self.log_file = f"test_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
    def log(self, message):
        """寫入日誌"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_msg + '\n')
        except:
            pass
    
    @commands.hybrid_command(name='testall', aliases=['測試全部', '系統檢測'])
    @commands.has_permissions(administrator=True)
    async def test_all_functions(self, ctx):
        """測試所有機器人功能並重新載入cogs（管理員專用）"""
        
        # 初始化測試結果
        self.test_results = {
            'cog_reload': {'status': 'pending', 'details': []},
            'cog_loading': {'status': 'pending', 'details': []},
            'command_test': {'status': 'pending', 'details': []},
            'api_connection': {'status': 'pending', 'details': []},
            'database': {'status': 'pending', 'details': []}
        }
        
        # 發送初始進度訊息
        progress_embed = discord.Embed(
            title="🔍 開始全面系統檢測",
            description="正在初始化測試程序...",
            color=0x3498db
        )
        progress_message = await ctx.send(embed=progress_embed)
        
        try:
            # ========== 第一階段：重新載入所有 Cogs ==========
            await self.update_progress(progress_message, "第一階段：重新載入所有 Cogs", 0)
            self.log("=" * 60)
            self.log("開始測試：重新載入所有 Cogs")
            
            reload_success = []
            reload_failed = []
            
            # 取得所有已載入的 cogs
            loaded_cogs = list(self.bot.cogs.keys())
            self.log(f"目前載入的 Cogs: {', '.join(loaded_cogs)}")
            
            # 重新載入每個 cog
            for cog_name in loaded_cogs:
                try:
                    cog = self.bot.get_cog(cog_name)
                    if cog:
                        # 取得模組路徑
                        module_path = cog.__module__
                        self.log(f"正在重新載入 {cog_name} ({module_path})...")
                        
                        # 卸載後重新載入
                        await self.bot.unload_extension(module_path)
                        await asyncio.sleep(0.5)  # 避免過快
                        await self.bot.load_extension(module_path)
                        
                        reload_success.append(cog_name)
                        self.log(f"✅ {cog_name} 重新載入成功")
                except Exception as e:
                    reload_failed.append(f"{cog_name}: {str(e)}")
                    self.log(f"❌ {cog_name} 重新載入失敗: {e}")
            
            # 更新 reload 測試結果
            self.test_results['cog_reload'] = {
                'status': 'success' if not reload_failed else 'partial',
                'details': {
                    'success': reload_success,
                    'failed': reload_failed,
                    'total': len(loaded_cogs)
                }
            }
            
            await self.update_progress(progress_message, "第一階段：重新載入所有 Cogs", 100, 
                                      f"✅ 成功: {len(reload_success)}/{len(loaded_cogs)}")
            await asyncio.sleep(1)
            
            # ========== 第二階段：檢查所有 Cogs 是否正常載入 ==========
            await self.update_progress(progress_message, "第二階段：檢查 Cogs 載入狀態", 0)
            self.log("\n" + "=" * 60)
            self.log("開始測試：檢查 Cogs 載入狀態")
            
            # 從 initial_extensions 檢查
            expected_cogs = []
            if hasattr(self.bot, 'initial_extensions'):
                for ext in self.bot.initial_extensions:
                    cog_name = ext.replace('cogs.', '').capitalize()
                    if hasattr(self.bot, 'cogs') and ext in [cog.__module__ for cog in self.bot.cogs.values()]:
                        expected_cogs.append((ext, True))
                        self.log(f"✅ {ext} 已載入")
                    else:
                        expected_cogs.append((ext, False))
                        self.log(f"❌ {ext} 未載入")
            
            loaded_count = sum(1 for _, loaded in expected_cogs if loaded)
            self.test_results['cog_loading'] = {
                'status': 'success' if loaded_count == len(expected_cogs) else 'partial',
                'details': {
                    'loaded': loaded_count,
                    'total': len(expected_cogs),
                    'list': expected_cogs
                }
            }
            
            await self.update_progress(progress_message, "第二階段：檢查 Cogs 載入狀態", 100,
                                      f"✅ 已載入: {loaded_count}/{len(expected_cogs)}")
            await asyncio.sleep(1)
            
            # ========== 第三階段：測試關鍵指令 ==========
            await self.update_progress(progress_message, "第三階段：測試關鍵指令", 0)
            self.log("\n" + "=" * 60)
            self.log("開始測試：關鍵指令檢查")
            
            command_tests = []
            
            # 測試基本指令
            basic_commands = ['ping', 'help', 'version']
            for cmd_name in basic_commands:
                cmd = self.bot.get_command(cmd_name)
                if cmd:
                    command_tests.append((cmd_name, True, "指令存在"))
                    self.log(f"✅ 指令 !{cmd_name} 存在")
                else:
                    command_tests.append((cmd_name, False, "指令不存在"))
                    self.log(f"❌ 指令 !{cmd_name} 不存在")
            
            # 測試各 cog 的主要指令
            cog_commands = {
                'AICog': ['ai', 'set_ai'],
                'MusicCog': ['play', 'skip', 'stop'],
                'AdminCog': ['panel', 'webpanel'],
                'EconomyCog': ['balance', 'work', 'gamble'],
                'LevelsCog': ['profile', 'rank'],
                'TicketsCog': ['ticket'],
                'ModmailCog': ['modmail']
            }
            
            for cog_name, commands in cog_commands.items():
                cog = self.bot.get_cog(cog_name)
                if cog:
                    for cmd_name in commands:
                        cmd = self.bot.get_command(cmd_name)
                        if cmd:
                            command_tests.append((f"{cog_name}.{cmd_name}", True, "指令存在"))
                        else:
                            command_tests.append((f"{cog_name}.{cmd_name}", False, "指令不存在"))
            
            passed_commands = sum(1 for _, success, _ in command_tests if success)
            self.test_results['command_test'] = {
                'status': 'success' if passed_commands == len(command_tests) else 'partial',
                'details': {
                    'passed': passed_commands,
                    'total': len(command_tests),
                    'tests': command_tests
                }
            }
            
            await self.update_progress(progress_message, "第三階段：測試關鍵指令", 100,
                                      f"✅ 通過: {passed_commands}/{len(command_tests)}")
            await asyncio.sleep(1)
            
            # ========== 第四階段：檢查 API 連接 ==========
            await self.update_progress(progress_message, "第四階段：檢查 API 連接", 0)
            self.log("\n" + "=" * 60)
            self.log("開始測試：API 連接檢查")
            
            api_tests = []
            
            # 檢查 AI API
            ai_cog = self.bot.get_cog("AICog")
            if ai_cog:
                api_type = "Gemini" if "generativelanguage.googleapis.com" in ai_cog.api_url else \
                           "OpenAI" if "openai.com" in ai_cog.api_url else "Ollama (本地)"
                api_tests.append(("AI API", True, f"使用 {api_type} 模式"))
                self.log(f"✅ AI API 已配置: {api_type}")
            else:
                api_tests.append(("AI API", False, "AICog 未載入"))
                self.log("❌ AI API 未配置")
            
            # 檢查其他 API 設定
            if os.getenv("GEMINI_API_KEY"):
                api_tests.append(("Gemini API Key", True, "已設定"))
            if os.getenv("OPENAI_API_KEY"):
                api_tests.append(("OpenAI API Key", True, "已設定"))
            if os.getenv("DISCORD_TOKEN"):
                api_tests.append(("Discord Token", True, "已設定"))
            
            passed_apis = sum(1 for _, success, _ in api_tests if success)
            self.test_results['api_connection'] = {
                'status': 'success' if passed_apis == len(api_tests) else 'partial',
                'details': {
                    'passed': passed_apis,
                    'total': len(api_tests),
                    'tests': api_tests
                }
            }
            
            await self.update_progress(progress_message, "第四階段：檢查 API 連接", 100,
                                      f"✅ 通過: {passed_apis}/{len(api_tests)}")
            await asyncio.sleep(1)
            
            # ========== 第五階段：檢查資料儲存 ==========
            await self.update_progress(progress_message, "第五階段：檢查資料儲存系統", 0)
            self.log("\n" + "=" * 60)
            self.log("開始測試：資料儲存系統")
            
            db_tests = []
            
            # 檢查必要的資料檔案
            data_files = [
                ('ai_channels.json', 'AI 頻道設定'),
                ('ai_prompt.txt', 'AI 提示詞'),
                ('kuji_data.json', '一番賞資料'),
                ('economy_data.json', '經濟系統資料'),
                ('levels.json', '等級系統資料')
            ]
            
            for filename, desc in data_files:
                if os.path.exists(filename):
                    db_tests.append((desc, True, "檔案存在"))
                    self.log(f"✅ {desc} ({filename}) 存在")
                else:
                    db_tests.append((desc, False, "檔案不存在（將自動建立）"))
                    self.log(f"⚠️ {desc} ({filename}) 不存在")
            
            # 檢查 utils 模組
            try:
                from utils.config import config_manager
                db_tests.append(("Config Manager", True, "正常載入"))
                self.log("✅ Config Manager 正常載入")
            except Exception as e:
                db_tests.append(("Config Manager", False, str(e)))
                self.log(f"❌ Config Manager 載入失敗: {e}")
            
            try:
                from utils.data_store import DataStore
                db_tests.append(("DataStore", True, "正常載入"))
                self.log("✅ DataStore 正常載入")
            except Exception as e:
                db_tests.append(("DataStore", False, str(e)))
                self.log(f"❌ DataStore 載入失敗: {e}")
            
            passed_db = sum(1 for _, success, _ in db_tests if success)
            self.test_results['database'] = {
                'status': 'success' if passed_db == len(db_tests) else 'partial',
                'details': {
                    'passed': passed_db,
                    'total': len(db_tests),
                    'tests': db_tests
                }
            }
            
            await self.update_progress(progress_message, "第五階段：檢查資料儲存系統", 100,
                                      f"✅ 通過: {passed_db}/{len(db_tests)}")
            await asyncio.sleep(1)
            
            # ========== 生成最終報告 ==========
            await self.update_progress(progress_message, "生成測試報告", 100)
            self.log("\n" + "=" * 60)
            self.log("測試完成，生成報告...")
            
            # 判斷整體狀態
            all_status = [v['status'] for v in self.test_results.values()]
            if all(s == 'success' for s in all_status):
                overall_status = "✅ 全部正常"
                overall_color = 0x00ff00
            elif all(s == 'failed' for s in all_status):
                overall_status = "❌ 全部失敗"
                overall_color = 0xff0000
            else:
                overall_status = "⚠️ 部分正常"
                overall_color = 0xffaa00
            
            # 建立詳細報告 embed
            report_embed = discord.Embed(
                title=f"📊 系統檢測報告 - {overall_status}",
                description=f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                           f"詳細日誌已儲存至: `{self.log_file}`",
                color=overall_color
            )
            
            # 加入各階段結果
            for stage, result in self.test_results.items():
                stage_name = {
                    'cog_reload': '🔄 Cogs 重新載入',
                    'cog_loading': '📦 Cogs 載入狀態',
                    'command_test': '⚡ 指令測試',
                    'api_connection': '🌐 API 連接',
                    'database': '💾 資料儲存'
                }.get(stage, stage)
                
                status_emoji = {'success': '✅', 'partial': '⚠️', 'failed': '❌'}.get(result['status'], '❓')
                
                if stage == 'cog_reload':
                    details = result['details']
                    value = f"成功: {len(details['success'])}/{details['total']}\n"
                    if details['failed']:
                        value += f"失敗: {', '.join(details['failed'][:3])}"
                    report_embed.add_field(name=f"{stage_name} {status_emoji}", value=value, inline=False)
                
                elif stage == 'cog_loading':
                    details = result['details']
                    value = f"已載入: {details['loaded']}/{details['total']}"
                    report_embed.add_field(name=f"{stage_name} {status_emoji}", value=value, inline=False)
                
                elif stage == 'command_test':
                    details = result['details']
                    value = f"通過: {details['passed']}/{details['total']}"
                    if details['passed'] < details['total']:
                        failed = [t[0] for t in details['tests'] if not t[1]]
                        value += f"\n失敗: {', '.join(failed[:5])}"
                    report_embed.add_field(name=f"{stage_name} {status_emoji}", value=value, inline=False)
                
                elif stage == 'api_connection':
                    details = result['details']
                    value = f"通過: {details['passed']}/{details['total']}"
                    report_embed.add_field(name=f"{stage_name} {status_emoji}", value=value, inline=False)
                
                elif stage == 'database':
                    details = result['details']
                    value = f"通過: {details['passed']}/{details['total']}"
                    if details['passed'] < details['total']:
                        failed = [t[0] for t in details['tests'] if not t[1]]
                        value += f"\n缺失: {', '.join(failed)}"
                    report_embed.add_field(name=f"{stage_name} {status_emoji}", value=value, inline=False)
            
            # 加入 bot 狀態資訊
            report_embed.add_field(
                name="🤖 Bot 狀態",
                value=f"伺服器數: {len(self.bot.guilds)}\n"
                      f"延遲: {round(self.bot.latency * 1000)}ms\n"
                      f"Cogs 數量: {len(self.bot.cogs)}",
                inline=False
            )
            
            report_embed.set_footer(text=f"測試者: {ctx.author.display_name}")
            
            await progress_message.edit(embed=report_embed)
            
            # 發送日誌檔案
            try:
                log_file = discord.File(self.log_file, filename=self.log_file)
                await ctx.send(f"📄 詳細測試日誌:", file=log_file)
            except:
                self.log("⚠️ 無法發送日誌檔案")
            
            self.log("=" * 60)
            self.log(f"測試完成 - 整體狀態: {overall_status}")
            
        except Exception as e:
            self.log(f"❌ 測試過程發生嚴重錯誤: {e}")
            import traceback
            self.log(traceback.format_exc())
            
            error_embed = discord.Embed(
                title="❌ 測試過程發生錯誤",
                description=f"```{str(e)}```",
                color=0xff0000
            )
            await progress_message.edit(embed=error_embed)
    
    async def update_progress(self, message, stage, progress, detail=""):
        """更新進度條"""
        progress_bar = self.create_progress_bar(progress)
        embed = message.embeds[0]
        embed.description = f"**{stage}**\n{progress_bar} {progress}%\n{detail}"
        await message.edit(embed=embed)
    
    def create_progress_bar(self, progress, length=20):
        """建立進度條"""
        filled = int(length * progress / 100)
        bar = '█' * filled + '░' * (length - filled)
        return f"`{bar}`"
    
    @commands.hybrid_command(name='testlog', aliases=['查看測試日誌'])
    @commands.has_permissions(administrator=True)
    async def view_test_log(self, ctx):
        """查看最新的測試日誌"""
        try:
            # 尋找最新的測試日誌
            log_files = [f for f in os.listdir('.') if f.startswith('test_log_') and f.endswith('.txt')]
            if not log_files:
                await ctx.send("❌ 找不到任何測試日誌")
                return
            
            latest_log = max(log_files)
            with open(latest_log, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 如果內容太長，只顯示最後 1000 字元
            if len(content) > 1000:
                content = "...\n" + content[-1000:]
            
            await ctx.send(f"📄 最新測試日誌 ({latest_log}):\n```\n{content}\n```")
        except Exception as e:
            await ctx.send(f"❌ 讀取日誌失敗: {e}")

async def setup(bot):
    await bot.add_cog(TestSystemCog(bot))