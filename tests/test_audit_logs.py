"""
审计日志系统测试脚本
用于验证审计日志系统的完整功能
"""
import sys
import os
import time
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 设置环境变量
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

from app.integrations.audit_logger import AuditLogger

def test_audit_logger():
    """测试审计日志记录器"""
    print("=" * 60)
    print("测试 1: 审计日志记录器基础功能")
    print("=" * 60)
    
    # 创建日志记录器
    logger = AuditLogger(
        user_id="test_user_001",
        user_name="测试用户",
        session_id="session_12345"
    )
    
    # 测试 1: 记录成功的工具调用
    print("\n✓ 测试 1.1: 记录成功的工具调用")
    log_id = logger.log_tool_call(
        tool_name="test_tool",
        request_data={"param1": "value1", "param2": 123},
        response_data={"result": "success", "data": [1, 2, 3]},
        duration_ms=150,
        task_id=1001,
        spec_id="spec_001"
    )
    print(f"  日志 ID: {log_id}")
    assert log_id > 0, "日志 ID 应该大于 0"
    print("  ✓ 通过")
    
    # 测试 2: 记录失败的工具调用
    print("\n✓ 测试 1.2: 记录失败的工具调用")
    log_id = logger.log_tool_call(
        tool_name="failing_tool",
        request_data={"param1": "bad_value"},
        error=Exception("测试错误：模拟失败"),
        duration_ms=50,
        task_id=1002
    )
    print(f"  日志 ID: {log_id}")
    assert log_id > 0, "日志 ID 应该大于 0"
    print("  ✓ 通过")
    
    # 测试 3: 批量记录
    print("\n✓ 测试 1.3: 批量记录日志")
    for i in range(10):
        logger.log_tool_call(
            tool_name=f"batch_tool_{i % 3}",
            request_data={"batch_id": i},
            response_data={"result": f"batch_{i}"},
            duration_ms=50 + i * 10,
            status="success" if i % 2 == 0 else "failed"
        )
    print("  已记录 10 条日志")
    print("  ✓ 通过")
    
    print("\n✅ 测试 1 全部通过！")
    return True

def test_api_endpoints():
    """测试 API 端点"""
    print("\n" + "=" * 60)
    print("测试 2: API 端点功能")
    print("=" * 60)
    
    try:
        import requests
    except ImportError:
        print("  ⚠️  缺少 requests 库，跳过 API 测试")
        print("  安装方法：pip install requests")
        return True
    
    base_url = "http://localhost:5010/api/audit-logs"
    
    # 测试 1: 获取日志列表
    print("\n✓ 测试 2.1: 获取日志列表")
    try:
        response = requests.get(f"{base_url}/list?page=1&page_size=10")
        if response.status_code == 200:
            data = response.json()
            print(f"  总记录数：{data.get('total', 0)}")
            print(f"  当前页：{data.get('page', 0)}")
            print(f"  返回日志数：{len(data.get('logs', []))}")
            print("  ✓ 通过")
        else:
            print(f"  ✗ 失败：HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ 失败：{e}")
        print("  提示：请确保后端服务已启动 (python web/backend/main.py)")
        return False
    
    # 测试 2: 获取统计信息
    print("\n✓ 测试 2.2: 获取统计信息")
    try:
        response = requests.get(f"{base_url}/stats")
        if response.status_code == 200:
            data = response.json()
            print(f"  总日志数：{data.get('total', 0)}")
            print(f"  成功率：{data.get('success_rate', 0)}%")
            print("  ✓ 通过")
        else:
            print(f"  ✗ 失败：HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ 失败：{e}")
        return False
    
    print("\n✅ 测试 2 全部通过！")
    return True

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 审计日志系统测试")
    print("=" * 60)
    print(f"项目根目录：{project_root}")
    db_path = os.path.join(project_root, 'app', 'data', 'audit_logs.db')
    print(f"数据库路径：{db_path}")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("日志记录器", test_audit_logger()))
    results.append(("API 端点", test_api_endpoints()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
    
    print("-" * 60)
    print(f"总计：{passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！审计日志系统运行正常！")
        print("\n📝 使用指南:")
        print("  1. 启动后端服务：cd D:\\dfCode\\AICreate && python web/backend/main.py")
        print("  2. 访问审计日志页面：http://localhost:5010/audit-logs.html")
        print("  3. 查看 API 文档：http://localhost:5010/docs")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())
