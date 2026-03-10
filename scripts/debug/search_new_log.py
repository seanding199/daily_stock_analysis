import os
import sys

# Windows 环境设置 UTF-8 编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

log_file = r"C:\Users\sean.ding\.cursor\projects\e-code-project-Stock\terminals\618937.txt"

if not os.path.exists(log_file):
    print(f"日志文件不存在: {log_file}")
    exit(1)

with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# 查找包含关键词的行
keywords = ['LLM返回', '分析完成', 'OpenAI', 'deepseek', '评分', 'API响应']
matches = []

for i, line in enumerate(lines):
    for keyword in keywords:
        if keyword in line:
            matches.append((i+1, line.strip()))
            break

# 打印最后20个匹配
print(f"找到 {len(matches)} 个匹配")
print(f"日志文件行数: {len(lines)}")
print("\n最近20个匹配:")
for line_num, line in matches[-20:]:
    print(f"{line_num}: {line[:200]}")
