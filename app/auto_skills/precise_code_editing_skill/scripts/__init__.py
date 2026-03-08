"""
精准代码编辑技能 - 工具集合
支持 Python 和 JavaScript (ES6+) 的精确代码修改
"""

from .find_code_block import find_code_block
from .ast_parse_replace import ast_parse_replace
from .js_ast_parse_replace import js_ast_parse_replace
from .validate_code_changes import validate_code_changes
from .debug_text_replace import debug_text_replace
from .detect_file_format import detect_file_format
from .analyze_js_structure import analyze_js_structure

__all__ = [
    'find_code_block',
    'ast_parse_replace',
    'js_ast_parse_replace',
    'validate_code_changes',
    'debug_text_replace',
    'detect_file_format',
    'analyze_js_structure',
]
