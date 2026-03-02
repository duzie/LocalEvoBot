import os
import ast
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool

def analyze_functions(file_path: str) -> list:
    """分析 Python 文件中的函数和类方法"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        source = f.read()
    
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
        
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
                try:
                    returns = ast.unparse(node.returns)
                except:
                    pass
            
            functions.append({
                'name': node.name,
                'args': args,
                'docstring': docstring,
                'returns': returns,
                'lineno': node.lineno
            })
    
    return functions

def analyze_imports(file_path: str) -> list:
    """分析文件的导入语句"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        source = f.read()
    
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
        
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
            arg_placeholders.append('None')
    
    # 生成测试代码
    test_code = f'''
def {test_name}():
    """测试 {func_name} 函数"""
    # TODO: 设置测试输入
'''
    
    if args:
        test_code += f"    # {func_name}({', '.join(args)})\n"
        test_code += f"    # result = {func_name}({', '.join(arg_placeholders)})\n"
    else:
        test_code += f"    # result = {func_name}()\n"
    
    test_code += '''    # TODO: 添加断言
    # assert result is not None
    pass
'''
    
    # 生成边界情况测试
    if include_edge_cases and args:
        test_code += f'''
def {test_name}_edge_cases():
    """测试 {func_name} 函数的边界情况"""
    # TODO: 测试 None, 空值, 极端值等
    pass
'''
    
    return test_code

@tool
def generate_pytest_tests(
    file_path: str,
    output_path: Optional[str] = None,
    coverage_target: int = 80,
    include_edge_cases: bool = True
) -> Dict[str, Any]:
    """
    根据 Python 代码文件自动生成 pytest 测试用例骨架。
    
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
            return {'ok': False, 'error': f'文件不存在：{file_path}'}
        
        # 验证是 Python 文件
        if not file_path.endswith('.py'):
            return {'ok': False, 'error': f'不是 Python 文件：{file_path}'}
        
        # 确定输出路径
        if output_path is None:
            file_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            test_file_name = f"test_{file_name}"
            output_path = os.path.join(file_dir, test_file_name)
        
        # 分析源文件
        functions = analyze_functions(file_path)
        
        if not functions:
            return {'ok': False, 'error': '未找到可测试的函数'}
        
        # 生成测试文件内容
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        
        test_content = f'''"""
自动生成的 pytest 测试文件
源文件：{file_path}
目标覆盖率：{coverage_target}%
生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
import pytest
import sys
import os

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
        
        # 写入测试文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        return {
            'ok': True,
            'message': f'成功生成测试文件: {output_path}',
            'output_path': output_path,
            'functions_tested': len(test_functions)
        }
    
    except Exception as e:
        return {'ok': False, 'error': str(e)}
