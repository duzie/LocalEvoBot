"""
改进的调试文本替换工具
更好地处理特殊字符、换行符、编码问题
"""
from langchain_core.tools import tool
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple
from web.backend.shared import shared


def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is not None:
            payload[str(k)] = v
    return payload


def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is not None:
            payload[str(k)] = v
    return payload


def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is not None:
            payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))


def detect_file_encoding(file_path: str) -> str:
    """检测文件编码"""
    try:
        import chardet
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return result.get('encoding', 'utf-8')
    except:
        return 'utf-8'


def detect_line_ending(content: str) -> str:
    """检测换行符类型"""
    if '\r\n' in content:
        return '\r\n'
    elif '\n' in content:
        return '\n'
    elif '\r' in content:
        return '\r'
    else:
        return '\n'


def normalize_line_endings(text: str, target_ending: str = '\n') -> str:
    """统一换行符"""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if target_ending != '\n':
        text = text.replace('\n', target_ending)
    return text


def escape_special_chars(text: str) -> str:
    """转义特殊字符以便显示"""
    return text.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')


def find_best_match(content: str, old_text: str, threshold: float = 0.8) -> List[Dict[str, Any]]:
    """查找最佳匹配位置"""
    matches = []
    
    # 1. 精确匹配
    if old_text in content:
        idx = content.find(old_text)
        matches.append({
            "type": "exact",
            "position": idx,
            "similarity": 1.0,
            "text": old_text[:100]
        })
        return matches
    
    # 2. 忽略空白差异的匹配
    old_normalized = re.sub(r'\s+', ' ', old_text.strip())
    content_normalized = re.sub(r'\s+', ' ', content)
    
    if old_normalized in content_normalized:
        idx = content_normalized.find(old_normalized)
        matches.append({
            "type": "whitespace_normalized",
            "position": idx,
            "similarity": 0.95,
            "text": content_normalized[idx:idx+100]
        })
    
    # 3. 逐行匹配
    old_lines = old_text.splitlines()
    content_lines = content.splitlines()
    
    for i in range(len(content_lines) - len(old_lines) + 1):
        candidate_lines = content_lines[i:i+len(old_lines)]
        similarity = calculate_lines_similarity(old_lines, candidate_lines)
        
        if similarity >= threshold:
            matches.append({
                "type": "line_based",
                "start_line": i,
                "end_line": i + len(old_lines) - 1,
                "similarity": similarity,
                "text": '\n'.join(candidate_lines[:3]) + ("..." if len(candidate_lines) > 3 else "")
            })
    
    # 按相似度排序
    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return matches


def calculate_lines_similarity(lines1: List[str], lines2: List[str]) -> float:
    """计算两组行的相似度"""
    if len(lines1) != len(lines2):
        return 0.0
    
    matches = 0
    for l1, l2 in zip(lines1, lines2):
        # 移除空白后比较
        clean_l1 = re.sub(r'\s+', '', l1.strip())
        clean_l2 = re.sub(r'\s+', '', l2.strip())
        
        if clean_l1 == clean_l2:
            matches += 1
        elif clean_l1 in clean_l2 or clean_l2 in clean_l1:
            matches += 0.5
    
    return matches / len(lines1) if lines1 else 0.0


def analyze_differences(content: str, old_text: str) -> Dict[str, Any]:
    """分析差异"""
    old_lines = old_text.splitlines()
    content_lines = content.splitlines()
    
    differences = {
        "line_count_diff": abs(len(content_lines) - len(old_lines)),
        "char_count_diff": abs(len(content) - len(old_text)),
        "line_ending_diff": {
            "content": detect_line_ending(content),
            "old_text": detect_line_ending(old_text)
        },
        "encoding_issues": [],
        "whitespace_diff": {
            "content_spaces": content.count(' '),
            "old_text_spaces": old_text.count(' '),
            "content_tabs": content.count('\t'),
            "old_text_tabs": old_text.count('\t')
        }
    }
    
    # 检查编码问题
    try:
        content.encode('utf-8')
    except UnicodeEncodeError as e:
        differences["encoding_issues"].append(f"Content encoding error: {e}")
    
    try:
        old_text.encode('utf-8')
    except UnicodeEncodeError as e:
        differences["encoding_issues"].append(f"Old text encoding error: {e}")
    
    return differences


