"""
代码审查技能 - 工具实现
"""

import os
import ast
import re
from typing import List, Dict, Any
from pathlib import Path
from langchain_core.tools import tool
from web.backend.shared import shared
from datetime import datetime


def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload


def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload


def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))


@tool
def review_code(file_path: str) -> str:
    """
    审查单个文件的代码质量
    
    检查项：
    - 语法错误
    - 代码风格 (PEP8)
    - 潜在 bug
    - 代码复杂度
    - 命名规范
    
    Args:
        file_path: 文件路径
    
    Returns:
        审查报告
    """
    tool_name = "review_code"
    try:
        if not os.path.exists(file_path):
            return _error_payload("file_not_found", f"文件不存在：{file_path}", tool=tool_name, file_path=file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return _error_payload("read_failed", f"读取文件失败：{e}", tool=tool_name, file_path=file_path)
    
    issues = []
    warnings = []
    infos = []
    
    # 1. 语法检查
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        issues.append(f"❌ 语法错误 (行{e.lineno}): {e.msg}")
        return _error_payload("syntax_error", "\n".join(issues), tool=tool_name, file_path=file_path)
    
    # 2. 代码风格检查
    lines = content.splitlines()
    
    for i, line in enumerate(lines, 1):
        # 行长度检查
        if len(line) > 120:
            warnings.append(f"⚠️ 行{i} 超过 120 字符 (当前{len(line)}字符)")
        
        # Tab 检查
        if '\t' in line:
            infos.append(f"ℹ️ 行{i}: 使用空格代替 Tab")
        
        # 末尾空格检查
        if line.rstrip() != line:
            infos.append(f"ℹ️ 行{i}: 移除末尾空格")
    
    # 3. 命名规范检查
    naming_pattern = re.compile(r'def\s+(\w+)|class\s+(\w+)')
    for match in naming_pattern.finditer(content):
        name = match.group(1) or match.group(2)
        if name:
            # 函数/类命名检查
            if match.group(1) and not name.islower() and '_' not in name:
                if len(name) > 1:  # 单字母函数名可能是故意的
                    infos.append(f"ℹ️ 函数 '{name}' 建议使用 snake_case 命名")
            
            if match.group(2) and not name[0].isupper():
                infos.append(f"ℹ️ 类 '{name}' 建议使用 PascalCase 命名")
    
    # 4. 复杂度检查（简单的函数长度检查）
    func_pattern = re.compile(r'def\s+\w+\s*\([^)]*\)\s*:')
    func_starts = [m.start() for m in func_pattern.finditer(content)]
    
    for i, start in enumerate(func_starts):
        end = func_starts[i + 1] if i + 1 < len(func_starts) else len(content)
        func_content = content[start:end]
        func_lines = func_content.count('\n')
        
        if func_lines > 50:
            warnings.append(f"⚠️ 函数超过 50 行 (当前{func_lines}行)，建议拆分")
    
    # 5. 常见问题检查
    common_issues = [
        (r'print\s*\(', 'ℹ️ 生产代码建议移除 print 语句'),
        (r'#\s*TODO|#\s*FIXME', 'ℹ️ 存在待办事项'),
        (r'import\s+\*', '⚠️ 避免使用通配符导入'),
        (r'eval\s*\(|exec\s*\(', '❌ 避免使用 eval/exec，存在安全风险'),
        (r'except\s*:', '⚠️ 避免裸 except，建议指定异常类型'),
    ]
    
    for pattern, message in common_issues:
        matches = list(re.finditer(pattern, content))
        if matches:
            if '❌' in message:
                issues.append(f"{message} (找到{len(matches)}处)")
            elif '⚠️' in message:
                warnings.append(f"{message} (找到{len(matches)}处)")
            else:
                infos.append(f"{message} (找到{len(matches)}处)")
    
    # 生成报告
    report = [f"📋 代码审查报告：{os.path.basename(file_path)}", ""]
    
    if issues:
        report.append("## ❌ 严重问题")
        report.extend(issues)
        report.append("")
    
    if warnings:
        report.append("## ⚠️ 警告")
        report.extend(warnings[:10])  # 限制显示数量
        if len(warnings) > 10:
            report.append(f"... 还有 {len(warnings) - 10} 个警告")
        report.append("")
    
    if infos:
        report.append("## ℹ️ 建议")
        report.extend(infos[:10])  # 限制显示数量
        if len(infos) > 10:
            report.append(f"... 还有 {len(infos) - 10} 个建议")
        report.append("")
    
    if not issues and not warnings and not infos:
        report.append("✅ 代码质量良好！")
    
    report.append("")
    report.append(f"统计：{len(issues)} 个问题，{len(warnings)} 个警告，{len(infos)} 个建议")
    
    _emit_event(tool_name, "review_completed", file_path=file_path, issues=len(issues), warnings=len(warnings), infos=len(infos))
    return _ok_payload("\n".join(report), file_path=file_path, issues=len(issues), warnings=len(warnings), infos=len(infos))


@tool
def review_project(project_path: str, max_files: int = 20) -> str:
    """
    审查整个项目的代码结构
    
    Args:
        project_path: 项目路径
        max_files: 最大检查文件数
    
    Returns:
        审查报告
    """
    tool_name = "review_project"
    try:
        if not os.path.isdir(project_path):
            return _error_payload("directory_not_found", f"目录不存在：{project_path}", tool=tool_name, project_path=project_path)
        
        # 收集 Python 文件
        python_files = []
        for root, dirs, files in os.walk(project_path):
            # 跳过常见忽略目录
            dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', 'venv', 'env', 'node_modules', '.venv'}]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
                    
                    if len(python_files) >= max_files:
                        break
            
            if len(python_files) >= max_files:
                break
        
        if not python_files:
            return _ok_payload("未找到 Python 文件", project_path=project_path, files_found=0)
        
        # 项目结构分析
        report = [
            f"📋 项目审查报告：{os.path.basename(project_path)}",
            "",
            f"找到 {len(python_files)} 个 Python 文件",
            "",
            "## 项目结构",
        ]
        
        # 目录结构
        dir_structure = {}
        for f in python_files:
            rel_path = os.path.relpath(f, project_path)
            parts = rel_path.split(os.sep)
            if len(parts) > 1:
                dir_structure[parts[0]] = dir_structure.get(parts[0], 0) + 1
        
        for dir_name, count in sorted(dir_structure.items()):
            report.append(f"- {dir_name}/ ({count} 个文件)")
        
        report.append("")
        report.append("## 文件审查摘要")
        report.append("")
        
        # 审查每个文件（简化版）
        total_issues = 0
        total_warnings = 0
        
        for file_path in python_files[:10]:  # 只详细检查前 10 个
            rel_path = os.path.relpath(file_path, project_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 简单检查
                issues = 0
                warnings = 0
                
                if 'import *' in content:
                    warnings += 1
                if 'eval(' in content or 'exec(' in content:
                    issues += 1
                if len(content.splitlines()) > 500:
                    warnings += 1
                
                total_issues += issues
                total_warnings += warnings
                
                if issues or warnings:
                    report.append(f"- {rel_path}: {issues} 个问题，{warnings} 个警告")
            
            except Exception as e:
                report.append(f"- {rel_path}: 读取失败 ({e})")
        
        report.append("")
        report.append(f"总计：{total_issues} 个严重问题，{total_warnings} 个警告")
        
        if total_issues == 0 and total_warnings == 0:
            report.append("")
            report.append("✅ 项目代码质量良好！")
        
        _emit_event(tool_name, "review_completed", project_path=project_path, total_files=len(python_files), total_issues=total_issues, total_warnings=total_warnings)
        return _ok_payload("\n".join(report), project_path=project_path, total_files=len(python_files), total_issues=total_issues, total_warnings=total_warnings)
    
    except Exception as e:
        return _error_payload("review_failed", str(e), tool=tool_name, project_path=project_path)


@tool
def check_security(file_path: str) -> str:
    """
    检查代码安全问题
    
    Args:
        file_path: 文件路径
    
    Returns:
        安全检查报告
    """
    tool_name = "check_security"
    try:
        if not os.path.exists(file_path):
            return _error_payload("file_not_found", f"文件不存在：{file_path}", tool=tool_name, file_path=file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return _error_payload("read_failed", f"读取文件失败：{e}", tool=tool_name, file_path=file_path)
    
    vulnerabilities = []
    
    # 安全检查项
    security_checks = [
        (r'eval\s*\(', '❌ 高风险：使用 eval() 可能执行恶意代码'),
        (r'exec\s*\(', '❌ 高风险：使用 exec() 可能执行恶意代码'),
        (r'os\.system\s*\(', '⚠️ 中风险：os.system() 可能存在命令注入'),
        (r'subprocess\..*shell\s*=\s*True', '⚠️ 中风险：subprocess 使用 shell=True'),
        (r'pickle\.load', '⚠️ 中风险：pickle.load() 可能反序列化恶意数据'),
        (r'yaml\.load\s*\([^)]*\)\s*$', '⚠️ 中风险：yaml.load() 应使用 safe_load'),
        (r'input\s*\(\s*\)\s*\.eval', '❌ 高风险：input() 后直接 eval'),
        (r'__import__', '⚠️ 中风险：使用 __import__ 动态导入'),
        (r'password\s*=\s*["\'][^"\']+["\']', '⚠️ 中风险：硬编码密码'),
        (r'secret\s*=\s*["\'][^"\']+["\']', '⚠️ 中风险：硬编码密钥'),
        (r'api_key\s*=\s*["\'][^"\']+["\']', '⚠️ 中风险：硬编码 API 密钥'),
    ]
    
    for pattern, message in security_checks:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if matches:
            vulnerabilities.append(f"{message} (找到{len(matches)}处)")
    
    # 生成报告
    report = [f"🔒 安全检查报告：{os.path.basename(file_path)}", ""]
    
    if vulnerabilities:
        report.append("## 发现的安全问题")
        report.extend(vulnerabilities)
        report.append("")
        report.append("## 建议")
        report.append("1. 立即修复所有 ❌ 高风险问题")
        report.append("2. 审查所有 ⚠️ 中风险问题")
        report.append("3. 使用环境变量存储敏感信息")
        report.append("4. 使用 secrets 模块生成安全随机数")
    else:
        report.append("✅ 未发现明显安全问题")
        report.append("")
        report.append("注意：此检查仅覆盖常见问题，不能保证完全安全。")
    
    _emit_event(tool_name, "security_check_completed", file_path=file_path, vulnerabilities=len(vulnerabilities))
    return _ok_payload("\n".join(report), file_path=file_path, vulnerabilities=len(vulnerabilities))


@tool
def check_performance(file_path: str) -> str:
    """
    检查代码性能问题
    
    Args:
        file_path: 文件路径
    
    Returns:
        性能检查报告
    """
    tool_name = "check_performance"
    try:
        if not os.path.exists(file_path):
            return _error_payload("file_not_found", f"文件不存在：{file_path}", tool=tool_name, file_path=file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return _error_payload("read_failed", f"读取文件失败：{e}", tool=tool_name, file_path=file_path)
    
    issues = []
    
    # 性能检查项
    performance_checks = [
        (r'for\s+\w+\s+in\s+range\s*\(\s*len\s*\([^)]+\)\s*\)', '⚠️ 建议使用 enumerate() 代替 range(len(...))'),
        (r'\.append\s*\([^)]*\)\s+in\s+for', 'ℹ️ 循环中频繁 append 可能影响性能'),
        (r'while\s+True:', '⚠️ 确保有正确的退出条件'),
        (r'import\s+time\s*.*\s*time\.sleep', 'ℹ️ 检查是否有不必要的 sleep'),
        (r'for\s+\w+\s+in\s+\[', '⚠️ 循环中使用列表字面量，建议改为元组'),
        (r'\+\s*=\s*\[', '⚠️ 列表拼接建议使用 extend()'),
        (r'global\s+\w+', 'ℹ️ 全局变量可能影响性能'),
    ]
    
    for pattern, message in performance_checks:
        matches = list(re.finditer(pattern, content))
        if matches:
            issues.append(f"{message} (找到{len(matches)}处)")
    
    # 生成报告
    report = [f"⚡ 性能检查报告：{os.path.basename(file_path)}", ""]
    
    if issues:
        report.append("## 发现的性能问题")
        report.extend(issues)
        report.append("")
        report.append("## 优化建议")
        report.append("1. 使用列表推导式代替循环")
        report.append("2. 使用生成器处理大数据")
        report.append("3. 缓存重复计算的结果")
        report.append("4. 使用适当的数据结构")
    else:
        report.append("✅ 未发现明显的性能问题")
    
    _emit_event(tool_name, "performance_check_completed", file_path=file_path, issues=len(issues))
    return _ok_payload("\n".join(report), file_path=file_path, issues=len(issues))


@tool
def suggest_refactoring(file_path: str) -> str:
    """
    提供重构建议
    
    Args:
        file_path: 文件路径
    
    Returns:
        重构建议报告
    """
    tool_name = "suggest_refactoring"
    try:
        if not os.path.exists(file_path):
            return _error_payload("file_not_found", f"文件不存在：{file_path}", tool=tool_name, file_path=file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
    except Exception as e:
        return _error_payload("read_failed", f"读取文件失败：{e}", tool=tool_name, file_path=file_path)
    
    suggestions = []
    
    # 分析代码结构
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _error_payload("syntax_error", "代码有语法错误，无法分析", tool=tool_name, file_path=file_path)
    
    # 检查函数
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # 函数过长
            if node.end_lineno and (node.end_lineno - node.lineno) > 50:
                suggestions.append(f"ℹ️ 函数 '{node.name}' 过长 ({node.end_lineno - node.lineno}行)，建议拆分")
            
            # 参数过多
            if len(node.args.args) > 5:
                suggestions.append(f"ℹ️ 函数 '{node.name}' 参数过多 ({len(node.args.args)}个)，考虑使用配置对象")
            
            # 嵌套过深
            max_depth = _get_max_nesting_depth(node)
            if max_depth > 4:
                suggestions.append(f"ℹ️ 函数 '{node.name}' 嵌套过深 ({max_depth}层)，建议简化逻辑")
    
    # 检查类
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
            if len(methods) > 10:
                suggestions.append(f"ℹ️ 类 '{node.name}' 方法过多 ({len(methods)}个)，考虑拆分")
    
    # 重复代码检查（简化版）
    line_counts = {}
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            line_counts[stripped] = line_counts.get(stripped, 0) + 1
    
    duplicates = [(line, count) for line, count in line_counts.items() if count > 3]
    if duplicates:
        suggestions.append(f"ℹ️ 发现 {len(duplicates)} 行重复代码，考虑提取为函数")
    
    # 生成报告
    report = [f"🔧 重构建议：{os.path.basename(file_path)}", ""]
    
    if suggestions:
        report.append("## 重构建议")
        report.extend(suggestions[:10])
        if len(suggestions) > 10:
            report.append(f"... 还有 {len(suggestions) - 10} 个建议")
    else:
        report.append("✅ 代码结构良好，暂无重构建议")
    
    _emit_event(tool_name, "refactoring_check_completed", file_path=file_path, suggestions=len(suggestions))
    return _ok_payload("\n".join(report), file_path=file_path, suggestions=len(suggestions))


def _get_max_nesting_depth(node, current_depth=0) -> int:
    """计算代码嵌套深度"""
    max_depth = current_depth
    
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            child_depth = _get_max_nesting_depth(child, current_depth + 1)
            max_depth = max(max_depth, child_depth)
        else:
            child_depth = _get_max_nesting_depth(child, current_depth)
            max_depth = max(max_depth, child_depth)
    
    return max_depth
