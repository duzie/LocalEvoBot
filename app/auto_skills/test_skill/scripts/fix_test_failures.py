from langchain_core.tools import tool
"""
分析失败的测试并尝试修复代码或测试。

Args:
    test_output: pytest 失败输出
    source_file: 源代码文件路径
    test_file: 测试文件路径
    auto_fix: 是否自动修复（默认 True）

Returns:
    包含修复结果的字典
"""
import os
import re
import ast
from pathlib import Path


@tool
def parse_failure_info(test_output: str) -> dict:
    """解析 pytest 失败输出，提取关键信息"""
    failures = []
    
    lines = test_output.split('\n')
    current_failure = None
    
    for i, line in enumerate(lines):
        # 检测失败的测试
        if 'FAILED' in line and '::test_' in line:
            if current_failure:
                failures.append(current_failure)
            
            # 提取测试名称
            match = re.search(r'test_(\w+)\.py::(test_\w+)', line)
            if match:
                test_file = match.group(1)
                test_func = match.group(2)
            else:
                test_file = 'unknown'
                test_func = 'unknown'
            
            current_failure = {
                'test_file': test_file,
                'test_function': test_func,
                'error_type': 'Unknown',
                'error_message': '',
                'location': None,
                'expected': None,
                'actual': None
            }
        
        # 提取错误类型
        if current_failure and ('AssertionError' in line or 'Error' in line):
            current_failure['error_type'] = line.strip().split(':')[0]
        
        # 提取错误消息
        if current_failure and 'AssertionError' in line:
            # 尝试提取 expected vs actual
            for j in range(i, min(i+10, len(lines))):
                if 'assert' in lines[j].lower():
                    current_failure['error_message'] = lines[j].strip()
                if 'Expected:' in lines[j] or 'expected' in lines[j].lower():
                    current_failure['expected'] = lines[j].strip()
                if 'Actual:' in lines[j] or 'got' in lines[j].lower():
                    current_failure['actual'] = lines[j].strip()
        
        # 提取位置信息
        if current_failure and 'test_' in line and '.py:' in line:
            match = re.search(r'(test_\w+\.py):(\d+)', line)
            if match:
                current_failure['location'] = {
                    'file': match.group(1),
                    'line': int(match.group(2))
                }
    
    if current_failure:
        failures.append(current_failure)
    
    return {
        'total_failures': len(failures),
        'failures': failures
    }


def suggest_fix(failure: dict, source_file: str, test_file: str) -> dict:
    """根据失败信息提供修复建议"""
    suggestions = []
    
    error_type = failure.get('error_type', '')
    error_msg = failure.get('error_message', '')
    expected = failure.get('expected')
    actual = failure.get('actual')
    
    # 类型错误
    if 'AssertionError' in error_type or 'assert' in error_msg.lower():
        if expected and actual:
            suggestions.append({
                'type': 'assertion_mismatch',
                'description': '断言不匹配',
                'fix': f'检查预期值 {expected} 和实际值 {actual} 的差异',
                'action': 'review_test_or_code'
            })
        else:
            suggestions.append({
                'type': 'assertion_failed',
                'description': '断言失败',
                'fix': '检查测试逻辑或被测函数的返回值',
                'action': 'review_assertion'
            })
    
    # 属性错误
    if 'AttributeError' in error_type:
        match = re.search(r"'(\w+)' object has no attribute '(\w+)'", error_msg)
        if match:
            obj_type = match.group(1)
            missing_attr = match.group(2)
            suggestions.append({
                'type': 'missing_attribute',
                'description': f'对象 {obj_type} 缺少属性 {missing_attr}',
                'fix': f'在代码中添加 {missing_attr} 属性或修正测试中的属性名',
                'action': 'add_attribute_or_fix_test'
            })
    
    # 类型错误
    if 'TypeError' in error_type:
        suggestions.append({
            'type': 'type_mismatch',
            'description': '类型不匹配',
            'fix': '检查函数参数类型和返回值类型',
            'action': 'check_types'
        })
    
    # 值错误
    if 'ValueError' in error_type:
        suggestions.append({
            'type': 'invalid_value',
            'description': '无效的值',
            'fix': '检查输入值是否符合函数要求',
            'action': 'validate_input'
        })
    
    # 未捕获的异常
    if 'raises' in error_msg.lower() and 'did not raise' in error_msg.lower():
        suggestions.append({
            'type': 'expected_exception_not_raised',
            'description': '预期异常未抛出',
            'fix': '检查测试用例是否应该抛出异常，或修改代码逻辑',
            'action': 'review_exception_handling'
        })
    
    return {
        'failure': failure,
        'suggestions': suggestions,
        'auto_fixable': len(suggestions) > 0 and any(s['action'] in ['add_attribute_or_fix_test', 'validate_input'] for s in suggestions)
    }


def fix_test_failures(
    test_output: str,
    source_file: str = None,
    test_file: str = None,
    auto_fix: bool = True
) -> dict:
    """
    分析失败的测试并尝试修复代码或测试
    
    Args:
        test_output: pytest 失败输出
        source_file: 源代码文件路径
        test_file: 测试文件路径
        auto_fix: 是否自动修复
    
    Returns:
        包含修复结果的字典
    """
    try:
        # 解析失败信息
        failure_info = parse_failure_info(test_output)
        
        if failure_info['total_failures'] == 0:
            return {
                'ok': True,
                'message': '未检测到失败的测试',
                'total_failures': 0
            }
        
        # 分析每个失败并提供建议
        analysis_results = []
        auto_fixes_applied = []
        
        for failure in failure_info['failures']:
            # 确定实际的文件路径
            actual_source = source_file
            actual_test = test_file
            
            if not actual_source and failure.get('location'):
                # 尝试从失败位置推断源文件
                loc_file = failure['location'].get('file', '')
                if loc_file.startswith('test_'):
                    actual_test = loc_file
            
            analysis = suggest_fix(failure, actual_source or '', actual_test or '')
            analysis_results.append(analysis)
            
            # 自动修复（如果启用且可行）
            if auto_fix and analysis['auto_fixable']:
                for suggestion in analysis['suggestions']:
                    if suggestion['action'] == 'add_attribute_or_fix_test':
                        # 这里可以添加实际的代码修复逻辑
                        auto_fixes_applied.append({
                            'failure': failure['test_function'],
                            'action': 'suggested',
                            'note': '需要人工确认修复方案'
                        })
        
        # 生成总结
        total_suggestions = sum(len(r['suggestions']) for r in analysis_results)
        auto_fix_count = len(auto_fixes_applied)
        
        return {
            'ok': False,  # 有失败
            'total_failures': failure_info['total_failures'],
            'total_suggestions': total_suggestions,
            'auto_fixes_applied': auto_fix_count,
            'analysis': analysis_results,
            'summary': f'分析 {failure_info["total_failures"]} 个失败，提供 {total_suggestions} 条建议，自动修复 {auto_fix_count} 个',
            'next_steps': [
                '查看 analysis 中的详细建议',
                '手动修复代码或测试',
                '重新运行测试验证修复'
            ]
        }
    
    except Exception as e:
        return {
            'ok': False,
            'error': str(e),
            'traceback': __import__('traceback').format_exc()
        }


if __name__ == '__main__':
    # 测试示例
    sample_output = """
    test_example.py::test_addition FAILED
    AssertionError: assert 3 == 4
    Expected: 4
    Actual: 3
    """
    result = fix_test_failures(sample_output)
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))