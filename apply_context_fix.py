"""
Main.py 上下文修复补丁

修复内容：
1. 添加 transcript 导入
2. 修改历史记录加载
3. 修改消息保存
"""

import os

main_py_path = r"D:\localevobot\langchain\main.py"

print(f"正在修改：{main_py_path}")

with open(main_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加 import
if "from app.context.transcript_manager import" not in content:
    old_import = "from app.agent import create_agent_executor, create_llm"
    new_import = """from app.agent import create_agent_executor, create_llm
from app.context.transcript_manager import get_session_manager"""
    content = content.replace(old_import, new_import)
    print("✓ 添加 import")

# 2. 修改历史记录加载
old_init = """    # 初始化历史记录
    try:
        chat_history = _load_short_term_messages(project_id, user_id, limit=60)
        print(f">>> 系统：已加载 {len(chat_history)} 条历史记录")
    except Exception as e:
        print(f">>> 系统：加载历史记录失败：{e}")
        chat_history = []"""

new_init = """    # 初始化历史记录 - 使用新的 transcript 系统
    try:
        transcript = get_session_manager().get_or_create_session(f"{project_id}_{user_id}")
        chat_history = transcript.to_langchain_format(limit=60)
        print(f">>> 系统：[Transcript] 已加载 {len(transcript.messages)} 条历史记录")
    except Exception as e:
        print(f">>> 系统：加载 transcript 失败：{e}，使用空历史")
        transcript = get_session_manager().get_or_create_session(f"{project_id}_{user_id}")
        chat_history = []"""

if old_init in content:
    content = content.replace(old_init, new_init)
    print("✓ 修改历史记录初始化")
else:
    print("⚠ 未找到历史记录初始化代码")

# 3. 修改用户消息保存
old_save = """_add_short_term_message("user", user_input, project_id, user_id)"""
new_save = """# 保存到 transcript
                transcript.add_user_message(user_input)
                # 同时保存到 SQLite（向后兼容）
                _add_short_term_message("user", user_input, project_id, user_id)"""

if old_save in content:
    content = content.replace(old_save, new_save)
    print("✓ 修改用户消息保存")
else:
    print("⚠ 未找到用户消息保存代码")

# 4. 修改助手消息保存
old_assistant = """_add_short_term_message("assistant", stored_output, project_id, user_id)"""
new_assistant = """# 保存到 transcript
                transcript.add_assistant_message(stored_output)
                # 同时保存到 SQLite（向后兼容）
                _add_short_term_message("assistant", stored_output, project_id, user_id)"""

if old_assistant in content:
    content = content.replace(old_assistant, new_assistant)
    print("✓ 修改助手消息保存")
else:
    print("⚠ 未找到助手消息保存代码")

# 保存
with open(main_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ 补丁应用完成！")
print("\n⚠️ 请重启 main.py 测试")
