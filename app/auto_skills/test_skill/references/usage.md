from langchain_core.tools import tool
# test_skill 使用指南

## 概述

`test_skill` 提供完整的 Python 测试工作流支持，包括：
- 测试用例自动生成
- 测试执行与结果分析
- 覆盖率检查与报告
- 失败测试分析与修复建议

## 快速开始

### 1. 安装依赖

```bash
pip install pytest pytest-cov pytest-json-report coverage
```

### 2. 生成测试用例

```python
from app.auto_skills.test_skill.scripts.generate_pytest_tests import generate_pytest_tests

# 为 utils.py 生成测试
result = generate_pytest_tests(
    file_path="app/utils.py",
    coverage_target=80,
    include_edge_cases=True
)

print(result['output_path'])  # 输出：app/test_utils.py
```

### 3. 编辑测试文件

生成的测试文件包含 TODO 注释，需要人工填充：

```python
# test_utils.py (自动生成，需编辑)
@tool
def test_add():
    """测试 add 函数"""
    # TODO: 设置测试输入
    result = add(2, 3)
    # TODO: 添加断言
    assert result == 5
```

### 4. 运行测试

```python
from app.auto_skills.test_skill.scripts.run_pytest import run_pytest

result = run_pytest(
    test_path="app/test_utils.py",
    verbose=True,
    coverage=True
)

print(result['summary'])  # 通过：5, 失败：0, 覆盖率：85.2%
```

### 5. 检查覆盖率

```python
from app.auto_skills.test_skill.scripts.check_coverage import check_coverage

result = check_coverage(
    source_dir="app",
    min_coverage=80,
    report_format="html"  # 生成 HTML 报告
)

print(result['summary'])  # 覆盖率：85.2% (要求：80%) - ✓ 达标
```

### 6. 修复失败测试

```python
from app.auto_skills.test_skill.scripts.fix_test_failures import fix_test_failures

if not test_result['ok']:
    fix_result = fix_test_failures(
        test_output=test_result['output'],
        source_file="app/utils.py"
    )
    
    for analysis in fix_result['analysis']:
        print(f"失败测试：{analysis['failure']['test_function']}")
        for suggestion in analysis['suggestions']:
            print(f"  建议：{suggestion['fix']}")
```

## 完整工作流示例

```python
from app.auto_skills.test_skill.scripts import (
    generate_pytest_tests,
    run_pytest,
    check_coverage,
    fix_test_failures
)

# 步骤 1: 生成测试
gen_result = generate_pytest_tests("app/calculator.py")
print(f"生成测试文件：{gen_result['output_path']}")

# 步骤 2: 人工编辑测试文件 (填充断言)
# ... 手动编辑 test_calculator.py ...

# 步骤 3: 运行测试
test_result = run_pytest("app/test_calculator.py", coverage=True)
print(f"测试结果：{test_result['summary']}")

# 步骤 4: 检查覆盖率
cov_result = check_coverage("app", min_coverage=80)
print(f"覆盖率：{cov_result['summary']}")

# 步骤 5: 如有失败，分析修复
if not test_result['ok']:
    fix_result = fix_test_failures(test_result['output'])
    print(f"修复建议：{fix_result['summary']}")
```

## 最佳实践

### 测试命名规范
- 测试文件：`test_<module>.py`
- 测试函数：`test_<function>[_<scenario>]()`
- 示例：`test_add()`, `test_add_negative_numbers()`

### 测试覆盖范围
1. **正常情况**: 标准输入输出
2. **边界情况**: 空值、极大值、极小值
3. **异常情况**: 无效输入、异常抛出
4. **边缘情况**: 特殊字符、Unicode、None

### 断言建议
```python
# 好的断言
assert result == expected_value
assert isinstance(result, expected_type)
assert len(result) > 0
with pytest.raises(ValueError):
    function(invalid_input)

# 避免的断言
assert result  # 太模糊
assert True    # 无意义
```

## 常见问题

### Q: 生成的测试无法运行？
A: 检查是否已填充 TODO 部分的测试逻辑和断言。

### Q: 覆盖率不达标？
A: 运行 `pytest --cov --cov-report=term-missing` 查看未覆盖的行，针对性添加测试。

### Q: 如何处理依赖外部资源的测试？
A: 使用 `unittest.mock` 或 `pytest-mock` 进行 mocking：
```python
from unittest.mock import patch

@patch('module.external_api')
def test_with_mock(mock_api):
    mock_api.return_value = {'data': 'test'}
    # ... 测试逻辑
```

### Q: 并行执行测试？
A: 安装 `pytest-xdist` 并使用 `-n auto` 参数：
```bash
pytest -n auto --cov
```

## 进阶用法

### 参数化测试
```python
import pytest

@pytest.mark.parametrize("input,expected", [
    (2, 4),
    (3, 9),
    (4, 16),
])
def test_square(input, expected):
    assert square(input) == expected
```

### 夹具 (Fixture)
```python
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):
    assert sample_data["key"] == "value"
```

### 跳过测试
```python
@pytest.mark.skip(reason="暂未实现")
def test_future_feature():
    pass

@pytest.mark.skipif(sys.platform == "win32", reason="仅 Linux")
def test_linux_only():
    pass
```

## 相关文件
- `scripts/generate_pytest_tests.py` - 测试生成
- `scripts/run_pytest.py` - 测试执行
- `scripts/check_coverage.py` - 覆盖率检查
- `scripts/fix_test_failures.py` - 失败分析