"""
validate_css - CSS 语法校验工具

检查 CSS 语法错误、未使用的选择器、兼容性问题等。
"""

from langchain_core.tools import tool
import os
import re
from typing import Dict, Any, List


@tool
def validate_css(file_path: str) -> Dict[str, Any]:
    """
    CSS 语法校验工具
    
    Args:
        file_path: CSS 文件路径
    
    Returns:
        {
            "success": True/False,
            "message": "校验通过/失败",
            "errors": [
                {
                    "line": 行号，
                    "col": 列号，
                    "message": "错误信息",
                    "code": "错误代码"
                }
            ],
            "warnings": [...]
        }
    """
    tool_name = "validate_css"
    
    try:
        # 1. 检查文件
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在：{file_path}"
            }
        
        # 2. 检查扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.css', '.scss', '.sass', '.less']:
            return {
                "success": False,
                "error": f"不是 CSS 文件：{ext}"
            }
        
        # 3. 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception:
                return {
                    "success": False,
                    "error": "无法读取文件（编码不支持）"
                }
        
        errors = []
        warnings = []
        
        # 4. 基础语法检查
        lines = content.split('\n')
        
        # 括号匹配
        brace_count = 0
        paren_count = 0
        
        for line_num, line in enumerate(lines, 1):
            # 跳过注释
            if line.strip().startswith('/*') or line.strip().startswith('//'):
                continue
            
            for char in line:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                elif char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
            
            # 检查负数
            if brace_count < 0:
                errors.append({
                    "line": line_num,
                    "col": 0,
                    "message": "多余的闭合大括号 }",
                    "code": "EXTRA_BRACE"
                })
                brace_count = 0
            elif paren_count < 0:
                errors.append({
                    "line": line_num,
                    "col": 0,
                    "message": "多余的闭合括号 )",
                    "code": "EXTRA_PAREN"
                })
                paren_count = 0
        
        # 检查未闭合
        if brace_count > 0:
            errors.append({
                "line": len(lines),
                "col": 0,
                "message": f"未闭合的大括号 {{ 共{brace_count}个",
                "code": "UNCLOSED_BRACE"
            })
        
        if paren_count > 0:
            errors.append({
                "line": len(lines),
                "col": 0,
                "message": f"未闭合的括号 ( 共{paren_count}个",
                "code": "UNCLOSED_PAREN"
            })
        
        # 5. 属性检查
        # 检查缺少分号
        property_pattern = re.compile(r'^\s*[\w-]+\s*:\s*[^;{}]+$', re.MULTILINE)
        for match in property_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            # 检查下一行是否以 } 开头（允许最后一行没有分号）
            next_line_start = match.end()
            while next_line_start < len(content) and content[next_line_start] in ['\n', ' ', '\t']:
                next_line_start += 1
            
            if next_line_start < len(content) and content[next_line_start] != '}':
                warnings.append({
                    "line": line_num,
                    "col": 0,
                    "message": "属性缺少分号 ;",
                    "code": "MISSING_SEMICOLON"
                })
        
        # 6. 常见错误检查
        
        # 检查无效的颜色值
        invalid_colors = re.findall(r'#[0-9a-fA-F]{5}(?![0-9a-fA-F])', content)
        for color in invalid_colors:
            warnings.append({
                "line": 0,
                "col": 0,
                "message": f"无效的颜色值：{color}（应该是 3 位或 6 位）",
                "code": "INVALID_COLOR"
            })
        
        # 检查常见的拼写错误
        common_typos = {
            'dispaly': 'display',
            'positon': 'position',
            'maring': 'margin',
            'pading': 'padding',
            'borderr': 'border',
            'backgroud': 'background',
            'heigth': 'height',
            'widht': 'width',
        }
        
        for typo, correct in common_typos.items():
            if re.search(rf'\b{typo}\b', content, re.IGNORECASE):
                warnings.append({
                    "line": 0,
                    "col": 0,
                    "message": f"可能的拼写错误：{typo} 应该是 {correct}",
                    "code": "TYPO"
                })
        
        # 7. 返回结果
        if errors:
            return {
                "success": False,
                "file_path": file_path,
                "error_count": len(errors),
                "warning_count": len(warnings),
                "errors": errors,
                "warnings": warnings
            }
        else:
            return {
                "success": True,
                "message": "CSS 语法校验通过",
                "warning_count": len(warnings),
                "warnings": warnings
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"校验失败：{e}"
        }


@tool
def check_css_compatibility(file_path: str, min_browser_versions: Dict[str, int] = None) -> Dict[str, Any]:
    """
    检查 CSS 的浏览器兼容性
    
    Args:
        file_path: CSS 文件路径
        min_browser_versions: 最低浏览器版本要求
            {"chrome": 80, "firefox": 75, "safari": 13, "edge": 80}
    
    Returns:
        {
            "success": True/False,
            "incompatible_properties": [...],
            "vendor_prefixes_needed": [...]
        }
    """
    tool_name = "check_css_compatibility"
    
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在：{file_path}"
            }
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        incompatible = []
        prefixes_needed = []
        
        # 检查需要 vendor prefix 的属性
        prefix_properties = {
            'transform': ['-webkit-transform', '-ms-transform'],
            'transition': ['-webkit-transition'],
            'flex': ['-webkit-flex', '-ms-flexbox'],
            'grid': ['-ms-grid'],
            'filter': ['-webkit-filter'],
            'backdrop-filter': ['-webkit-backdrop-filter'],
        }
        
        import re
        for prop, prefixes in prefix_properties.items():
            if re.search(rf'\b{prop}\s*:', content):
                # 检查是否已经使用了 prefix
                has_prefix = any(re.search(rf'\b{prefix}\s*:', content) for prefix in prefixes)
                if not has_prefix:
                    prefixes_needed.append({
                        "property": prop,
                        "needed_prefixes": prefixes
                    })
        
        # 检查新特性
        new_features = {
            r'\bcontainer\s+type\b': 'Container Queries（较新）',
            r'\b@layer\b': 'Cascade Layers（较新）',
            r'\b:has\(': ':has() 选择器（较新）',
            r'\bsubgrid\b': 'subgrid（较新）',
        }
        
        for pattern, feature in new_features.items():
            if re.search(pattern, content):
                incompatible.append({
                    "feature": feature,
                    "pattern": pattern
                })
        
        return {
            "success": True,
            "incompatible_properties": incompatible,
            "vendor_prefixes_needed": prefixes_needed,
            "message": f"发现 {len(incompatible)} 个兼容性问题，{len(prefixes_needed)} 个需要添加 vendor prefix"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"检查失败：{e}"
        }
