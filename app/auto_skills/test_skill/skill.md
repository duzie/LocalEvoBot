# Skill

## Name
test_skill

## Version
1.0.0

## Description
Python 代码测试技能：支持 pytest 测试用例生成、执行、覆盖率检查和失败修复

## Entry
app.auto_skills.test_skill.scripts

## Tools
- generate_pytest_tests
- run_pytest
- check_coverage
- fix_test_failures

## Platforms
- Windows

## References
- references/usage.md


## Tool Details

### generate_pytest_tests
根据 Python 代码文件自动生成 pytest 测试用例模板。
- **参数**: file_path (源文件), output_path (输出路径), coverage_target (目标覆盖率), include_edge_cases (包含边界测试)
- **返回**: 生成的测试文件路径、测试的函数数量、下一步建议
- **示例**: `generate_pytest_tests("app/utils.py", coverage_target=80)`

### run_pytest
执行 pytest 测试并返回详细结果。
- **参数**: test_path (测试文件/目录), verbose (详细输出), stop_on_failure (失败即停), coverage (生成覆盖率)
- **返回**: 通过/失败数量、覆盖率百分比、失败详情、测试输出
- **示例**: `run_pytest("tests/test_utils.py", coverage=True)`

### check_coverage
检查测试覆盖率并生成报告。
- **参数**: source_dir (源码目录), coverage_file (覆盖数据文件), report_format (text/html/json), min_coverage (最低要求)
- **返回**: 覆盖率百分比、是否达标、详细报告、改进建议
- **示例**: `check_coverage("app", min_coverage=80, report_format="html")`

### fix_test_failures
分析失败的测试并提供修复建议。
- **参数**: test_output (pytest 输出), source_file (源文件), test_file (测试文件), auto_fix (自动修复)
- **返回**: 失败分析、修复建议、自动修复结果
- **示例**: `fix_test_failures(test_output, source_file="app/utils.py")`

## Workflow Example

```python
# 1. 生成测试
result = generate_pytest_tests("app/utils.py")

# 2. 编辑测试文件填充逻辑 (人工)

# 3. 运行测试
test_result = run_pytest("tests/test_utils.py", coverage=True)

# 4. 检查覆盖率
cov_result = check_coverage("app", min_coverage=80)

# 5. 如有失败，分析并修复
if not test_result['ok']:
    fix_result = fix_test_failures(test_result['output'])
```

## Dependencies
- pytest
- pytest-cov
- pytest-json-report
- coverage

## Installation
```bash
pip install pytest pytest-cov pytest-json-report coverage
```

## Limitations
- 当前仅支持 Python (pytest)
- 自动生成的测试需要人工填充断言逻辑
- 自动修复功能有限，主要提供建议
