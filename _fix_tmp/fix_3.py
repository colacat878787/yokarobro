"""Fix 3-5: hybrid_group and alias fixes"""
import os
os.chdir(r'D:\win11\桌點\程式作品\\yokaro')

# Fix 3: reaction_roles.py
fpath = r'cogs\reaction_roles.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace(
    '@commands.hybrid_command(name="reactionrole", aliases=["rr", "反應角色"])',
    '@commands.hybrid_group(name="reactionrole", aliases=["rr", "反應角色"], invoke_without_command=True)'
)
with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ reaction_roles.py: hybrid_command -> hybrid_group')

# Fix 4: reminder.py
fpath = r'cogs\reminder.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace(
    '@commands.hybrid_command(name="remindme", aliases=["提醒", "reminder"])',
    '@commands.hybrid_group(name="remindme", aliases=["提醒", "reminder"], invoke_without_command=True)'
)
with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ reminder.py: hybrid_command -> hybrid_group')

# Fix 5: auto_role.py - remove duplicate alias "autorole"
fpath = r'cogs\auto_role.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace(
    'aliases=["自動身分組", "autorole"]',
    'aliases=["自動身分組", "ar"]'
)
with open(fpath, 'w', encoding='utf-8') as f:
    f.write(content)
print('✅ auto_role.py: removed duplicate autorole alias')
