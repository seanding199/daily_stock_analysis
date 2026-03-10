import os
import sys

# Windows 环境设置 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

log_file = r"C:\Users\sean.ding\.cursor\projects\e-code-project-Stock\terminals\688895.txt"

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# 查找趋势分析相关的行
keywords = ['趋势分析', 'trend', 'StockTrendAnalyzer', 'analyze']
matches = []

for i, line in enumerate(lines):
    for keyword in keywords:
        if keyword in line:
            matches.append((i+1, line.strip()))
            break

# 打印所有匹配
print(f"找到 {len(matches)} 个匹配")
print("\n所有匹配:")
for line_num, line in matches:
    print(f"{line_num}: {line[:250]}")
