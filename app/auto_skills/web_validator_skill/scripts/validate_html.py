"""
validate_html - HTML 结构校验工具

验证 HTML 文档结构是否合法，检查标签闭合、属性格式等。
"""

from langchain_core.tools import tool
import os
import re
from typing import Dict, Any, List


@tool
def validate_html(file_path: str, strict_mode: bool = False) -> Dict[str, Any]:
    """
    HTML 结构校验工具
    
    Args:
        file_path: HTML 文件路径
        strict_mode: 严格模式（默认 False）
            - True: 检查所有标签必须闭合
            - False: 允许自闭合标签（如 <br>, <img>）
    
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
            "warnings": [...]  # 仅严格模式下
        }
    """
    tool_name = "validate_html"
    
    try:
        # 1. 检查文件
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在：{file_path}"
            }
        
        # 2. 检查扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.html', '.htm', '.xhtml']:
            return {
                "success": False,
                "error": f"不是 HTML 文件：{ext}"
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
        
        # 4. 基础检查
        
        # 检查 DOCTYPE
        if not re.search(r'<!DOCTYPE\s+html', content, re.IGNORECASE):
            warnings.append({
                "line": 1,
                "col": 1,
                "message": "缺少 DOCTYPE 声明",
                "code": "MISSING_DOCTYPE"
            })
        
        # 检查 html 标签
        if not re.search(r'<html[^>]*>', content, re.IGNORECASE):
            errors.append({
                "line": 1,
                "col": 1,
                "message": "缺少 <html> 标签",
                "code": "MISSING_HTML_TAG"
            })
        
        # 检查 head 标签
        if not re.search(r'<head[^>]*>.*?</head>', content, re.IGNORECASE | re.DOTALL):
            warnings.append({
                "line": 1,
                "col": 1,
                "message": "缺少 <head> 标签",
                "code": "MISSING_HEAD_TAG"
            })
        
        # 检查 body 标签
        if not re.search(r'<body[^>]*>.*?</body>', content, re.IGNORECASE | re.DOTALL):
            errors.append({
                "line": 1,
                "col": 1,
                "message": "缺少 <body> 标签",
                "code": "MISSING_BODY_TAG"
            })
        
        # 5. 标签闭合检查（简化版）
        lines = content.split('\n')
        tag_stack = []
        self_closing_tags = ['br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 'col', 'embed', 'param', 'source', 'track', 'wbr']
        
        for line_num, line in enumerate(lines, 1):
            # 查找所有标签
            tags = re.findall(r'<(/?)(\w+)([^>]*)/?>', line)
            
            for close_flag, tag_name, attrs in tags:
                tag_name = tag_name.lower()
                
                # 跳过注释和脚本内容
                if tag_name in ['script', 'style']:
                    continue
                
                # 自闭合标签
                if attrs.rstrip().endswith('/'):
                    continue
                
                # 自闭合标签列表
                if tag_name in self_closing_tags:
                    continue
                
                if close_flag:  # 闭合标签
                    if not tag_stack:
                        errors.append({
                            "line": line_num,
                            "col": line.find(f'</{tag_name}'),
                            "message": f"多余的闭合标签 </{tag_name}>",
                            "code": "EXTRA_CLOSING_TAG"
                        })
                    elif tag_stack[-1] != tag_name:
                        # 检查是否在前面有匹配的开启标签
                        if tag_name in tag_stack:
                            errors.append({
                                "line": line_num,
                                "col": line.find(f'</{tag_name}'),
                                "message": f"标签嵌套错误：<{tag_stack[-1]}> 内不能闭合 </{tag_name}>",
                                "code": "TAG_NESTING_ERROR"
                            })
                            tag_stack.remove(tag_name)
                        else:
                            errors.append({
                                "line": line_num,
                                "col": line.find(f'</{tag_name}'),
                                "message": f"未配对的闭合标签 </{tag_name}>",
                                "code": "UNCLOSED_TAG"
                            })
                    else:
                        tag_stack.pop()
                else:  # 开启标签
                    tag_stack.append(tag_name)
        
        # 检查未闭合的标签
        if tag_stack and strict_mode:
            for tag in tag_stack[:5]:  # 最多报告 5 个
                errors.append({
                    "line": len(lines),
                    "col": 0,
                    "message": f"未闭合的标签 <{tag}>",
                    "code": "UNCLOSED_TAG"
                })
        
        # 6. 属性检查
        # 检查引号
        unquoted_attrs = re.findall(r'\s(\w+)=([^\s"\'>]+)(?=[\s>])', content)
        if unquoted_attrs and strict_mode:
            for attr, value in unquoted_attrs[:5]:
                warnings.append({
                    "line": 0,
                    "col": 0,
                    "message": f"属性值应该用引号包裹：{attr}={value}",
                    "code": "UNQUOTED_ATTRIBUTE"
                })
        
        # 7. 返回结果
        if errors:
            return {
                "success": False,
                "file_path": file_path,
                "error_count": len(errors),
                "warning_count": len(warnings) if strict_mode else 0,
                "errors": errors,
                "warnings": warnings if strict_mode else []
            }
        else:
            return {
                "success": True,
                "message": "HTML 结构校验通过",
                "warning_count": len(warnings) if strict_mode else 0,
                "warnings": warnings if strict_mode else []
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"校验失败：{e}"
        }


@tool
def check_html_links(file_path: str, check_external: bool = False) -> Dict[str, Any]:
    """
    检查 HTML 文件中的链接
    
    Args:
        file_path: HTML 文件路径
        check_external: 是否检查外部链接（默认 False，只检查内部链接）
    
    Returns:
        {
            "success": True/False,
            "total_links": 总数，
            "internal_links": [...],
            "external_links": [...],
            "broken_links": [...]  # 仅当 check_external=True 时
        }
    """
    tool_name = "check_html_links"
    
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在：{file_path}"
            }
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取所有链接
        links = re.findall(r'href=["\']([^"\']+)["\']', content)
        
        internal = []
        external = []
        
        for link in links:
            if link.startswith(('http://', 'https://', '//')):
                external.append(link)
            else:
                internal.append(link)
        
        result = {
            "success": True,
            "total_links": len(links),
            "internal_links": internal,
            "external_links": external if check_external else []
        }
        
        # 检查内部链接是否存在（仅相对路径）
        broken = []
        base_dir = os.path.dirname(file_path)
        
        for link in internal:
            # 跳过锚点和特殊链接
            if link.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
                continue
            
            # 移除查询参数
            link_path = link.split('?')[0].split('#')[0]
            
            # 检查文件是否存在
            if link_path and not os.path.exists(os.path.join(base_dir, link_path)):
                broken.append({
                    "link": link,
                    "reason": "文件不存在"
                })
        
        if broken:
            result["broken_links"] = broken
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"检查失败：{e}"
        }
