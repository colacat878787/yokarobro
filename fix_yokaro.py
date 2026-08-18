import sys

# Fix yokaro.py - add daily midnight restart with status change
fpath = 'yokaro.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# Add datetime import if not present
if 'from datetime import datetime, timedelta' not in content and 'from datetime import datetime' not in content:
    content = content.replace(
        'import json\n',
        'import json\nfrom datetime import datetime, timedelta\n'
    )

# Daily restart scheduler method
daily_restart_code = '''
    async def _daily_restart_scheduler(self):
        """每日定時重新啟動 - 每天晚上12:00自動重啟"""
        await self.wait_until_ready()
        print("📅 每日重啟排程已啟動，將在每天晚上12:00執行")

        while not self.is_closed():
            try:
                now = datetime.now()
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                wait_seconds = (midnight - now).total_seconds()

                print(f"📅 下次重啟時間: {midnight.strftime('%Y-%m-%d %H:%M:%S')} (等待 {int(wait_seconds)} 秒)")
                await asyncio.sleep(wait_seconds)

                print("🌙 午夜到啦，準備每日重啟...")

                # 1. 將狀態改成 idle + "重啟中"
                restart_activity = discord.Activity(
                    type=discord.ActivityType.playing,
                    name="重啟中..."
                )
                await self.change_presence(status=discord.Status.idle, activity=restart_activity)
                print("🔄 狀態已改為 idle - 重啟中...")

                # 發送重啟通知
                updater = self.get_cog("AutoUpdaterCog")
                if updater:
                    for ch_id in updater.changelog_channel_ids:
                        try:
                            ch = self.get_channel(ch_id)
                            if ch:
                                embed = discord.Embed(
                                    title="🌙 每日自動重啟",
                                    description="洛洛正在進行每日維護重啟，約 30 秒後回來！",
                                    color=0xff9900
                                )
                                await ch.send(embed=embed)
                        except:
                            pass

                # 2. 重新載入所有 extensions (graceful reload)
                for ext in list(self.extensions.keys()):
                    try:
                        await self.unload_extension(ext)
                        await self.load_extension(ext)
                    except Exception as e:
                        print(f"[DailyRestart] 重載 {ext} 失敗: {e}")

                # 3. 同步指令樹
                try:
                    await self.tree.sync()
                except Exception as e:
                    print(f"[DailyRestart] 指令同步失敗: {e}")

                # 4. 將狀態改回來 (online + 歌詞)
                self.status_index = 0
                status, message = self.status_messages[0]
                activity = discord.Activity(
                    type=discord.ActivityType.playing,
                    name=message
                )
                await self.change_presence(status=status, activity=activity)
                print(f"✅ 重啟完成！狀態恢復: {status} - {message}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ 每日重啟排程錯誤: {e}")
                await asyncio.sleep(60)

'''

# Insert daily restart method after _status_cycler's last line
content = content.replace(
    '                await asyncio.sleep(10)',
    '                await asyncio.sleep(10)' + daily_restart_code
)

# Start the daily restart scheduler in on_ready
content = content.replace(
    "self.status_task = self.loop.create_task(self._status_cycler())",
    "self.status_task = self.loop.create_task(self._status_cycler())\n        self.daily_restart_task = self.loop.create_task(self._daily_restart_scheduler())"
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ yokaro.py: added daily midnight restart with status change')
print('   - Status: lyrics -> idle (restarting) -> online (back to lyrics)')
print('   - Graceful reload (no hard exit, no music/AI interruption)')
