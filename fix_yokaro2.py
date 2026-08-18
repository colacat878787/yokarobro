"""Fix yokaro.py - daily restart scheduler placement and indentation"""
fpath = 'yokaro.py'
with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_until_except = False
i = 0
while i < len(lines):
    line = lines[i]
    
    # Fix: comment indentation in on_ready (line 212 area)
    if line.strip() == '# 啟動狀態輪播任務' and line.startswith('                '):
        # Fix double indentation - should be 8 spaces
        new_lines.append('        # 啟動狀態輪播任務\n')
        i += 1
        continue
    
    # Fix: the _daily_restart_scheduler was inserted inside _status_cycler's try block
    # We need to find where it starts and move it after the except block
    if 'async def _daily_restart_scheduler(self):' in line:
        # This method was incorrectly placed inside _status_cycler's try block
        # We need to:
        # 1. Close the try block properly
        # 2. Skip the incorrectly placed method
        # 3. Add it later
        
        # First, ensure the previous try block has except
        # Check if we're missing except for the try block in _status_cycler
        # Look backwards to find the try
        found_try = False
        for j in range(len(new_lines)-1, -1, -1):
            if 'try:' in new_lines[j]:
                found_try = True
                break
            if 'except' in new_lines[j] or 'async def' in new_lines[j]:
                break
        
        if found_try:
            # Add except block to close the try in _status_cycler
            new_lines.append('            except Exception as e:\n')
            new_lines.append('                print(f"⚠️ 狀態輪播錯誤: {e}")\n')
            new_lines.append('                import traceback\n')
        
        # Now skip all lines of _daily_restart_scheduler until we find the next method
        # Save it to add later
        daily_method_lines = []
        i += 1  # Skip the def line itself
        while i < len(lines):
            if lines[i].strip().startswith('async def ') or (lines[i].strip() == '' and i + 1 < len(lines) and lines[i+1].strip().startswith('async def ')):
                # Check if this is a new method at the right indentation
                if lines[i].startswith('    async def ') or (lines[i].strip() == '' and i + 1 < len(lines) and lines[i+1].startswith('    async def ')):
                    break
            daily_method_lines.append(lines[i])
            i += 1
        
        # Store the daily method for later
        daily_method = ''.join(daily_method_lines)
        
        # Add the daily method properly after the _status_cycler method
        # We'll store it and add it after the next method we hit
        # For now, let's just add it immediately after closing _status_cycler
        new_lines.append('\n')
        new_lines.append('    ' + daily_method.strip().split('\n')[0] + '\n')  # async def line
        for ml in daily_method.strip().split('\n')[1:]:
            new_lines.append(ml + '\n')
        
        continue
    
    new_lines.append(line)
    i += 1

# Fix: Add daily_restart_task initialization in on_ready
# Find the line with "print('⚠️ 狀態輪播任務已在運行中')"
content = ''.join(new_lines)
content = content.replace(
    '            print("⚠️ 狀態輪播任務已在運行中")\n\n    async def _status_cycler',
    '            print("⚠️ 狀態輪播任務已在運行中")\n\n        # 啟動每日午夜重啟排程\n        self.daily_restart_task = self.loop.create_task(self._daily_restart_scheduler())\n        print("📅 每日重啟排程已啟動")\n\n    async def _status_cycler'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

# Re-read and apply the on_ready fix
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace(
    '            print("⚠️ 狀態輪播任務已在運行中")\n\n    async def _status_cycler',
    '            print("⚠️ 狀態輪播任務已在運行中")\n\n        # 啟動每日午夜重啟排程\n        self.daily_restart_task = self.loop.create_task(self._daily_restart_scheduler())\n        print("📅 每日重啟排程已啟動")\n\n    async def _status_cycler'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ yokaro.py fixed - daily restart scheduler properly placed")