@tool
def debug_text_replace(
    file_path: str,
    old_text: str,
    new_text: str,
    fuzzy_match: bool = True,
    preserve_line_ending: bool = True,
    show_debug_info: bool = True
) -> Dict[str, Any]:
    """
    增强的调试文本替换工具，更好地处理特殊字符和换行符
    
    Args:
        file_path: 文件路径
        old_text: 原文本
        new_text: 新文本
        fuzzy_match: 是否启用模糊匹配
        preserve_line_ending: 是否保持原始换行符
        show_debug_info: 是否显示详细调试信息
    """
    tool_name = "debug_text_replace"
    
    try:
        # 检测文件编码
        encoding = detect_file_encoding(file_path)
        
        # 读取文件
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
        
        # 检测换行符
        original_line_ending = detect_line_ending(content)
        
        # 统一换行符进行处理
        content_normalized = normalize_line_endings(content, '\n')
        old_text_normalized = normalize_line_endings(old_text, '\n')
        new_text_normalized = normalize_line_endings(new_text, '\n')
        
        # 1. 尝试精确匹配
        if old_text_normalized in content_normalized:
            # 执行替换
            new_content_normalized = content_normalized.replace(old_text_normalized, new_text_normalized)
            
            # 恢复原始换行符
            if preserve_line_ending:
                new_content = normalize_line_endings(new_content_normalized, original_line_ending)
            else:
                new_content = new_content_normalized
            
            # 写回文件
            with open(file_path, 'w', encoding=encoding, newline='') as f:
                f.write(new_content)
            
            result = {
                "file_path": file_path,
                "replace_type": "exact",
                "fuzzy_match_used": False,
                "replacements_made": content_normalized.count(old_text_normalized),
                "success": True,
                "encoding": encoding,
                "line_ending": repr(original_line_ending)
            }
            
            _emit_event(tool_name, "completed", result=result)
            return _ok_payload(f"精确匹配替换完成，替换了 {result['replacements_made']} 处", **result)
        
        # 2. 如果精确匹配失败，尝试模糊匹配
        if fuzzy_match:
            matches = find_best_match(content_normalized, old_text_normalized)
            
            if matches:
                best_match = matches[0]
                
                if best_match["type"] == "whitespace_normalized":
                    # 空白差异匹配
                    old_normalized = re.sub(r'\s+', ' ', old_text_normalized.strip())
                    content_normalized_re = re.sub(r'\s+', ' ', content_normalized)
                    new_content_normalized = content_normalized_re.replace(old_normalized, new_text_normalized)
                    
                    # 恢复原始格式
                    if preserve_line_ending:
                        new_content = normalize_line_endings(new_content_normalized, original_line_ending)
                    else:
                        new_content = new_content_normalized
                    
                    with open(file_path, 'w', encoding=encoding, newline='') as f:
                        f.write(new_content)
                    
                    result = {
                        "file_path": file_path,
                        "replace_type": "whitespace_normalized",
                        "fuzzy_match_used": True,
                        "replacements_made": 1,
                        "success": True,
                        "match_info": best_match,
                        "encoding": encoding
                    }
                    
                    _emit_event(tool_name, "completed", result=result)
                    return _ok_payload("空白差异匹配替换完成", **result)
                
                elif best_match["type"] == "line_based":
                    # 行级匹配
                    start_line = best_match["start_line"]
                    end_line = best_match["end_line"]
                    
                    content_lines = content_normalized.splitlines()
                    new_lines = new_text_normalized.splitlines()
                    
                    # 替换行
                    new_content_lines = content_lines[:start_line] + new_lines + content_lines[end_line+1:]
                    new_content_normalized = '\n'.join(new_content_lines)
                    
                    if preserve_line_ending:
                        new_content = normalize_line_endings(new_content_normalized, original_line_ending)
                    else:
                        new_content = new_content_normalized
                    
                    with open(file_path, 'w', encoding=encoding, newline='') as f:
                        f.write(new_content)
                    
                    result = {
                        "file_path": file_path,
                        "replace_type": "line_based",
                        "fuzzy_match_used": True,
                        "replacements_made": 1,
                        "success": True,
                        "match_info": best_match,
                        "start_line": start_line + 1,
                        "end_line": end_line + 1,
                        "encoding": encoding
                    }
                    
                    _emit_event(tool_name, "completed", result=result)
                    return _ok_payload(f"行级匹配替换完成 (第{start_line+1}-{end_line+1}行)", **result)
        
        # 3. 所有匹配都失败，提供详细调试信息
        if show_debug_info:
            debug_info = {
                "file_path": file_path,
                "encoding": encoding,
                "line_ending": repr(original_line_ending),
                "content_length": len(content),
                "old_text_length": len(old_text),
                "old_text_preview": escape_special_chars(old_text[:200]),
                "differences": analyze_differences(content, old_text),
                "possible_matches": matches[:5] if fuzzy_match else [],
                "suggestions": []
            }
            
            # 生成建议
            if debug_info["differences"]["line_ending_diff"]["content"] != debug_info["differences"]["line_ending_diff"]["old_text"]:
                debug_info["suggestions"].append("换行符不一致，建议统一换行符")
            
            if debug_info["differences"]["whitespace_diff"]["content_spaces"] != debug_info["differences"]["whitespace_diff"]["old_text_spaces"]:
                debug_info["suggestions"].append("空格数量不一致，可能存在空白差异")
            
            result = {
                "file_path": file_path,
                "success": False,
                "fuzzy_match_enabled": fuzzy_match,
                "debug_info": debug_info
            }
            
            error_msg = "未找到匹配的文本。已提供详细调试信息。"
            _emit_event(tool_name, "failed", result=result)
            return _ok_payload(error_msg, **result)
        
        return _error_payload("not_found", "未找到匹配的文本", tool=tool_name)
    
    except FileNotFoundError:
        err = _error_payload("file_not_found", f"文件不存在: {file_path}", tool=tool_name)
        _emit_event(tool_name, "error", error=f"文件不存在: {file_path}")
        return err
    except UnicodeDecodeError as e:
        err = _error_payload("encoding_error", f"文件编码错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err
    except Exception as e:
        err = _error_payload("unknown_error", f"调试文本替换时发生错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


if __name__ == "__main__":
    print("调试文本替换工具已加载")
