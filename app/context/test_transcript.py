"""测试上下文管理器"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from context.transcript_manager import get_session_manager

print("测试 Transcript Manager...")

manager = get_session_manager()
transcript = manager.get_or_create_session("test_session")

print("1. 添加测试消息...")
transcript.add_user_message("帮我看这个项目")
transcript.add_assistant_message(
    "好的，我来读取文件",
    tool_calls=[{
        "id": "tc_123",
        "name": "read_document",
        "arguments": {"path": "x:/xx.py"}
    }]
)
transcript.add_tool_result("文件内容...", tool_call_id="tc_123")
transcript.add_assistant_message("我已经读取了文件...")

print("2. 验证消息...")
messages = transcript.get_messages()
print(f"   总消息数：{len(messages)}")

for i, msg in enumerate(messages):
    role = msg.get("role")
    has_tool_calls = "tool_calls" in msg
    has_tool_id = "tool_call_id" in msg
    print(f"   [{i}] {role}: tc={has_tool_calls}, tid={has_tool_id}")

print("3. 转换为 LangChain 格式...")
lc_messages = transcript.to_langchain_format()
print(f"   LangChain 消息数：{len(lc_messages)}")

for i, msg in enumerate(lc_messages):
    role = msg.get("role")
    has_tool_calls = "tool_calls" in msg
    has_tool_id = "tool_call_id" in msg
    print(f"   [{i}] {role}: tc={has_tool_calls}, tid={has_tool_id}")

print("4. 测试会话恢复...")
transcript2 = manager.get_or_create_session("test_session")
messages2 = transcript2.get_messages()
print(f"   恢复后消息数：{len(messages2)}")

if len(messages2) == len(messages):
    print("   ✅ 会话恢复成功！")
else:
    print("   ❌ 会话恢复失败")

print("\n✅ 测试完成！")
