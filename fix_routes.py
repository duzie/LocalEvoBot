import re

# 读取文件
with open(r'D:/dfCode/AICreate/web/backend/routers/audit_logs.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到路由定义的行号
log_id_line = None
stats_line = None
clear_line = None

for i, line in enumerate(lines):
    if '@router.get("/{log_id}"' in line:
        log_id_line = i
    elif '@router.get("/stats")' in line:
        stats_line = i
    elif '@router.delete("/clear")' in line:
        clear_line = i

print(f"log_id_line: {log_id_line}")
print(f"stats_line: {stats_line}")
print(f"clear_line: {clear_line}")

if log_id_line and stats_line and log_id_line < stats_line:
    # 提取 log_id 函数（从@router.get 到下一个@router 之前）
    log_id_start = log_id_line
    log_id_end = stats_line
    
    # 提取 stats 函数
    stats_start = stats_line
    stats_end = clear_line
    
    # 重新组织：stats 在前，log_id 在后
    new_lines = lines[:log_id_start] + lines[stats_start:stats_end] + lines[log_id_start:log_id_end] + lines[stats_end:]
    
    # 写入文件
    with open(r'D:/dfCode/AICreate/web/backend/routers/audit_logs.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("路由顺序已调整！")
else:
    print("不需要调整或找不到路由")
