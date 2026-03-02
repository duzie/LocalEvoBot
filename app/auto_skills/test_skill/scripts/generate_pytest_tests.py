from langchain_core.tools import tool
"""
根据 Python 代码文件自动生成 pytest 测试用例。

Args:
    file_path: 要测试的 Python 文件路径
    output_path: 测试文件保存路径，默认在同目录创建 test_xxx.py
    coverage_target: 目标覆盖率百分比（默认 80）
    include_edge_cases: 是否包含边界情况测试（默认 True）

Returns:
    包含生成结果的字典
"""
import os
import ast
import re
from pathlib import Path


@tool
def analyze_functions(file_path: str) -> list:
    """分析 Python 文件中的函数和类方法"""
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    tree = ast.parse(source)
    functions = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # 获取函数参数
            args = []
            for arg in node.args.args:
                if arg.arg != 'self':  # 跳过 self
                    args.append(arg.arg)
            
            # 获取函数文档字符串
            docstring = ast.get_docstring(node) or ""
            
            # 获取返回类型注解
            returns = None
            if node.returns:
                returns = ast.unparse(node.returns)
            
            functions.append({
                'name': node.name,
                'args': args,
                'docstring': docstring,
                'returns': returns,
                'lineno': node.lineno,
                'is_method': any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) if hasattr(parent, 'body') and node in parent.body)
            })
    
    return functions


def analyze_imports(file_path: str) -> list:
    """分析文件的导入语句"""
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    
    tree = ast.parse(source)
    imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"from {module} import {alias.name}")
    
    return imports


def generate_test_template(func_info: dict, module_name: str, include_edge_cases: bool) -> str:
    """为单个函数生成测试模板"""
    func_name = func_info['name']
    args = func_info['args']
    docstring = func_info['docstring']
    
    # 生成测试函数名
    test_name = f"test_{func_name}"
    
    # 生成参数占位符
    arg_placeholders = []
    for arg in args:
        # 根据参数名推测类型并生成示例值
        if 'path' in arg.lower() or 'file' in arg.lower():
            arg_placeholders.append(f'"{arg}_test_value"')
        elif 'count' in arg.lower() or 'num' in arg.lower() or 'size' in arg.lower():
            arg_placeholders.append('0')
        elif 'name' in arg.lower() or 'title' in arg.lower():
            arg_placeholders.append('"test_string"')
        elif 'flag' in arg.lower() or 'enable' in arg.lower():
            arg_placeholders.append('True')
        else:
            arg_placeholders.append('None  # TODO: 设置合适的测试值')
    
    # 生成测试代码
    test_code = f'''
def {test_name}():
    """测试 {func_name} 函数"""
    # TODO: 设置测试输入
'''
    
    if args:
        test_code += f"    args = {', '.join(arg_placeholders)}\n"
        test_code += f"    result = {func_name}({', '.join(args)})\n"
    else:
        test_code += f"    result = {func_name}()\n"
    
    test_code += '''    # TODO: 添加断言
    # assert result is not None
    # assert isinstance(result, expected_type)
'''
    
    # 生成边界情况测试
    if include_edge_cases and args:
        test_code += f'''

def {test_name}_edge_cases():
    """测试 {func_name} 函数的边界情况"""
    # 边界情况 1: 空值/None
    # TODO: 测试 None 输入
    
    # 边界情况 2: 空字符串/空列表
    # TODO: 测试空输入
    
    # 边界情况 3: 极大值/极小值
    # TODO: 测试极端值
    
    # 边界情况 4: 特殊字符
    # TODO: 测试特殊字符输入
'''
    
    return test_code


def generate_pytest_tests(
    file_path: str,
    output_path: str = None,
    coverage_target: int = 80,
    include_edge_cases: bool = True
) -> dict:
    """
    根据 Python 代码文件自动生成 pytest 测试用例
    
    Args:
        file_path: 要测试的 Python 文件路径
        output_path: 测试文件保存路径，默认在同目录创建 test_xxx.py
        coverage_target: 目标覆盖率百分比
        include_edge_cases: 是否包含边界情况测试
    
    Returns:
        包含生成结果的字典
    """
    try:
        # 验证文件存在
        if not os.path.exists(file_path):
            return {
                'ok': False,
                'error': f'文件不存在：{file_path}'
            }
        
        # 验证是 Python 文件
        if not file_path.endswith('.py'):
            return {
                'ok': False,
                'error': f'不是 Python 文件：{file_path}'
            }
        
        # 确定输出路径
        if output_path is None:
            file_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            test_file_name = f"test_{file_name}"
            output_path = os.path.join(file_dir, test_file_name)
        
        # 分析源文件
        functions = analyze_functions(file_path)
        imports = analyze_imports(file_path)
        
        if not functions:
            return {
                'ok': False,
                'error': '未找到可测试的函数',
                'functions_found': 0
            }
        
        # 生成测试文件内容
        module_name = os.path.basename(file_path).replace('.py', '')
        
        test_content = f'''"""
自动生成的 pytest 测试文件
源文件：{file_path}
目标覆盖率：{coverage_target}%
生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
import pytest
import sys
import os

# 添加源文件目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath("{file_path}")))

# 导入被测试模块
from {module_name} import *

'''
        
        # 为每个函数生成测试
        test_functions = []
        for func in functions:
            if not func['name'].startswith('_'):  # 跳过私有函数
                test_code = generate_test_template(func, module_name, include_edge_cases)
                test_functions.append(test_code)
        
        test_content += '\n'.join(test_functions)
        
        # 添加使用说明
        test_content += f'''

# ============================================
# 使用说明:
# 1. 替换 TODO 注释中的占位符为实际测试值
# 2. 添加合适的断言
# 3. 运行测试：pytest {output_path} -v
# 4. 检查覆盖率：pytest {output_path} --cov={module_name} --cov-report=html
# ============================================
'''
        
        # 写入测试文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        return {
            'ok': True,
            'message': f'成功生成测试文件',
            'output_path': output_path,
            'functions_tested': len(test_functions),
            'coverage_target': coverage_target,
            'next_steps': [
                f'1. 编辑 {output_path} 填充测试逻辑',
                f'2. 运行测试：pytest {output_path} -v',
                f'3. 检查覆盖率：pytest {output_path} --cov={module_name}'
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
    import sys
    if len(sys.argv) > 1:
        result = generate_pytest_tests(sys.argv[1])
        print(result)