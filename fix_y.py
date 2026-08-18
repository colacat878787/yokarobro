"""Fix yokaro.py - daily restart scheduler"""
fpath = 'yokaro.py'
with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # 1. Add datetime import after 'import json'
    if line == 'import json\n':
        new_lines.append(line)
        new_lines.append('from datetime import datetime, timedelta\n')
        i += 1
        continue
    
    # 2. Add daily_restart_task after status_task else block
    if line == '            print("⚠️ 狀態輪播任務已在運行中")\n':
        new_lines.append(line)
        new_lines.append('\n')
        new_lines.append('        # 啟動每日午夜重啟排程\n')
        new_lines.append('        self.daily_restart_task = self.loop.create_task(self._daily_restart_scheduler())\n')
        new_lines.append('        print("📅 每日重啟排程已啟動")\n')
        i += 1
        continue
    
    # 3. Insert _daily_restart_scheduler after _status_cycler
    if line == '        print("🛑 狀態輪播任務已停止")\n':
        new_lines.append(line)
