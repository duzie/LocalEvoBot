"""
Git 技能 - 工具实现
"""

import os
import subprocess
import json
from typing import List, Optional
from langchain_core.tools import tool
from web.backend.shared import shared
from datetime import datetime


def _error_payload(code: str, message: str, **fields) -> dict:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: dict = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload


def _ok_payload(message: str = "", **fields) -> dict:
    payload: dict = {"ok": True}
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


def _run_git_command(args: List[str], cwd: str = None) -> str:
    """执行 Git 命令"""
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return f"❌ Git 错误：{result.stderr.strip()}"
        
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "❌ Git 命令超时"
    except FileNotFoundError:
        return "❌ 未找到 Git，请确认已安装"
    except Exception as e:
        return f"❌ 执行失败：{e}"


@tool
def git_status(repo_path: str) -> str:
    """
    查看 Git 仓库状态
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        状态信息
    """
    tool_name = "git_status"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    git_dir = os.path.join(repo_path, '.git')
    if not os.path.exists(git_dir):
        return _error_payload("not_git_repo", f"不是 Git 仓库：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    result = _run_git_command(['status'], cwd=repo_path)
    _emit_event(tool_name, "status_checked", repo_path=repo_path)
    return _ok_payload(result, repo_path=repo_path)


@tool
def git_diff(repo_path: str, staged: bool = False) -> str:
    """
    查看代码变更
    
    Args:
        repo_path: 仓库路径
        staged: 是否查看暂存区的变更
    
    Returns:
        变更内容
    """
    tool_name = "git_diff"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    args = ['diff']
    if staged:
        args.append('--cached')
    
    result = _run_git_command(args, cwd=repo_path)
    _emit_event(tool_name, "diff_checked", repo_path=repo_path, staged=staged)
    return _ok_payload(result, repo_path=repo_path, staged=staged)


@tool
def git_commit(repo_path: str, message: str, all_files: bool = False) -> str:
    """
    提交代码
    
    Args:
        repo_path: 仓库路径
        message: 提交信息
        all_files: 是否包含所有修改的文件
    
    Returns:
        提交结果
    """
    tool_name = "git_commit"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    args = ['commit', '-m', message]
    if all_files:
        args.insert(1, '-a')
    
    result = _run_git_command(args, cwd=repo_path)
    _emit_event(tool_name, "commit_completed", repo_path=repo_path, message=message, all_files=all_files)
    return _ok_payload(result, repo_path=repo_path, message=message, all_files=all_files)


@tool
def git_push(repo_path: str, remote: str = 'origin', branch: str = None) -> str:
    """
    推送代码
    
    Args:
        repo_path: 仓库路径
        remote: 远程仓库名
        branch: 分支名（可选，默认当前分支）
    
    Returns:
        推送结果
    """
    tool_name = "git_push"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    args = ['push', remote]
    if branch:
        args.append(branch)
    
    result = _run_git_command(args, cwd=repo_path)
    _emit_event(tool_name, "push_completed", repo_path=repo_path, remote=remote, branch=branch)
    return _ok_payload(result, repo_path=repo_path, remote=remote, branch=branch)


@tool
def git_pull(repo_path: str, remote: str = 'origin', branch: str = None) -> str:
    """
    拉取代码
    
    Args:
        repo_path: 仓库路径
        remote: 远程仓库名
        branch: 分支名（可选，默认当前分支）
    
    Returns:
        拉取结果
    """
    tool_name = "git_pull"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    args = ['pull', remote]
    if branch:
        args.append(branch)
    
    result = _run_git_command(args, cwd=repo_path)
    _emit_event(tool_name, "pull_completed", repo_path=repo_path, remote=remote, branch=branch)
    return _ok_payload(result, repo_path=repo_path, remote=remote, branch=branch)


@tool
def git_branch(repo_path: str, list_all: bool = False, create: str = None, delete: str = None) -> str:
    """
    分支管理
    
    Args:
        repo_path: 仓库路径
        list_all: 是否列出所有分支（包括远程）
        create: 创建新分支
        delete: 删除分支
    
    Returns:
        操作结果
    """
    tool_name = "git_branch"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    if delete:
        result = _run_git_command(['branch', '-d', delete], cwd=repo_path)
        _emit_event(tool_name, "branch_deleted", repo_path=repo_path, branch=delete)
        return _ok_payload(result, repo_path=repo_path, action="delete", branch=delete)
    
    if create:
        result = _run_git_command(['branch', create], cwd=repo_path)
        _emit_event(tool_name, "branch_created", repo_path=repo_path, branch=create)
        return _ok_payload(result, repo_path=repo_path, action="create", branch=create)
    
    args = ['branch']
    if list_all:
        args.append('-a')
    
    result = _run_git_command(args, cwd=repo_path)
    _emit_event(tool_name, "branch_listed", repo_path=repo_path, list_all=list_all)
    return _ok_payload(result, repo_path=repo_path, action="list", list_all=list_all)


@tool
def git_log(repo_path: str, max_commits: int = 10, oneline: bool = True) -> str:
    """
    查看提交历史
    
    Args:
        repo_path: 仓库路径
        max_commits: 最大显示数量
        oneline: 是否单行显示
    
    Returns:
        提交历史
    """
    tool_name = "git_log"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    args = ['log', f'-n{max_commits}']
    if oneline:
        args.append('--oneline')
    
    result = _run_git_command(args, cwd=repo_path)
    _emit_event(tool_name, "log_viewed", repo_path=repo_path, max_commits=max_commits, oneline=oneline)
    return _ok_payload(result, repo_path=repo_path, max_commits=max_commits, oneline=oneline)


@tool
def git_checkout(repo_path: str, branch: str, create_new: bool = False) -> str:
    """
    切换分支
    
    Args:
        repo_path: 仓库路径
        branch: 分支名
        create_new: 是否创建新分支并切换
    
    Returns:
        切换结果
    """
    tool_name = "git_checkout"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    args = ['checkout']
    if create_new:
        args.append('-b')
    args.append(branch)
    
    result = _run_git_command(args, cwd=repo_path)
    _emit_event(tool_name, "checkout_completed", repo_path=repo_path, branch=branch, create_new=create_new)
    return _ok_payload(result, repo_path=repo_path, branch=branch, create_new=create_new)


@tool
def git_add(repo_path: str, files: List[str] = None, all_files: bool = False) -> str:
    """
    添加文件到暂存区
    
    Args:
        repo_path: 仓库路径
        files: 文件列表
        all_files: 是否添加所有文件
    
    Returns:
        操作结果
    """
    tool_name = "git_add"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    args = ['add']
    if all_files:
        args.append('.')
    elif files:
        args.extend(files)
    else:
        return _error_payload("invalid_arguments", "请指定文件或设置 all_files=True", tool=tool_name, repo_path=repo_path)
    
    result = _run_git_command(args, cwd=repo_path)
    _emit_event(tool_name, "files_added", repo_path=repo_path, files=files, all_files=all_files)
    return _ok_payload(result, repo_path=repo_path, files=files, all_files=all_files)


@tool
def git_clone(repo_url: str, target_path: str = None) -> str:
    """
    克隆仓库
    
    Args:
        repo_url: 仓库 URL
        target_path: 目标路径（可选）
    
    Returns:
        克隆结果
    """
    tool_name = "git_clone"
    args = ['clone', repo_url]
    if target_path:
        args.append(target_path)
    
    result = _run_git_command(args)
    _emit_event(tool_name, "clone_completed", repo_url=repo_url, target_path=target_path)
    return _ok_payload(result, repo_url=repo_url, target_path=target_path)


@tool
def git_init(repo_path: str) -> str:
    """
    初始化 Git 仓库
    
    Args:
        repo_path: 仓库路径
    
    Returns:
        初始化结果
    """
    tool_name = "git_init"
    if not os.path.isdir(repo_path):
        return _error_payload("directory_not_found", f"目录不存在：{repo_path}", tool=tool_name, repo_path=repo_path)
    
    result = _run_git_command(['init'], cwd=repo_path)
    _emit_event(tool_name, "init_completed", repo_path=repo_path)
    return _ok_payload(result, repo_path=repo_path)
