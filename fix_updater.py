import sys

# Fix updater.py - replace os._exit(0) with graceful reload
fpath = 'cogs/updater.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace os._exit(0) in auto-update with graceful reload
old_auto = '''            # 在重啟前發送更新通知到頻道
            await self._notify_changelog(local_hash, remote_hash)

            # 立即重啟，不等待
            os._exit(0)'''
new_auto = '''            # 在重啟前發送更新通知到頻道
            await self._notify_changelog(local_hash, remote_hash)

            # 優雅重啟：重新載入所有 extensions 而非強制退出
            # 這樣不會中斷正在播放的音樂或 AI 對話
            await self._graceful_reload()'''
content = content.replace(old_auto, new_auto)

# Replace os._exit(0) in manual update
old_manual = '''            await msg.edit(content="✅ 同步完成！洛洛馬上重啟...")
            await self._notify_changelog(local_hash, remote_hash)
            os._exit(0)'''
new_manual = '''            await msg.edit(content="✅ 同步完成！洛洛正在優雅重啟模組...")
            await self._notify_changelog(local_hash, remote_hash)
            await self._graceful_reload()'''
content = content.replace(old_manual, new_manual)

# Add _graceful_reload method before before_check
graceful_method = '''
    async def _graceful_reload(self):
        """優雅重啟：重新載入所有 extensions，但不強制退出過程"""
        changelog_ids = self.changelog_channel_ids
        for ch_id in changelog_ids:
            try:
                ch = self.bot.get_channel(ch_id)
                if ch:
                    embed = discord.Embed(
                        title="🔄 優雅重啟中",
                        description="洛洛正在重新載入模組，期間音樂播放與 AI 對話不受影響！",
                        color=0xf1c40f
                    )
                    await ch.send(embed=embed)
            except:
                pass

        extensions = list(self.bot.extensions.keys())
        reloaded = []
        failed = []
        for ext in extensions:
            try:
                await self.bot.unload_extension(ext)
                await self.bot.load_extension(ext)
                reloaded.append(ext)
            except Exception as e:
                failed.append(f"{ext}: {e}")

        try:
            await self.bot.tree.sync()
        except Exception as e:
            print(f"[GracefulReload] 指令同步失敗: {e}")

        for ch_id in changelog_ids:
            try:
                ch = self.bot.get_channel(ch_id)
                if ch:
                    embed = discord.Embed(
                        title="✅ 重啟完成",
                        description=f"模組重載完成！({len(reloaded)}/{len(extensions)} 成功)\\n音樂播放與 AI 對話恢復正常。",
                        color=0x2ecc71
                    )
                    await ch.send(embed=embed)
            except:
                pass

        print(f"[GracefulReload] 重載完成: {len(reloaded)}/{len(extensions)} 成功")
        if failed:
            print(f"[GracefulReload] 失敗: {failed}")

'''

content = content.replace(
    '    @check_update.before_loop',
    graceful_method + '    @check_update.before_loop'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ updater.py: replaced os._exit(0) with graceful reload')
print('   - Auto-update now uses _graceful_reload() instead of os._exit(0)')
print('   - Manual update now uses _graceful_reload() instead of os._exit(0)')
print('   - Added _graceful_reload() method')
