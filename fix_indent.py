"""Fix server_settings.py indentation"""
fpath = 'cogs/server_settings.py'
with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "name='用戶面板'" in line:
        if line.startswith('        @'):
            lines[i] = '    ' + line[8:]
            print(f"Fixed indentation on line {i+1}")
        break

with open(fpath, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("Done")
